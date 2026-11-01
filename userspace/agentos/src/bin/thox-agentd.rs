//! thox-agentd: the ThoxOS agent supervisor daemon.
//!
//! Loads agent manifests from the agents directory, verifies each agent
//! identity token against the trust store before registering it, starts
//! agents marked autostart, and serves a line-delimited JSON control API
//! on a Unix socket. The same socket carries tool broker requests from
//! agents: a tool request names the requesting agent, and the broker
//! enforces that agent manifest's capability grants.
//!
//! Usage:
//!   thox-agentd [--state-dir DIR] [--agents-dir DIR] [--trust-dir DIR]
//!               [--socket PATH]
//!
//! Defaults come from THOX_AGENTOS_HOME when set, else ~/.local/share and
//! ~/.config under the home directory (see thox-agentos util module).
//!
//! Shutdown: SIGTERM and SIGINT ask the daemon to stop. The accept loop
//! polls a flag set by the signal handler, then the supervisor
//! terminates every supervised agent (SIGTERM to each agent process
//! group, bounded grace period, SIGKILL for survivors) before the
//! daemon exits. This fixes defect F2: previously the daemon had no
//! signal handling at all, so a bare run orphaned its agents and only
//! the systemd control-group kill masked the bug.

use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixListener;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use serde_json::{json, Value};

use thox_agentos::audit::AuditLog;
use thox_agentos::broker::Broker;
use thox_agentos::identity::TrustStore;
use thox_agentos::manifest::Manifest;
use thox_agentos::supervisor::{Supervisor, DEFAULT_SHUTDOWN_GRACE};
use thox_agentos::util::{config_dir, base_dir, tail_lines};

/// Set by the SIGTERM and SIGINT handlers; polled by the accept loop.
/// The handler does nothing else: all shutdown work happens on the main
/// thread, outside signal context.
static SHUTDOWN_REQUESTED: AtomicBool = AtomicBool::new(false);

extern "C" fn on_shutdown_signal(_sig: libc::c_int) {
    SHUTDOWN_REQUESTED.store(true, Ordering::SeqCst);
}

/// Install handlers for SIGTERM and SIGINT. Installed before any agent
/// is spawned, so a shutdown request can never arrive in a window where
/// agents exist but nobody is listening for the signal.
fn install_signal_handlers() {
    // SAFETY: the handler only stores to a static AtomicBool, which is
    // async-signal-safe. sa_mask is emptied and no SA_RESTART is set;
    // the listener is nonblocking and polled, so no syscall needs to
    // resume after the handler runs.
    unsafe {
        let mut sa: libc::sigaction = std::mem::zeroed();
        sa.sa_sigaction = on_shutdown_signal as *const () as libc::sighandler_t;
        libc::sigemptyset(&mut sa.sa_mask);
        sa.sa_flags = 0;
        libc::sigaction(libc::SIGTERM, &sa, std::ptr::null_mut());
        libc::sigaction(libc::SIGINT, &sa, std::ptr::null_mut());
    }
}

struct Config {
    state_dir: PathBuf,
    agents_dir: PathBuf,
    trust_dir: PathBuf,
    socket: PathBuf,
}

fn parse_args() -> Config {
    let mut state_dir = base_dir();
    let mut agents_dir = config_dir().join("agents");
    let mut trust_dir = config_dir().join("trust");
    let mut socket: Option<PathBuf> = None;
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--state-dir" => {
                i += 1;
                state_dir = PathBuf::from(args.get(i).cloned().unwrap_or_default());
            }
            "--agents-dir" => {
                i += 1;
                agents_dir = PathBuf::from(args.get(i).cloned().unwrap_or_default());
            }
            "--trust-dir" => {
                i += 1;
                trust_dir = PathBuf::from(args.get(i).cloned().unwrap_or_default());
            }
            "--socket" => {
                i += 1;
                socket = Some(PathBuf::from(args.get(i).cloned().unwrap_or_default()));
            }
            "-h" | "--help" => {
                println!("usage: thox-agentd [--state-dir DIR] [--agents-dir DIR] [--trust-dir DIR] [--socket PATH]");
                std::process::exit(0);
            }
            other => {
                eprintln!("thox-agentd: unknown argument {other}");
                std::process::exit(2);
            }
        }
        i += 1;
    }
    let socket = socket.unwrap_or_else(|| state_dir.join("run").join("agentd.sock"));
    Config {
        state_dir,
        agents_dir,
        trust_dir,
        socket,
    }
}

