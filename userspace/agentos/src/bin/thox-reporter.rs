//! thox-reporter: the sample first-boot agent.
//!
//! It answers one question, "is this system healthy and what is it
//! running", from real OS state. It does not read /proc or /etc directly
//! for its report: it asks the thox-agentd tool broker for `fs.read` on
//! /proc/uptime and /etc/os-release, which the broker only allows because
//! the reporter manifest grants those exact roots. Every answer is one
//! journal line, so `thox-agent logs reporter` shows a live status feed
//! and `thox-agent audit` shows the broker decisions behind it.
//!
//! Environment:
//!   THOX_AGENT_NAME     agent name to claim at the broker (set by the
//!                       supervisor from the manifest name)
//!   THOX_AGENTD_SOCKET  path to the daemon control socket

use std::path::PathBuf;
use std::time::Duration;

use serde_json::json;

use thox_agentos::client::request;
use thox_agentos::util::base_dir;

fn socket_path() -> PathBuf {
    if let Ok(v) = std::env::var("THOX_AGENTD_SOCKET") {
        if !v.is_empty() {
            return PathBuf::from(v);
        }
    }
    base_dir().join("run").join("agentd.sock")
}

fn broker_read(socket: &PathBuf, agent: &str, path: &str) -> Result<String, String> {
    let resp = request(
        socket,
        json!({"cmd": "tool", "agent": agent, "tool": "fs.read", "params": {"path": path}}),
    )?;
    if resp.get("ok").and_then(|v| v.as_bool()) == Some(true) {
        Ok(resp
            .get("result")
            .and_then(|r| r.get("content"))
            .and_then(|c| c.as_str())
            .unwrap_or("")
            .trim()
            .to_string())
    } else {
        Err(resp
            .get("reason")
            .and_then(|r| r.as_str())
            .unwrap_or("broker denied the read")
            .to_string())
    }
}

fn main() {
    let agent = std::env::var("THOX_AGENT_NAME").unwrap_or_else(|_| "reporter".to_string());
    let socket = socket_path();
    println!("reporter: started as agent {agent}, broker at {}", socket.display());
    loop {
        match (
            broker_read(&socket, &agent, "/proc/uptime"),
            broker_read(&socket, &agent, "/etc/os-release"),
        ) {
            (Ok(uptime), Ok(osrel)) => {
                let up_secs: f64 = uptime
                    .split_whitespace()
                    .next()
                    .and_then(|s| s.parse().ok())
                    .unwrap_or(0.0);
                let pretty = osrel
                    .lines()
                    .find(|l| l.starts_with("PRETTY_NAME="))
                    .map(|l| l.trim_start_matches("PRETTY_NAME=").trim_matches('"').to_string())
                    .unwrap_or_else(|| "unknown OS".to_string());
                println!(
                    "STATUS os=\"{pretty}\" uptime_seconds={:.0} source=broker",
                    up_secs
                );
            }
            (Err(e), _) | (_, Err(e)) => {
                println!("STATUS unavailable: broker read failed: {e}");
            }
        }
        std::thread::sleep(Duration::from_secs(5));
    }
}
