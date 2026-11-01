//! Regression tests for defect F2: thox-agentd did not stop its
//! supervised agents on SIGTERM, so bare (non-systemd) runs orphaned
//! them.
//!
//! Coverage:
//! - `Supervisor::shutdown_all` terminates a cooperative agent quickly.
//! - It escalates to SIGKILL when an agent ignores SIGTERM, inside a
//!   bounded grace period.
//! - It kills the agent's whole process group, so children the agent
//!   forked do not survive either.
//! - End to end: the real `thox-agentd` binary, sent SIGTERM and SIGINT,
//!   exits on its own and leaves its autostarted agent dead.

use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Arc;
use std::time::{Duration, Instant};

use serde_json::json;

use thox_agentos::audit::AuditLog;
use thox_agentos::client::request;
use thox_agentos::identity::{
    generate_signing_key, issue_token, verifying_key_to_hex, Claims, TrustStore,
};
use thox_agentos::manifest::{Manifest, Permissions, Restart, RestartPolicy};
use thox_agentos::supervisor::{AgentState, Supervisor};
use thox_agentos::util::now_unix;

fn unique_dir(tag: &str) -> PathBuf {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.subsec_nanos())
        .unwrap_or(0);
    let dir = std::env::temp_dir().join(format!(
        "thox-agentos-shutdown-{}-{}-{}",
        tag,
        std::process::id(),
        nanos
    ));
    std::fs::create_dir_all(&dir).expect("create temp dir");
    dir
}

fn trust_with(key_id: &str, key: &ed25519_dalek::SigningKey) -> TrustStore {
    let mut trust = TrustStore::default();
    trust.insert(key_id.to_string(), key.verifying_key());
    trust
}

fn claims(agent: &str, issuer: &str) -> Claims {
    Claims {
        agent: agent.to_string(),
        issuer: issuer.to_string(),
        issued_at: now_unix(),
        expires_at: None,
    }
}

fn sleeper_manifest(name: &str, token: String) -> Manifest {
    Manifest {
        name: name.to_string(),
        command: vec!["/bin/sleep".to_string(), "300".to_string()],
        env: Default::default(),
        permissions: Permissions::default(),
        restart: Restart {
            policy: RestartPolicy::Never,
            max_restarts: 0,
            backoff_ms: 50,
        },
        identity_token: token,
        autostart: false,
    }
}

/// True while `pid` exists as a live (non-zombie) process. /proc based:
/// a zombie still has a /proc entry, and state Z must count as dead
/// because the regression is about the agent process surviving.
fn process_alive(pid: u32) -> bool {
    let stat = match std::fs::read_to_string(format!("/proc/{pid}/stat")) {
        Ok(s) => s,
        Err(_) => return false,
    };
    // comm is parenthesized and may contain spaces; parse after the
    // last closing paren: state, ppid, pgrp, ...
    let after = stat.rsplit(')').next().unwrap_or("");
    let state = after.split_whitespace().next().unwrap_or("");
    state != "Z" && state != "X" && !state.is_empty()
}

fn process_group(pid: u32) -> Option<u32> {
    let stat = std::fs::read_to_string(format!("/proc/{pid}/stat")).ok()?;
    let after = stat.rsplit(')').next()?;
    // Fields after comm: state(1) ppid(2) pgrp(3) in /proc pid stat
    // numbering; in the split remainder they are indexes 0, 1, 2.
    after.split_whitespace().nth(2)?.parse().ok()
}

fn wait_until_dead(pid: u32, timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if !process_alive(pid) {
            return true;
        }
        std::thread::sleep(Duration::from_millis(25));
    }
    !process_alive(pid)
}

fn force_kill(pid: u32) {
    let _ = Command::new("/bin/kill")
        .args(["-KILL", &pid.to_string()])
        .status();
}

#[test]
fn supervisor_shutdown_terminates_cooperative_agent() {
    let dir = unique_dir("coop");
    let audit = Arc::new(AuditLog::open(dir.join("audit.log")).unwrap());
    let sup = Supervisor::new(dir.clone(), audit);
    let key = generate_signing_key();
    let trust = trust_with("thox", &key);
    let token = issue_token(&key, &claims("sleeper", "thox"));
    sup.register(sleeper_manifest("sleeper", token), &trust).unwrap();
    sup.start("sleeper").unwrap();
    let pid = sup.status("sleeper").unwrap().pid.unwrap();
    assert!(process_alive(pid), "agent should be running before shutdown");
    // The agent leads its own process group (group id equals its pid),
    // which is what lets shutdown signal the whole group.
    assert_eq!(process_group(pid), Some(pid));

    let started = Instant::now();
    let stopped = sup.shutdown_all(Duration::from_secs(5));
    let elapsed = started.elapsed();

    assert_eq!(stopped, 1);
    assert!(
        elapsed < Duration::from_secs(4),
        "cooperative agent should die on SIGTERM well inside the grace period, took {elapsed:?}"
    );
    assert!(
        wait_until_dead(pid, Duration::from_secs(2)),
        "agent pid {pid} survived supervisor shutdown"
    );
    assert_eq!(sup.status("sleeper").unwrap().state, AgentState::Stopped);
}

