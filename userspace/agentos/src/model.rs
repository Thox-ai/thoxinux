//! The user-swappable kernel model slot (spec S10 in Thox-ai/thox-kernel-lab,
//! ruling D11: the user swaps their kernel model; no THOX permission is
//! needed or asked).
//!
//! The slot is a directory in the daemon state dir:
//! - `current.json`   the active model record
//! - `previous.json`  the record before the last swap, for rollback
//!
//! A swap validates the candidate manifest first. When the source is a
//! local file, its SHA-256 must match the declared digest. The write is
//! atomic (write temp file, rename), and the swapped-in record is read
//! back and compared before the swap is reported as done. If validation
//! or read-back fails, the previous current record stays in place.
//! No model weights live in this repository; the slot records name,
//! source, and digest only.

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::util::{now_unix, sha256_hex};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelManifest {
    pub name: String,
    /// Where the model comes from: a local path, a registry reference
    /// such as `hf:Thox-ai/example`, or an `ollama:` reference.
    pub source: String,
    /// SHA-256 of the model artifact, 64 lowercase hex characters.
    pub digest: String,
    #[serde(default)]
    pub format: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActiveModel {
    pub name: String,
    pub source: String,
    pub digest: String,
    #[serde(default)]
    pub format: Option<String>,
    pub installed_at: u64,
}

pub fn slot_dir(state_dir: &Path) -> PathBuf {
    state_dir.join("model-slot")
}

fn current_path(state_dir: &Path) -> PathBuf {
    slot_dir(state_dir).join("current.json")
}

fn previous_path(state_dir: &Path) -> PathBuf {
    slot_dir(state_dir).join("previous.json")
}

pub fn validate_manifest(m: &ModelManifest) -> Result<(), String> {
    if m.name.is_empty() {
        return Err("model name is empty".to_string());
    }
    if m.source.is_empty() {
        return Err("model source is empty".to_string());
    }
    if m.digest.len() != 64 || !m.digest.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err("model digest must be 64 hex characters (SHA-256)".to_string());
    }
    // Local file sources are verified against the declared digest.
    let source_path = Path::new(&m.source);
    if source_path.is_file() {
        let data = std::fs::read(source_path)
            .map_err(|e| format!("cannot read model source {}: {e}", m.source))?;
        let actual = sha256_hex(&data);
        if actual != m.digest.to_lowercase() {
            return Err(format!(
                "digest mismatch for local model source: manifest declares {}, file hashes to {actual}",
                m.digest
            ));
        }
    }
    Ok(())
}

pub fn current(state_dir: &Path) -> Option<ActiveModel> {
    let text = std::fs::read_to_string(current_path(state_dir)).ok()?;
    serde_json::from_str(&text).ok()
}

fn write_atomic(path: &Path, data: &[u8]) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("cannot create {}: {e}", parent.display()))?;
    }
    let tmp = path.with_extension("json.tmp");
    std::fs::write(&tmp, data).map_err(|e| format!("cannot write {}: {e}", tmp.display()))?;
    std::fs::rename(&tmp, path).map_err(|e| format!("cannot rename into {}: {e}", path.display()))?;
    Ok(())
}

/// Swap the active model. On any failure the previously active record is
/// left untouched (or restored), and Err describes the failure.
pub fn swap(state_dir: &Path, manifest: &ModelManifest) -> Result<ActiveModel, String> {
    validate_manifest(manifest)?;
    let dir = slot_dir(state_dir);
    std::fs::create_dir_all(&dir).map_err(|e| format!("cannot create model slot: {e}"))?;
    let prior = current(state_dir);
    if let Some(prior) = &prior {
        let prior_json = serde_json::to_vec_pretty(prior).expect("serialize prior model");
        write_atomic(&previous_path(state_dir), &prior_json)?;
    }
    let active = ActiveModel {
        name: manifest.name.clone(),
        source: manifest.source.clone(),
        digest: manifest.digest.to_lowercase(),
        format: manifest.format.clone(),
        installed_at: now_unix(),
    };
    let json = serde_json::to_vec_pretty(&active).expect("serialize active model");
    write_atomic(&current_path(state_dir), &json)?;
    // Read back and compare; restore the prior record on mismatch.
    match current(state_dir) {
        Some(read_back)
            if read_back.name == active.name
                && read_back.source == active.source
                && read_back.digest == active.digest =>
        {
            Ok(active)
        }
        _ => {
            if let Some(prior) = &prior {
                let prior_json = serde_json::to_vec_pretty(prior).expect("serialize prior model");
                let _ = write_atomic(&current_path(state_dir), &prior_json);
            } else {
                let _ = std::fs::remove_file(current_path(state_dir));
            }
            Err("model swap read-back verification failed; previous model restored".to_string())
        }
    }
}

/// Roll back to the model that was active before the last swap.
pub fn rollback(state_dir: &Path) -> Result<ActiveModel, String> {
    let prev_text = std::fs::read_to_string(previous_path(state_dir))
        .map_err(|e| format!("no previous model recorded: {e}"))?;
    let prev: ActiveModel = serde_json::from_str(&prev_text)
        .map_err(|e| format!("previous model record is corrupt: {e}"))?;
    // The record being replaced becomes the new rollback target.
    if let Some(cur) = current(state_dir) {
        let cur_json = serde_json::to_vec_pretty(&cur).expect("serialize current model");
        write_atomic(&previous_path(state_dir), &cur_json)?;
    }
    let prev_json = serde_json::to_vec_pretty(&prev).expect("serialize previous model");
    write_atomic(&current_path(state_dir), &prev_json)?;
    Ok(prev)
}
