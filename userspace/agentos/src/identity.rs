//! Signed agent identity tokens, verified offline with ed25519.
//!
//! The pattern follows the thox-entitlement crate (THOX handoffs lane
//! thoxos-open): a token is a signed payload, verification needs only the
//! issuer public key, and no network is involved. Here the subject is an
//! agent, not a paid entitlement: the supervisor refuses to start any agent
//! whose token does not verify against the local trust store, whose subject
//! does not match the manifest name, or whose token has expired.
//!
//! Token format: base64(payload_json) "." base64(signature), where the
//! signature is ed25519 over the payload JSON bytes.

use std::collections::HashMap;
use std::path::Path;

use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};

use crate::util::now_unix;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    /// Agent name the token was issued to.
    pub agent: String,
    /// Key id of the issuer; selects the public key in the trust store.
    pub issuer: String,
    pub issued_at: u64,
    /// Unix seconds. None means the token does not expire.
    #[serde(default)]
    pub expires_at: Option<u64>,
}

#[derive(Debug)]
pub enum IdentityError {
    Malformed(String),
    UnknownIssuer(String),
    BadSignature,
    SubjectMismatch { token_agent: String, manifest_agent: String },
    Expired { expires_at: u64 },
    Unsigned,
}

impl std::fmt::Display for IdentityError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            IdentityError::Malformed(m) => write!(f, "malformed identity token: {m}"),
            IdentityError::UnknownIssuer(k) => write!(f, "unknown issuer key id: {k}"),
            IdentityError::BadSignature => write!(f, "identity token signature does not verify"),
            IdentityError::SubjectMismatch { token_agent, manifest_agent } => write!(
                f,
                "identity token is for agent {token_agent:?}, manifest is {manifest_agent:?}"
            ),
            IdentityError::Expired { expires_at } => {
                write!(f, "identity token expired at {expires_at}")
            }
            IdentityError::Unsigned => write!(f, "agent manifest carries no identity token"),
        }
    }
}

impl std::error::Error for IdentityError {}

/// Generate a new issuer key pair. The seed comes from /dev/urandom; if that
/// is unavailable (minimal guests), it falls back to a time and pid mix,
/// which is documented as weaker and only a last resort.
pub fn generate_signing_key() -> SigningKey {
    let mut seed = [0u8; 32];
    // Read exactly 32 bytes: /dev/urandom never returns EOF, so a plain
    // fs::read would allocate without bound.
    let urandom_ok = std::fs::File::open("/dev/urandom")
        .and_then(|mut f| {
            use std::io::Read;
            f.read_exact(&mut seed)
        })
        .is_ok();
    match urandom_ok {
        true => {}
        _ => {
            let mut state = (now_unix() ^ (std::process::id() as u64) << 32).wrapping_add(0x9E3779B97F4A7C15);
            for b in seed.iter_mut() {
                // xorshift64star, fallback entropy only.
                state ^= state >> 12;
                state ^= state << 25;
                state ^= state >> 27;
                *b = (state.wrapping_mul(0x2545F4914F6CDD1D) >> 56) as u8;
            }
        }
    }
    SigningKey::from_bytes(&seed)
}

pub fn signing_key_to_hex(key: &SigningKey) -> String {
    hex::encode(key.to_bytes())
}

pub fn verifying_key_to_hex(key: &VerifyingKey) -> String {
    hex::encode(key.to_bytes())
}

pub fn signing_key_from_hex(text: &str) -> Result<SigningKey, String> {
    let bytes = hex::decode(text.trim()).map_err(|e| format!("bad key hex: {e}"))?;
    let arr: [u8; 32] = bytes
        .try_into()
        .map_err(|_| "signing key must be 32 bytes".to_string())?;
    Ok(SigningKey::from_bytes(&arr))
}

pub fn verifying_key_from_hex(text: &str) -> Result<VerifyingKey, String> {
    let bytes = hex::decode(text.trim()).map_err(|e| format!("bad key hex: {e}"))?;
    let arr: [u8; 32] = bytes
        .try_into()
        .map_err(|_| "verifying key must be 32 bytes".to_string())?;
    VerifyingKey::from_bytes(&arr).map_err(|e| format!("bad verifying key: {e}"))
}

/// Issue a token for an agent.
pub fn issue_token(key: &SigningKey, claims: &Claims) -> String {
    let payload = serde_json::to_vec(claims).expect("claims serialize");
    let signature = key.sign(&payload);
    format!(
        "{}.{}",
        URL_SAFE_NO_PAD.encode(&payload),
        URL_SAFE_NO_PAD.encode(signature.to_bytes())
    )
}

/// A directory of trusted issuer public keys. Each file is named
/// `<key_id>.pub` and contains the hex-encoded ed25519 public key.
#[derive(Debug, Default)]
pub struct TrustStore {
    keys: HashMap<String, VerifyingKey>,
}

impl TrustStore {
    pub fn load_dir(dir: &Path) -> Result<TrustStore, String> {
        let mut store = TrustStore::default();
        if !dir.exists() {
            return Ok(store);
        }
        let entries = std::fs::read_dir(dir)
            .map_err(|e| format!("cannot read trust dir {}: {e}", dir.display()))?;
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) == Some("pub") {
                let key_id = path
                    .file_stem()
                    .and_then(|s| s.to_str())
                    .unwrap_or_default()
                    .to_string();
                let text = std::fs::read_to_string(&path)
                    .map_err(|e| format!("cannot read {}: {e}", path.display()))?;
                let key = verifying_key_from_hex(&text)?;
                store.keys.insert(key_id, key);
            }
        }
        Ok(store)
    }

    pub fn insert(&mut self, key_id: String, key: VerifyingKey) {
        self.keys.insert(key_id, key);
    }

    pub fn is_empty(&self) -> bool {
        self.keys.is_empty()
    }

    /// Verify a token for the agent named by a manifest.
    pub fn verify(&self, token: &str, manifest_agent: &str) -> Result<Claims, IdentityError> {
        if token.trim().is_empty() {
            return Err(IdentityError::Unsigned);
        }
        let mut parts = token.splitn(2, '.');
        let payload_b64 = parts.next().unwrap_or("");
        let sig_b64 = parts.next().ok_or_else(|| {
            IdentityError::Malformed("expected payload.signature".to_string())
        })?;
        let payload = URL_SAFE_NO_PAD
            .decode(payload_b64)
            .map_err(|e| IdentityError::Malformed(format!("payload base64: {e}")))?;
        let sig_bytes = URL_SAFE_NO_PAD
            .decode(sig_b64)
            .map_err(|e| IdentityError::Malformed(format!("signature base64: {e}")))?;
        let claims: Claims = serde_json::from_slice(&payload)
            .map_err(|e| IdentityError::Malformed(format!("payload json: {e}")))?;
        let key = self
            .keys
            .get(&claims.issuer)
            .ok_or_else(|| IdentityError::UnknownIssuer(claims.issuer.clone()))?;
        let sig_arr: [u8; 64] = sig_bytes
            .try_into()
            .map_err(|_| IdentityError::Malformed("signature must be 64 bytes".to_string()))?;
        let signature = Signature::from_bytes(&sig_arr);
        key.verify(&payload, &signature)
            .map_err(|_| IdentityError::BadSignature)?;
        if claims.agent != manifest_agent {
            return Err(IdentityError::SubjectMismatch {
                token_agent: claims.agent.clone(),
                manifest_agent: manifest_agent.to_string(),
            });
        }
        if let Some(exp) = claims.expires_at {
            if now_unix() > exp {
                return Err(IdentityError::Expired { expires_at: exp });
            }
        }
        Ok(claims)
    }
}