fn load_agents(sup: &Supervisor, trust: &TrustStore, agents_dir: &PathBuf) -> Vec<String> {
    let mut notes = Vec::new();
    if !agents_dir.exists() {
        notes.push(format!("agents dir {} does not exist yet", agents_dir.display()));
        return notes;
    }
    let mut paths: Vec<PathBuf> = match std::fs::read_dir(agents_dir) {
        Ok(rd) => rd
            .flatten()
            .map(|e| e.path())
            .filter(|p| p.extension().and_then(|s| s.to_str()) == Some("json"))
            .collect(),
        Err(e) => {
            notes.push(format!("cannot read agents dir: {e}"));
            return notes;
        }
    };
    paths.sort();
    for path in paths {
        match Manifest::load(&path) {
            Ok(manifest) => {
                let name = manifest.name.clone();
                // Reload safety: never clobber the handle of a running
                // agent; its child would be orphaned and untracked.
                if let Some(st) = sup.status(&name) {
                    if st.state == thox_agentos::supervisor::AgentState::Running {
                        notes.push(format!("skipped agent {name}: already running"));
                        continue;
                    }
                }
                let autostart = manifest.autostart;
                match sup.register(manifest, trust) {
                    Ok(()) => {
                        notes.push(format!("registered agent {name}"));
                        if autostart {
                            match sup.start(&name) {
                                Ok(()) => notes.push(format!("autostarted agent {name}")),
                                Err(e) => notes.push(format!("autostart of {name} failed: {e}")),
                            }
                        }
                    }
                    Err(e) => notes.push(format!("refused agent {name}: {e}")),
                }
            }
            Err(e) => notes.push(format!("skipped manifest {}: {e}", path.display())),
        }
    }
    notes
}

fn handle(sup: &Arc<Supervisor>, trust: &TrustStore, agents_dir: &PathBuf, req: &Value) -> Value {
    let cmd = req.get("cmd").and_then(|v| v.as_str()).unwrap_or("");
    let audit = sup.audit();
    match cmd {
        "ping" => json!({"ok": true, "result": "pong"}),
        "list" => {
            let agents: Vec<Value> = sup
                .list()
                .iter()
                .map(|s| serde_json::to_value(s).unwrap_or(Value::Null))
                .collect();
            json!({"ok": true, "agents": agents})
        }
        "status" => match req.get("name").and_then(|v| v.as_str()) {
            Some(name) => match sup.status(name) {
                Some(s) => json!({"ok": true, "status": serde_json::to_value(s).unwrap_or(Value::Null)}),
                None => json!({"ok": false, "error": format!("unknown agent: {name}")}),
            },
            None => {
                let agents: Vec<Value> = sup
                    .list()
                    .iter()
                    .map(|s| serde_json::to_value(s).unwrap_or(Value::Null))
                    .collect();
                json!({"ok": true, "agents": agents})
            }
        },
        "start" => {
            let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
            match sup.start(name) {
                Ok(()) => json!({"ok": true}),
                Err(e) => json!({"ok": false, "error": e}),
            }
        }
        "stop" => {
            let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
            match sup.stop(name) {
                Ok(()) => json!({"ok": true}),
                Err(e) => json!({"ok": false, "error": e}),
            }
        }
        "logs" => {
            let name = req.get("name").and_then(|v| v.as_str()).unwrap_or("");
            let lines = req.get("lines").and_then(|v| v.as_u64()).unwrap_or(50) as usize;
            let path = sup.journal_path(name);
            json!({"ok": true, "lines": tail_lines(&path, lines)})
        }
        "audit" => {
            let lines = req.get("lines").and_then(|v| v.as_u64()).unwrap_or(50) as usize;
            let entries = thox_agentos::audit::read_entries(audit.path(), lines);
            json!({"ok": true, "entries": serde_json::to_value(entries).unwrap_or(Value::Null)})
        }
        "reload" => {
            let notes = load_agents(sup, trust, agents_dir);
            json!({"ok": true, "notes": notes})
        }
        "tool" => {
            let agent = req.get("agent").and_then(|v| v.as_str()).unwrap_or("");
            let tool = req.get("tool").and_then(|v| v.as_str()).unwrap_or("");
            let params = req.get("params").cloned().unwrap_or(json!({}));
            let manifest = match sup.manifest(agent) {
                Some(m) => m,
                None => {
                    return json!({"ok": false, "error": format!("unknown agent: {agent}")})
                }
            };
            if !sup.is_running(agent) {
                let _ = audit.append(agent, &format!("tool.{tool}"), "", "deny", "agent is not running");
                return json!({"ok": false, "error": format!("agent {agent} is not running; broker requests require a running agent")});
            }
            let broker = Broker::new(audit);
            let outcome = broker.execute(agent, &manifest.permissions, tool, &params);
            json!({"ok": outcome.allowed, "result": outcome.result, "reason": outcome.reason})
        }
        "model.show" => match thox_agentos::model::current(sup.state_dir()) {
            Some(m) => json!({"ok": true, "model": serde_json::to_value(m).unwrap_or(Value::Null)}),
            None => json!({"ok": true, "model": Value::Null}),
        },
        "model.swap" => {
            let manifest_value = req.get("manifest").cloned().unwrap_or(Value::Null);
            let manifest: Result<thox_agentos::model::ModelManifest, _> =
                serde_json::from_value(manifest_value);
            match manifest {
                Ok(m) => {
                    let name = m.name.clone();
                    match thox_agentos::model::swap(sup.state_dir(), &m) {
                        Ok(active) => {
                            let _ = audit.append("user", "model.swap", &name, "ok", "model swapped");
                            json!({"ok": true, "model": serde_json::to_value(active).unwrap_or(Value::Null)})
                        }
                        Err(e) => {
                            let _ = audit.append("user", "model.swap", &name, "error", &e);
                            json!({"ok": false, "error": e})
                        }
                    }
                }
                Err(e) => json!({"ok": false, "error": format!("bad model manifest: {e}")}),
            }
        }
        "model.rollback" => match thox_agentos::model::rollback(sup.state_dir()) {
            Ok(active) => {
                let name = active.name.clone();
                let _ = audit.append("user", "model.rollback", &name, "ok", "rolled back");
                json!({"ok": true, "model": serde_json::to_value(active).unwrap_or(Value::Null)})
            }
            Err(e) => json!({"ok": false, "error": e}),
        },
        other => json!({"ok": false, "error": format!("unknown command: {other}")}),
    }
}

