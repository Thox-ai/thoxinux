//! thox-agent: user CLI for the ThoxOS agent layer.
//!
//! Control commands (talk to thox-agentd over its Unix socket):
//!   thox-agent list
//!   thox-agent status [name]
//!   thox-agent start <name>
//!   thox-agent stop <name>
//!   thox-agent logs <name> [--lines N]
//!   thox-agent reload
//!   thox-agent model show
//!   thox-agent model swap <model-manifest.json>
//!   thox-agent model rollback
//!
//! Local commands (no daemon needed):
//!   thox-agent audit [--lines N]        read the audit log directly
//!   thox-agent keygen --out DIR         create an issuer key pair
//!   thox-agent sign --key FILE --issuer ID --agent NAME [--expires-in-days N]
//!                                       print a signed identity token
//!
//! Global options: --socket PATH, --state-dir DIR.

use std::path::PathBuf;

use serde_json::{json, Value};

use thox_agentos::audit::read_entries;
use thox_agentos::client::request;
use thox_agentos::identity::{
    generate_signing_key, issue_token, signing_key_from_hex, signing_key_to_hex,
    verifying_key_to_hex, Claims,
};
use thox_agentos::util::{base_dir, now_unix};

fn usage() -> ! {
    eprintln!(
        "usage: thox-agent [--socket PATH] [--state-dir DIR] <command>\n\
         commands: list | status [name] | start <name> | stop <name> |\n\
         logs <name> [--lines N] | reload | audit [--lines N] |\n\
         model show | model swap <file> | model rollback |\n\
         keygen --out DIR | sign --key FILE --issuer ID --agent NAME [--expires-in-days N]"
    );
    std::process::exit(2);
}

fn print_json(v: &Value) {
    println!("{}", serde_json::to_string_pretty(v).unwrap_or_default());
}

