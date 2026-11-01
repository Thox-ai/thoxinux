//! Agent supervision.
//!
//! Each registered agent is a child process of the daemon. The supervisor
//! spawns it with its manifest command, appends stdout and stderr to a
//! per-agent journal file, and restarts it according to the manifest
//! restart policy (always, on-failure, never) up to max_restarts times.
//! A monitor thread ticks over all agents and applies the policy when a
//! child exits. Stopping an agent through the control API suppresses
//! restarts until it is started again.
//!
//! Registration verifies the agent identity token first. An unsigned or
//! unverifiable agent is refused, the refusal is audited, and the agent
//! is never spawned.

use std::collections::HashMap;
use std::fs::OpenOptions;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use serde::Serialize;

use crate::audit::AuditLog;
use crate::identity::TrustStore;
use crate::manifest::{Manifest, RestartPolicy};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum AgentState {
    Registered,
    Running,
    Restarting,
    Stopped,
    Failed,
    Exited,
}

#[derive(Debug, Clone, Serialize)]
pub struct AgentStatus {
    pub name: String,
    pub state: AgentState,
    pub pid: Option<u32>,
    pub restarts: u32,
    pub last_exit_code: Option<i32>,
}

struct AgentHandle {
    manifest: Manifest,
    child: Option<Child>,
    state: AgentState,
    restarts: u32,
    last_exit_code: Option<i32>,
    stop_requested: bool,
    restart_at: Option<Instant>,
}

pub struct Supervisor {
    state_dir: PathBuf,
    audit: Arc<AuditLog>,
    agents: Mutex<HashMap<String, AgentHandle>>,
}

impl Supervisor {
    /// Create a supervisor and start its monitor thread. The returned Arc
    /// is what the daemon shares between connection threads.
    pub fn new(state_dir: PathBuf, audit: Arc<AuditLog>) -> Arc<Supervisor> {
        std::fs::create_dir_all(state_dir.join("journals")).ok();
        let sup = Arc::new(Supervisor {
            state_dir,
            audit,
            agents: Mutex::new(HashMap::new()),
        });
        let weak = Arc::downgrade(&sup);
        std::thread::spawn(move || loop {
            std::thread::sleep(Duration::from_millis(100));
            match weak.upgrade() {
                Some(s) => s.tick(),
                None => break,
            }
        });
        sup
    }

    pub fn state_dir(&self) -> &Path {
        &self.state_dir
    }

    pub fn journal_path(&self, name: &str) -> PathBuf {
        self.state_dir.join("journals").join(format!("{name}.log"))
    }

    pub fn audit(&self) -> &AuditLog {
        &self.audit
    }

    /// Verify identity and register an agent. Returns Err on refusal; the
    /// refusal is written to the audit log before returning.
    pub fn register(&self, manifest: Manifest, trust: &TrustStore) -> Result<(), String> {
        if let Err(e) = trust.verify(&manifest.identity_token, &manifest.name) {
            let reason = e.to_string();
            let _ = self.audit.append(
                "thox-agentd",
                "identity.verify",
                &manifest.name,
                "deny",
                &reason,
            );
            return Err(reason);
        }
        let _ = self.audit.append(
            "thox-agentd",
            "identity.verify",
            &manifest.name,
            "allow",
            "identity token verified offline",
        );
        let name = manifest.name.clone();
        let mut agents = self.agents.lock().expect("supervisor mutex");
        agents.insert(
            name,
            AgentHandle {
                manifest,
                child: None,
                state: AgentState::Registered,
                restarts: 0,
                last_exit_code: None,
                stop_requested: false,
                restart_at: None,
            },
        );
        Ok(())
    }

    pub fn manifest(&self, name: &str) -> Option<Manifest> {
        self.agents
            .lock()
            .expect("supervisor mutex")
            .get(name)
            .map(|h| h.manifest.clone())
    }

    pub fn is_running(&self, name: &str) -> bool {
        self.agents
            .lock()
            .expect("supervisor mutex")
            .get(name)
            .map(|h| h.state == AgentState::Running)
            .unwrap_or(false)
    }

    pub fn start(&self, name: &str) -> Result<(), String> {
        let mut agents = self.agents.lock().expect("supervisor mutex");
        let handle = agents
            .get_mut(name)
            .ok_or_else(|| format!("unknown agent: {name}"))?;
        if handle.state == AgentState::Running {
            return Err(format!("agent {name} is already running"));
        }
        handle.stop_requested = false;
        handle.restarts = 0;
        self.spawn_locked(name, handle)
    }