#[test]
fn supervisor_shutdown_escalates_to_sigkill_after_grace() {
    let dir = unique_dir("stubborn");
    let audit = Arc::new(AuditLog::open(dir.join("audit.log")).unwrap());
    let sup = Supervisor::new(dir.clone(), audit);
    let key = generate_signing_key();
    let trust = trust_with("thox", &key);
    let token = issue_token(&key, &claims("stubborn", "thox"));
    let mut m = sleeper_manifest("stubborn", token);
    // An agent that ignores SIGTERM entirely: only SIGKILL can stop it.
    m.command = vec![
        "/bin/sh".to_string(),
        "-c".to_string(),
        "trap '' TERM; while :; do sleep 1; done".to_string(),
    ];
    sup.register(m, &trust).unwrap();
    sup.start("stubborn").unwrap();
    let pid = sup.status("stubborn").unwrap().pid.unwrap();
    assert!(process_alive(pid));
    // Give the shell a moment to install its trap before the signal.
    std::thread::sleep(Duration::from_millis(300));

    let grace = Duration::from_millis(400);
    let started = Instant::now();
    let stopped = sup.shutdown_all(grace);
    let elapsed = started.elapsed();

    assert_eq!(stopped, 1);
    assert!(
        elapsed >= Duration::from_millis(300),
        "shutdown returned before the grace period elapsed ({elapsed:?}); SIGTERM was not given a chance"
    );
    assert!(
        elapsed < Duration::from_secs(10),
        "shutdown must stay bounded even when an agent ignores SIGTERM, took {elapsed:?}"
    );
    if !wait_until_dead(pid, Duration::from_secs(2)) {
        force_kill(pid);
        panic!("agent pid {pid} survived SIGKILL escalation");
    }
}

#[test]
fn supervisor_shutdown_kills_agent_process_group_children() {
    let dir = unique_dir("group");
    let audit = Arc::new(AuditLog::open(dir.join("audit.log")).unwrap());
    let sup = Supervisor::new(dir.clone(), audit);
    let key = generate_signing_key();
    let trust = trust_with("thox", &key);
    let token = issue_token(&key, &claims("parent", "thox"));
    let mut m = sleeper_manifest("parent", token);
    let pid_file = dir.join("grandchild.pid");
    m.command = vec![
        "/bin/sh".to_string(),
        "-c".to_string(),
        format!(
            "sleep 300 & echo $! > {}; wait",
            pid_file.display()
        ),
    ];
    sup.register(m, &trust).unwrap();
    sup.start("parent").unwrap();
    let pid = sup.status("parent").unwrap().pid.unwrap();

    // Wait for the agent to report the pid of the child it forked.
    let deadline = Instant::now() + Duration::from_secs(5);
    let grandchild: u32 = loop {
        if let Ok(text) = std::fs::read_to_string(&pid_file) {
            if let Ok(p) = text.trim().parse::<u32>() {
                break p;
            }
        }
        assert!(Instant::now() < deadline, "agent never reported its child pid");
        std::thread::sleep(Duration::from_millis(25));
    };
    assert!(process_alive(pid));
    assert!(process_alive(grandchild));

    let stopped = sup.shutdown_all(Duration::from_secs(3));
    assert_eq!(stopped, 1);
    let parent_dead = wait_until_dead(pid, Duration::from_secs(2));
    let grandchild_dead = wait_until_dead(grandchild, Duration::from_secs(2));
    if !grandchild_dead {
        force_kill(grandchild);
    }
    if !parent_dead {
        force_kill(pid);
    }
    assert!(parent_dead, "agent pid {pid} survived shutdown");
    assert!(
        grandchild_dead,
        "child pid {grandchild} forked by the agent survived shutdown; process group was not signaled"
    );
}