fn main() {
    let raw: Vec<String> = std::env::args().skip(1).collect();
    let mut socket: Option<PathBuf> = None;
    let mut state_dir = base_dir();
    let mut rest: Vec<String> = Vec::new();
    let mut i = 0;
    while i < raw.len() {
        match raw[i].as_str() {
            "--socket" => {
                i += 1;
                socket = Some(PathBuf::from(raw.get(i).cloned().unwrap_or_else(|| usage())));
            }
            "--state-dir" => {
                i += 1;
                state_dir = PathBuf::from(raw.get(i).cloned().unwrap_or_else(|| usage()));
            }
            other => rest.push(other.to_string()),
        }
        i += 1;
    }
    let socket = socket.unwrap_or_else(|| state_dir.join("run").join("agentd.sock"));
    if rest.is_empty() {
        usage();
    }
    let cmd = rest[0].as_str();
    let args = &rest[1..];

    match cmd {
        "keygen" => {
            let out_idx = args.iter().position(|a| a == "--out");
            let out = match out_idx {
                Some(p) => PathBuf::from(args.get(p + 1).cloned().unwrap_or_else(|| usage())),
                None => usage(),
            };
            std::fs::create_dir_all(&out).expect("create keygen output dir");
            let key = generate_signing_key();
            let key_file = out.join("issuer.key");
            std::fs::write(&key_file, signing_key_to_hex(&key)).expect("write issuer key");
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                std::fs::set_permissions(&key_file, std::fs::Permissions::from_mode(0o600)).ok();
            }
            let pub_file = out.join("issuer.pub");
            std::fs::write(&pub_file, verifying_key_to_hex(&key.verifying_key()))
                .expect("write issuer pub");
            println!("private key (keep secret): {}", key_file.display());
            println!("public key: {}", pub_file.display());
            println!("install the public key in the trust store as <key-id>.pub");
        }
        "sign" => {
            let get = |flag: &str| -> Option<String> {
                args.iter()
                    .position(|a| a == flag)
                    .and_then(|p| args.get(p + 1).cloned())
            };
            let key_file = get("--key").unwrap_or_else(|| usage());
            let issuer = get("--issuer").unwrap_or_else(|| usage());
            let agent = get("--agent").unwrap_or_else(|| usage());
            let days: Option<u64> = get("--expires-in-days").and_then(|v| v.parse().ok());
            let hex = std::fs::read_to_string(&key_file).unwrap_or_else(|e| {
                eprintln!("cannot read key file: {e}");
                std::process::exit(1);
            });
            let key = signing_key_from_hex(&hex).unwrap_or_else(|e| {
                eprintln!("{e}");
                std::process::exit(1);
            });
            let claims = Claims {
                agent,
                issuer,
                issued_at: now_unix(),
                expires_at: days.map(|d| now_unix() + d * 86400),
            };
            println!("{}", issue_token(&key, &claims));
        }
        "audit" => {
            let lines = args
                .iter()
                .position(|a| a == "--lines")
                .and_then(|p| args.get(p + 1))
                .and_then(|v| v.parse::<usize>().ok())
                .unwrap_or(50);
            let entries = read_entries(&state_dir.join("audit.log"), lines);
            for e in &entries {
                println!(
                    "#{seq} {ts} actor={actor} action={action} target={target} decision={decision} {detail}",
                    seq = e.seq,
                    ts = e.ts,
                    actor = e.actor,
                    action = e.action,
                    target = e.target,
                    decision = e.decision,
                    detail = e.detail
                );
            }
            if entries.is_empty() {
                println!("(audit log is empty)");
            }
        }
        "model" => {
            let sub = args.first().map(|s| s.as_str()).unwrap_or("");
            let req = match sub {
                "show" => json!({"cmd": "model.show"}),
                "swap" => {
                    let file = args.get(1).cloned().unwrap_or_else(|| usage());
                    let text = std::fs::read_to_string(&file).unwrap_or_else(|e| {
                        eprintln!("cannot read model manifest: {e}");
                        std::process::exit(1);
                    });
                    let manifest: Value = serde_json::from_str(&text).unwrap_or_else(|e| {
                        eprintln!("bad model manifest json: {e}");
                        std::process::exit(1);
                    });
                    json!({"cmd": "model.swap", "manifest": manifest})
                }
                "rollback" => json!({"cmd": "model.rollback"}),
                _ => usage(),
            };
            match request(&socket, req) {
                Ok(resp) => print_json(&resp),
                Err(e) => {
                    eprintln!("{e}");
                    std::process::exit(1);
                }
            }
        }
        "list" | "status" | "start" | "stop" | "logs" | "reload" => {
            let req = match cmd {
                "list" => json!({"cmd": "list"}),
                "status" => match args.first() {
                    Some(name) => json!({"cmd": "status", "name": name}),
                    None => json!({"cmd": "status"}),
                },
                "start" => json!({"cmd": "start", "name": args.first().cloned().unwrap_or_else(|| usage())}),
                "stop" => json!({"cmd": "stop", "name": args.first().cloned().unwrap_or_else(|| usage())}),
                "logs" => {
                    let lines = args
                        .iter()
                        .position(|a| a == "--lines")
                        .and_then(|p| args.get(p + 1))
                        .and_then(|v| v.parse::<u64>().ok())
                        .unwrap_or(50);
                    json!({"cmd": "logs", "name": args.first().cloned().unwrap_or_else(|| usage()), "lines": lines})
                }
                _ => json!({"cmd": "reload"}),
            };
            match request(&socket, req) {
                Ok(resp) => {
                    if cmd == "logs" {
                        if let Some(lines) = resp.get("lines").and_then(|v| v.as_array()) {
                            for line in lines {
                                println!("{}", line.as_str().unwrap_or(""));
                            }
                            return;
                        }
                    }
                    print_json(&resp)
                }
                Err(e) => {
                    eprintln!("{e}");
                    std::process::exit(1);
                }
            }
        }
        _ => usage(),
    }
}