    fn spawn_locked(&self, name: &str, handle: &mut AgentHandle) -> Result<(), String> {
        let journal = self.journal_path(name);
        let out = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&journal)
            .map_err(|e| format!("cannot open journal {}: {e}", journal.display()))?;
        let err = out
            .try_clone()
            .map_err(|e| format!("cannot clone journal handle: {e}"))?;
        let manifest = &handle.manifest;
        let mut cmd = Command::new(&manifest.command[0]);
        cmd.args(&manifest.command[1..])
            .envs(manifest.env.iter())
            .env("THOX_AGENT_NAME", name)
            .stdin(Stdio::null())
            .stdout(Stdio::from(out))
            .stderr(Stdio::from(err));
        match cmd.spawn() {
            Ok(child) => {
                handle.child = Some(child);
                handle.state = AgentState::Running;
                handle.restart_at = None;
                let _ = self.audit.append(
                    "thox-agentd",
                    "agent.start",
                    name,
                    "ok",
                    "process spawned",
                );
                Ok(())
            }
            Err(e) => {
                handle.state = AgentState::Failed;
                let _ = self.audit.append(
                    "thox-agentd",
                    "agent.start",
                    name,
                    "error",
                    &format!("spawn failed: {e}"),
                );
                Err(format!("spawn failed: {e}"))
            }
        }
    }

    pub fn stop(&self, name: &str) -> Result<(), String> {
        let mut agents = self.agents.lock().expect("supervisor mutex");
        let handle = agents
            .get_mut(name)
            .ok_or_else(|| format!("unknown agent: {name}"))?;
        handle.stop_requested = true;
        handle.restart_at = None;
        if let Some(mut child) = handle.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
        handle.state = AgentState::Stopped;
        let _ = self.audit.append("thox-agentd", "agent.stop", name, "ok", "stopped by request");
        Ok(())
    }

    pub fn status(&self, name: &str) -> Option<AgentStatus> {
        self.agents.lock().expect("supervisor mutex").get(name).map(|h| AgentStatus {
            name: h.manifest.name.clone(),
            state: h.state,
            pid: h.child.as_ref().map(|c| c.id()),
            restarts: h.restarts,
            last_exit_code: h.last_exit_code,
        })
    }

    pub fn list(&self) -> Vec<AgentStatus> {
        let agents = self.agents.lock().expect("supervisor mutex");
        let mut out: Vec<AgentStatus> = agents
            .values()
            .map(|h| AgentStatus {
                name: h.manifest.name.clone(),
                state: h.state,
                pid: h.child.as_ref().map(|c| c.id()),
                restarts: h.restarts,
                last_exit_code: h.last_exit_code,
            })
            .collect();
        out.sort_by(|a, b| a.name.cmp(&b.name));
        out
    }

    /// One monitor pass: collect exited children, apply restart policy,
    /// and fire any restarts whose backoff has elapsed.
    fn tick(&self) {
        let mut agents = self.agents.lock().expect("supervisor mutex");
        let names: Vec<String> = agents.keys().cloned().collect();
        for name in names {
            let handle = match agents.get_mut(&name) {
                Some(h) => h,
                None => continue,
            };
            // Fire a scheduled restart.
            if handle.state == AgentState::Restarting {
                if let Some(at) = handle.restart_at {
                    if Instant::now() >= at {
                        let _ = self.spawn_locked(&name, handle);
                    }
                }
                continue;
            }
            if handle.state != AgentState::Running {
                continue;
            }
            // Some(code) means the child exited (code None on signal or wait
            // error). None means it is still running (or absent).
            let exited: Option<Option<i32>> = match handle.child.as_mut() {
                Some(child) => match child.try_wait() {
                    Ok(Some(status)) => Some(status.code()),
                    Ok(None) => None,
                    Err(_) => Some(None),
                },
                None => None,
            };
            let code = match exited {
                Some(c) => c,
                None => continue,
            };
            handle.child = None;
            handle.last_exit_code = code;
            let _ = self.audit.append(
                "thox-agentd",
                "agent.exit",
                &name,
                "ok",
                &format!("exit code {code:?}, restarts so far {}", handle.restarts),
            );
            if handle.stop_requested {
                handle.state = AgentState::Stopped;
                continue;
            }
            let policy = handle.manifest.restart.policy;
            let failed = code != Some(0);
            let want_restart = match policy {
                RestartPolicy::Always => true,
                RestartPolicy::OnFailure => failed,
                RestartPolicy::Never => false,
            };
            if want_restart && handle.restarts < handle.manifest.restart.max_restarts {
                handle.restarts += 1;
                handle.state = AgentState::Restarting;
                handle.restart_at = Some(
                    Instant::now()
                        + Duration::from_millis(handle.manifest.restart.backoff_ms),
                );
                let _ = self.audit.append(
                    "thox-agentd",
                    "agent.restart",
                    &name,
                    "ok",
                    &format!("restart {} scheduled", handle.restarts),
                );
            } else if want_restart {
                handle.state = AgentState::Failed;
            } else if failed {
                handle.state = AgentState::Exited;
            } else {
                handle.state = AgentState::Exited;
            }
        }
    }
}

/// Helper for callers that need the journals directory for a state dir.
pub fn journals_dir(state_dir: &Path) -> PathBuf {
    state_dir.join("journals")
}
