use std::collections::{BTreeMap, HashSet};
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

/// Maximum accepted manifest file size. Manifests are small hand-written
/// JSON documents; anything larger is refused before parsing so a stray
/// or hostile file cannot make the daemon allocate without bound.
pub const MAX_MANIFEST_BYTES: u64 = 1 << 20;

/// Capability grants for one agent. Everything is deny-by-default: a path or
/// program that is not listed here is refused by the tool broker.
///
/// Unknown fields are rejected at parse time: a misspelled or invented
/// capability key must fail loudly instead of being silently ignored,
/// which would leave the operator believing a grant exists (or does
/// not) when the opposite is true.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
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
#[serde(deny_unknown_fields)]
pub struct Restart {
    pub policy: RestartPolicy,
    #[serde(default = "default_max_restarts")]
    pub max_restarts: u32,
    #[serde(default = "default_backoff_ms")]
    pub backoff_ms: u64,
}

/// Err unless `value` is a JSON object (used by `Manifest::parse_str`).
fn require_json_object(value: &serde_json::Value, what: &str) -> Result<(), String> {
    if value.is_object() {
        Ok(())
    } else {
        Err(format!("{what} must be a JSON object"))
    }
}

/// Err when `values` contains the same entry twice.
fn reject_duplicates<I>(field: &str, values: I) -> Result<(), String>
where
    I: Iterator<Item = String>,
{
    let mut seen: HashSet<String> = HashSet::new();
    for v in values {
        if !seen.insert(v.clone()) {
            return Err(format!("duplicate entry in {field}: {v:?}"));
        }
    }
    Ok(())
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
/// Unknown top-level fields are rejected, matching `Permissions`.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
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
        // Refuse oversized manifests before reading them into memory.
        if let Ok(meta) = std::fs::metadata(path) {
            if meta.len() > MAX_MANIFEST_BYTES {
                return Err(format!(
                    "manifest {} exceeds the {} byte limit ({} bytes)",
                    path.display(),
                    MAX_MANIFEST_BYTES,
                    meta.len()
                ));
            }
        }
        let text = std::fs::read_to_string(path)
            .map_err(|e| format!("cannot read manifest {}: {e}", path.display()))?;
        Manifest::parse_str(&text)
            .map_err(|e| format!("cannot parse manifest {}: {e}", path.display()))
    }

    /// Parse and validate a manifest from JSON text.
    ///
    /// Two passes, and a document must survive both. The structural
    /// pass requires the manifest, `permissions`, and `restart` nodes
    /// to be JSON objects: serde's derived struct deserializer would
    /// otherwise also accept a JSON array positionally, so a document
    /// like `"permissions": []` silently became an all-defaults grant
    /// set. The typed pass then applies the struct rules (unknown
    /// fields refused, duplicate object keys refused, integer ranges
    /// enforced by the field types) and `validate` runs last.
    pub fn parse_str(text: &str) -> Result<Manifest, String> {
        let value: serde_json::Value =
            serde_json::from_str(text).map_err(|e| e.to_string())?;
        require_json_object(&value, "manifest")?;
        if let Some(p) = value.get("permissions") {
            require_json_object(p, "permissions")?;
        }
        if let Some(r) = value.get("restart") {
            require_json_object(r, "restart")?;
        }
        let m: Manifest = serde_json::from_str(text).map_err(|e| e.to_string())?;
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
        // Duplicate capability entries are refused: a repeated root or
        // program is always an authoring mistake, and accepting it
        // silently would hide which grants the operator actually made.
        reject_duplicates("permissions.fs_read", self.permissions.fs_read.iter().map(|p| p.to_string_lossy().into_owned()))?;
        reject_duplicates("permissions.fs_write", self.permissions.fs_write.iter().map(|p| p.to_string_lossy().into_owned()))?;
        reject_duplicates("permissions.exec_allow", self.permissions.exec_allow.iter().cloned())?;
        Ok(())
    }
}
