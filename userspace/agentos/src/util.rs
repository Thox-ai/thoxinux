use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

use sha2::{Digest, Sha256};

/// Current unix time in seconds.
pub fn now_unix() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// Lowercase hex SHA-256 of a byte slice.
pub fn sha256_hex(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hex::encode(hasher.finalize())
}

/// Base directory for all thox-agentos state and config.
///
/// Resolution order: THOX_AGENTOS_HOME, then XDG base dirs, then ~/.config
/// style defaults under the home directory.
pub fn base_dir() -> PathBuf {
    if let Ok(v) = std::env::var("THOX_AGENTOS_HOME") {
        if !v.is_empty() {
            return PathBuf::from(v);
        }
    }
    let home = std::env::var("HOME").unwrap_or_else(|_| "/root".to_string());
    PathBuf::from(home).join(".local").join("share").join("thox-agentos")
}

/// Config directory (manifests and trust store live here in user installs).
pub fn config_dir() -> PathBuf {
    if let Ok(v) = std::env::var("THOX_AGENTOS_HOME") {
        if !v.is_empty() {
            return PathBuf::from(v).join("config");
        }
    }
    let home = std::env::var("HOME").unwrap_or_else(|_| "/root".to_string());
    PathBuf::from(home).join(".config").join("thox-agentos")
}

/// Read up to `max` bytes of a file as a lossy UTF-8 string.
pub fn read_text_limited(path: &std::path::Path, max: usize) -> std::io::Result<String> {
    let data = std::fs::read(path)?;
    let cut = data.len().min(max);
    Ok(String::from_utf8_lossy(&data[..cut]).into_owned())
}

/// Last `n` lines of a text file, oldest first.
pub fn tail_lines(path: &std::path::Path, n: usize) -> Vec<String> {
    match std::fs::read_to_string(path) {
        Ok(text) => {
            let lines: Vec<&str> = text.lines().collect();
            let start = lines.len().saturating_sub(n);
            lines[start..].iter().map(|s| s.to_string()).collect()
        }
        Err(_) => Vec::new(),
    }
}
