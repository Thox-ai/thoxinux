//! Append-only audit log.
//!
//! Every supervisor and broker decision lands here as one JSON line:
//! who acted, what they asked for, whether it was allowed, and why. The
//! file is only ever appended to by the daemon; `thox-agent audit` reads
//! it back for the user. Sequence numbers are assigned from the existing
//! line count at open time and increase monotonically in-process.

use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use serde::{Deserialize, Serialize};

use crate::util::now_unix;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEntry {
    pub seq: u64,
    pub ts: u64,
    /// Agent name, "thox-agentd", or "user" for CLI-driven actions.
    pub actor: String,
    /// For example "tool.fs.read", "agent.start", "identity.verify".
    pub action: String,
    /// Path, program, agent name, or model name the action concerned.
    pub target: String,
    /// "allow", "deny", "ok", or "error".
    pub decision: String,
    pub detail: String,
}

pub struct AuditLog {
    path: PathBuf,
    next_seq: Mutex<u64>,
}

impl AuditLog {
    pub fn open(path: PathBuf) -> std::io::Result<AuditLog> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let existing = if path.exists() {
            std::fs::read_to_string(&path)
                .map(|t| t.lines().filter(|l| !l.trim().is_empty()).count() as u64)
                .unwrap_or(0)
        } else {
            std::fs::write(&path, b"")?;
            0
        };
        Ok(AuditLog {
            path,
            next_seq: Mutex::new(existing + 1),
        })
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn append(
        &self,
        actor: &str,
        action: &str,
        target: &str,
        decision: &str,
        detail: &str,
    ) -> std::io::Result<AuditEntry> {
        // The lock is held across the file write so lines land in the
        // file in sequence order even with concurrent callers.
        let mut seq = self.next_seq.lock().expect("audit mutex");
        let entry = AuditEntry {
            seq: *seq,
            ts: now_unix(),
            actor: actor.to_string(),
            action: action.to_string(),
            target: target.to_string(),
            decision: decision.to_string(),
            detail: detail.to_string(),
        };
        let line = serde_json::to_string(&entry).expect("audit entry serializes");
        let mut file = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        writeln!(file, "{line}")?;
        file.flush()?;
        *seq += 1;
        Ok(entry)
    }
}

/// Read the last `limit` entries from an audit log file.
pub fn read_entries(path: &Path, limit: usize) -> Vec<AuditEntry> {
    let text = match std::fs::read_to_string(path) {
        Ok(t) => t,
        Err(_) => return Vec::new(),
    };
    let mut entries: Vec<AuditEntry> = text
        .lines()
        .filter_map(|l| serde_json::from_str(l).ok())
        .collect();
    if entries.len() > limit {
        entries.drain(..entries.len() - limit);
    }
    entries
}
