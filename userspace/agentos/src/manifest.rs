use std::collections::BTreeMap;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

/// Capability grants for one agent. Everything is deny-by-default: a path or
/// program that is not listed here is refused by the tool broker.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Permissions {
    /// Directory or file roots the agent may read through the broker.
    #[serde(default)]
    pub fs_read: Vec<PathBuf>,
    /// Directory roots the agent may write through the broker.
    #[serde(default)]
    pub fs_write: Vec<PathBuf>,
    /// Programs the agent may execute through the broker. Matched against
    /// the program path exactly as requested, or against its file name.
    #[serde(default)]
    pub exec_allow: Vec<String>,
    /// Network egress is off unless this is explicitly true.
    #[serde(default)]
    pub network_egress: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum RestartPolicy {
    Always,
    OnFailure,
    Never,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Restart {
    pub policy: RestartPolicy,
    #[serde(default = "default_max_restarts")]
    pub max_restarts: u32,
    #[serde(default = "default_backoff_ms")]
    pub backoff_ms: u64,
}

fn default_max_restarts() -> u32 {
    3
}
fn default_backoff_ms() -> u64 {
    1000
}

impl Default for Restart {
    fn default() -> Self {
        Restart {
            policy: RestartPolicy::OnFailure,
            max_restarts: default_max_restarts(),
            backoff_ms: default_backoff_ms(),
        }
    }
}

/// An agent definition. One JSON file per agent in the agents directory.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Manifest {
    /// Unique slug: lowercase letters, digits, hyphen, underscore.
    pub name: String,
    /// Command line: program followed by arguments. No shell is involved.
    pub command: Vec<String>,
    #[serde(default)]
    pub env: BTreeMap<String, String>,
    #[serde(default)]
    pub permissions: Permissions,
    #[serde(default)]
    pub restart: Restart,
    /// Signed identity token (see `identity`). Empty means unsigned, and an
    /// unsigned agent is refused by the supervisor.
    #[serde(default)]
    pub identity_token: String,
    /// Start automatically when the daemon starts.
    #[serde(default)]
    pub autostart: bool,
}

impl Manifest {
    pub fn load(path: &std::path::Path) -> Result<Manifest, String> {
        let text = std::fs::read_to_string(path)
            .map_err(|e| format!("cannot read manifest {}: {e}", path.display()))?;
        let m: Manifest = serde_json::from_str(&text)
            .map_err(|e| format!("cannot parse manifest {}: {e}", path.display()))?;
        m.validate()?;
        Ok(m)
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.name.is_empty()
            || !self
                .name
                .chars()
                .all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '-' || c == '_')
        {
            return Err(format!("invalid agent name: {:?}", self.name));
        }
        if self.command.is_empty() || self.command[0].is_empty() {
            return Err(format!("agent {} has an empty command", self.name));
        }
        Ok(())
    }
}