fn main() {
    install_signal_handlers();
    let cfg = parse_args();
    std::fs::create_dir_all(&cfg.state_dir).expect("create state dir");
    std::fs::create_dir_all(cfg.state_dir.join("run")).expect("create run dir");
    let audit = Arc::new(
        AuditLog::open(cfg.state_dir.join("audit.log")).expect("open audit log"),
    );
    let trust = TrustStore::load_dir(&cfg.trust_dir).unwrap_or_else(|e| {
        eprintln!("thox-agentd: trust store: {e}");
        TrustStore::default()
    });
    if trust.is_empty() {
        eprintln!(
            "thox-agentd: warning: trust store at {} is empty; every agent will be refused",
            cfg.trust_dir.display()
        );
    }
    let sup = Supervisor::new(cfg.state_dir.clone(), audit.clone());
    // Bind the control socket BEFORE loading or autostarting any agent.
    // If the bind fails (for example the state dir sits on a filesystem
    // that cannot host Unix sockets, such as a drvfs/9p mount), the daemon
    // exits here with nothing started, instead of autostarting agents and
    // then exiting and leaving them orphaned and unsupervised.
    if cfg.socket.exists() {
        std::fs::remove_file(&cfg.socket).ok();
    }
    let listener = UnixListener::bind(&cfg.socket).unwrap_or_else(|e| {
        eprintln!("thox-agentd: cannot bind {}: {e}", cfg.socket.display());
        std::process::exit(1);
    });
    eprintln!("thox-agentd: listening on {}", cfg.socket.display());
    for note in load_agents(&sup, &trust, &cfg.agents_dir) {
        eprintln!("thox-agentd: {note}");
    }
    let _ = audit.append("thox-agentd", "daemon.start", cfg.socket.to_str().unwrap_or(""), "ok", "daemon started");
    // Nonblocking accept loop so the main thread can observe shutdown
    // requests between connections. Behavior per connection is unchanged
    // from the previous blocking `listener.incoming()` loop.
    listener
        .set_nonblocking(true)
        .expect("set listener nonblocking");
    while !SHUTDOWN_REQUESTED.load(Ordering::SeqCst) {
        match listener.accept() {
            Ok((stream, _addr)) => {
                let sup = sup.clone();
                // Reload the trust store per connection so key rotation on
                // disk takes effect without a daemon restart.
                let trust_dir = cfg.trust_dir.clone();
                let agents_dir = cfg.agents_dir.clone();
                std::thread::spawn(move || {
                    let trust = TrustStore::load_dir(&trust_dir).unwrap_or_default();
                    let mut reader = BufReader::new(stream.try_clone().expect("clone stream"));
                    let mut writer = stream;
                    let mut line = String::new();
                    if reader.read_line(&mut line).is_ok() && !line.trim().is_empty() {
                        let req: Value = serde_json::from_str(&line)
                            .unwrap_or_else(|_| json!({"cmd": ""}));
                        let resp = handle(&sup, &trust, &agents_dir, &req);
                        let mut out = serde_json::to_string(&resp).unwrap_or_default();
                        out.push('\n');
                        let _ = writer.write_all(out.as_bytes());
                    }
                });
            }
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                std::thread::sleep(Duration::from_millis(25));
            }
            Err(e) => {
                eprintln!("thox-agentd: accept failed: {e}");
                std::thread::sleep(Duration::from_millis(25));
            }
        }
    }
    // Shutdown requested (SIGTERM or SIGINT). Terminate every supervised
    // agent before exiting so none is orphaned (defect F2), then remove
    // the control socket so a later start is not confused by a stale one.
    eprintln!("thox-agentd: shutdown requested; terminating supervised agents");
    let stopped = sup.shutdown_all(DEFAULT_SHUTDOWN_GRACE);
    let _ = audit.append(
        "thox-agentd",
        "daemon.stop",
        cfg.socket.to_str().unwrap_or(""),
        "ok",
        &format!("daemon stopped; {stopped} supervised agent(s) terminated"),
    );
    eprintln!("thox-agentd: stopped; {stopped} supervised agent(s) terminated");
    std::fs::remove_file(&cfg.socket).ok();
}
