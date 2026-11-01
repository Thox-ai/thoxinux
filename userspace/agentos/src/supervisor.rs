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
//!
//! Shutdown (defect F2): every agent is spawned as the leader of its own
//! process group. `shutdown_all` marks every agent stop-requested so the
//! restart policy cannot fire, sends SIGTERM to each live process group,
//! waits a bounded grace period for the groups to exit, then escalates
//! to SIGKILL for any survivor and reaps it. The daemon calls this when
//! it receives SIGTERM or SIGINT, so a bare (non-systemd) run leaves no
//! supervised agent behind.

use std::collections::HashMap;
use std::fs::OpenOptions;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use serde::Serialize;

#[cfg(unix)]
use std::os::unix::process::CommandExt;

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

/// Default grace period between SIGTERM and SIGKILL during daemon
/// shutdown. Agents that exit on SIGTERM finish well inside it; agents
/// that ignore SIGTERM are force-killed once it elapses.
pub const DEFAULT_SHUTDOWN_GRACE: Duration = Duration::from_secs(3);

/// Send `sig` to the process group led by `pid`, falling back to the
/// single process when the group does not exist (yet). Agents are
/// spawned with `process_group(0)`, so the group id equals the agent
/// pid and anything the agent itself forked is signaled with it.
/// Returns true when a signal was delivered to the group or the pid.
#[cfg(unix)]
fn signal_group(pid: u32, sig: libc::c_int) -> bool {
    // SAFETY: kill(2) with a pid and signal the caller owns the target
    // of; no memory is touched. A negative pid targets the process
    // group, the positive form targets the single process.
    let group_rc = unsafe { libc::kill(-(pid as libc::pid_t), sig) };
    if group_rc == 0 {
        return true;
    }
    unsafe { libc::kill(pid as libc::pid_t, sig) == 0 }
}

#[cfg(not(unix))]
fn signal_group(_pid: u32, _sig: i32) -> bool {
    false
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
        // Each agent leads its own process group so shutdown can signal
        // the whole group (the agent plus anything it forked) without
        // touching the daemon group.
        #[cfg(unix)]
        cmd.process_group(0);
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
            // SIGKILL semantics as before, but delivered to the whole
            // process group so helpers the agent forked die with it.
            #[cfg(unix)]
            signal_group(child.id(), libc::SIGKILL);
            let _ = child.kill();
            let _ = child.wait();
        }
        handle.state = AgentState::Stopped;
        let _ = self.audit.append("thox-agentd", "agent.stop", name, "ok", "stopped by request");
        Ok(())
    }

    /// Terminate every supervised agent. Used by the daemon on shutdown
    /// (SIGTERM or SIGINT) so no agent is orphaned when the daemon exits
    /// outside a systemd control group.
    ///
    /// Sequence: mark all agents stop-requested (restart policy must not
    /// resurrect them), SIGTERM every live process group, poll for exit
    /// until `grace` elapses, then SIGKILL the surviving groups and reap
    /// them. Returns the number of agents that had a live child when the
    /// shutdown began.
    pub fn shutdown_all(&self, grace: Duration) -> usize {
        // Phase 1: suppress restarts and collect live pids, then SIGTERM
        // each process group. Signaling happens after the lock is
        // released so a slow syscall never blocks the monitor thread.
        let mut live: Vec<(String, u32)> = Vec::new();
        {
            let mut agents = self.agents.lock().expect("supervisor mutex");
            for (name, handle) in agents.iter_mut() {
                handle.stop_requested = true;
                handle.restart_at = None;
                if handle.state == AgentState::Restarting {
                    handle.state = AgentState::Stopped;
                }
                if let Some(child) = handle.child.as_ref() {
                    live.push((name.clone(), child.id()));
                }
            }
        }
        if live.is_empty() {
            return 0;
        }
        let total = live.len();
        #[cfg(unix)]
        for (_, pid) in &live {
            signal_group(*pid, libc::SIGTERM);
        }
        #[cfg(not(unix))]
        for (name, _) in &live {
            let _ = self.stop(name);
        }
        let _ = self.audit.append(
            "thox-agentd",
            "daemon.shutdown",
            "",
            "ok",
            &format!(
                "SIGTERM sent to {total} agent process group(s); grace {} ms",
                grace.as_millis()
            ),
        );

        // Phase 2: bounded grace period. Poll try_wait under short lock
        // holds; exited children are reaped and recorded here rather
        // than by the monitor tick, which now sees stop_requested.
        let deadline = Instant::now() + grace;
        loop {
            let mut remaining = 0usize;
            {
                let mut agents = self.agents.lock().expect("supervisor mutex");
                for handle in agents.values_mut() {
                    let exited = match handle.child.as_mut() {
                        Some(child) => match child.try_wait() {
                            Ok(Some(status)) => Some(status.code()),
                            Ok(None) => None,
                            Err(_) => Some(None),
                        },
                        None => continue,
                    };
                    match exited {
                        Some(code) => {
                            handle.child = None;
                            handle.last_exit_code = code;
                            handle.state = AgentState::Stopped;
                        }
                        None => remaining += 1,
                    }
                }
            }
            if remaining == 0 || Instant::now() >= deadline {
                break;
            }
            std::thread::sleep(Duration::from_millis(25));
        }

        // Phase 3: SIGKILL survivors (whole group plus the child handle
        // itself, covering a group that was never created) and reap.
        let mut survivors: Vec<(String, u32)> = Vec::new();
        {
            let agents = self.agents.lock().expect("supervisor mutex");
            for (name, handle) in agents.iter() {
                if let Some(child) = handle.child.as_ref() {
                    survivors.push((name.clone(), child.id()));
                }
            }
        }
        if !survivors.is_empty() {
            #[cfg(unix)]
            for (_, pid) in &survivors {
                signal_group(*pid, libc::SIGKILL);
            }
            let mut agents = self.agents.lock().expect("supervisor mutex");
            for (name, handle) in agents.iter_mut() {
                if let Some(mut child) = handle.child.take() {
                    let _ = child.kill();
                    let _ = child.wait();
                    handle.state = AgentState::Stopped;
                    let _ = self.audit.append(
                        "thox-agentd",
                        "daemon.shutdown",
                        name,
                        "ok",
                        "agent did not exit within the grace period; SIGKILL sent",
                    );
                }
            }
        }
        total
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