/// Spawn the real daemon with one autostarted sleeper agent, deliver
/// `signal` to the daemon, and verify the daemon exits successfully and
/// the agent does not survive it. Returns Err with diagnostics instead
/// of panicking so the caller can clean up leaked processes first.
fn daemon_signal_scenario(signal: &str) -> Result<(), String> {
    let root = unique_dir(&format!("daemon{signal}"));
    let state_dir = root.join("state");
    let agents_dir = root.join("agents");
    let trust_dir = root.join("trust");
    std::fs::create_dir_all(&state_dir).map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&agents_dir).map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&trust_dir).map_err(|e| e.to_string())?;

    let key = generate_signing_key();
    std::fs::write(
        trust_dir.join("thox.pub"),
        verifying_key_to_hex(&key.verifying_key()),
    )
    .map_err(|e| e.to_string())?;
    let token = issue_token(&key, &claims("sleeper", "thox"));
    let manifest_json = format!(
        "{{\"name\":\"sleeper\",\"command\":[\"/bin/sleep\",\"300\"],\"autostart\":true,\"restart\":{{\"policy\":\"never\",\"max_restarts\":0,\"backoff_ms\":50}},\"identity_token\":\"{token}\"}}"
    );
    std::fs::write(agents_dir.join("sleeper.json"), manifest_json)
        .map_err(|e| e.to_string())?;

    let daemon_log = root.join("daemon.out");
    let log_file = std::fs::File::create(&daemon_log).map_err(|e| e.to_string())?;
    let log_err = log_file.try_clone().map_err(|e| e.to_string())?;
    let mut daemon: Child = Command::new(env!("CARGO_BIN_EXE_thox-agentd"))
        .args([
            "--state-dir",
            state_dir.to_str().unwrap(),
            "--agents-dir",
            agents_dir.to_str().unwrap(),
            "--trust-dir",
            trust_dir.to_str().unwrap(),
        ])
        .stdin(Stdio::null())
        .stdout(Stdio::from(log_file))
        .stderr(Stdio::from(log_err))
        .spawn()
        .map_err(|e| format!("cannot spawn thox-agentd: {e}"))?;
    let daemon_pid = daemon.id();
    let socket = state_dir.join("run").join("agentd.sock");
    let mut agent_pid_seen: Option<u32> = None;

    let run = |daemon: &mut Child,
               agent_pid_seen: &mut Option<u32>|
     -> Result<u32, String> {
        // Wait for the control socket, then confirm the agent is up.
        let deadline = Instant::now() + Duration::from_secs(15);
        while !socket.exists() {
            if let Some(status) = daemon.try_wait().map_err(|e| e.to_string())? {
                let out = std::fs::read_to_string(&daemon_log).unwrap_or_default();
                return Err(format!("daemon exited early with {status}; log: {out}"));
            }
            if Instant::now() >= deadline {
                return Err("daemon socket never appeared".to_string());
            }
            std::thread::sleep(Duration::from_millis(50));
        }
        let deadline = Instant::now() + Duration::from_secs(15);
        let agent_pid = loop {
            let resp = request(&socket, json!({"cmd": "status", "name": "sleeper"}))
                .map_err(|e| format!("status request failed: {e}"))?;
            if let Some(pid) = resp
                .get("status")
                .and_then(|s| s.get("pid"))
                .and_then(|p| p.as_u64())
            {
                break pid as u32;
            }
            if Instant::now() >= deadline {
                return Err(format!("agent never reported a pid; last status: {resp}"));
            }
            std::thread::sleep(Duration::from_millis(50));
        };
        *agent_pid_seen = Some(agent_pid);
        if !process_alive(agent_pid) {
            return Err(format!("agent pid {agent_pid} not alive before signal"));
        }
        if process_group(agent_pid) != Some(agent_pid) {
            return Err(format!(
                "agent pid {agent_pid} does not lead its own process group (pgrp {:?})",
                process_group(agent_pid)
            ));
        }

        // Deliver the shutdown signal to the daemon only.
        let kill_status = Command::new("/bin/kill")
            .args([signal, &daemon_pid.to_string()])
            .status()
            .map_err(|e| format!("cannot run /bin/kill: {e}"))?;
        if !kill_status.success() {
            return Err(format!("/bin/kill {signal} {daemon_pid} failed: {kill_status}"));
        }

        // The daemon must exit on its own, promptly and successfully.
        let deadline = Instant::now() + Duration::from_secs(20);
        loop {
            if let Some(status) = daemon.try_wait().map_err(|e| e.to_string())? {
                if !status.success() {
                    let out = std::fs::read_to_string(&daemon_log).unwrap_or_default();
                    return Err(format!("daemon exited with {status} after {signal}; log: {out}"));
                }
                break;
            }
            if Instant::now() >= deadline {
                return Err(format!("daemon did not exit within 20s of {signal}"));
            }
            std::thread::sleep(Duration::from_millis(50));
        }

        // And the supervised agent must be gone (the F2 regression).
        if !wait_until_dead(agent_pid, Duration::from_secs(5)) {
            return Err(format!(
                "agent pid {agent_pid} survived daemon {signal}; F2 regression"
            ));
        }
        Ok(agent_pid)
    };

    let result = run(&mut daemon, &mut agent_pid_seen);
    // Cleanup on any path: never leak the daemon or the agent from a
    // failing run into the rest of the suite.
    let _ = daemon.kill();
    let _ = daemon.wait();
    if let Some(pid) = agent_pid_seen {
        if process_alive(pid) {
            force_kill(pid);
        }
    }
    if let Err(e) = &result {
        eprintln!("daemon {signal} scenario failed: {e}");
        if let Ok(out) = std::fs::read_to_string(&daemon_log) {
            eprintln!("daemon log:\n{out}");
        }
    }
    result.map(|_| ())
}

#[test]
fn daemon_sigterm_terminates_supervised_agent() {
    daemon_signal_scenario("-TERM").unwrap();
}

#[test]
fn daemon_sigint_terminates_supervised_agent() {
    daemon_signal_scenario("-INT").unwrap();
}
