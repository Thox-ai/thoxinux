//! Integration tests for thox-agentos.
//!
//! Each test uses its own temporary state directory. Coverage maps to the
//! operation's acceptance list: identity refusal, capability denial,
//! audit append, supervisor restart, and model swap rollback.

use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};

use serde_json::json;

use thox_agentos::audit::{read_entries, AuditLog};
use thox_agentos::broker::Broker;
use thox_agentos::identity::{
    generate_signing_key, issue_token, Claims, TrustStore,
};
use thox_agentos::manifest::{Manifest, Permissions, Restart, RestartPolicy};
use thox_agentos::model;
use thox_agentos::supervisor::{AgentState, Supervisor};
use thox_agentos::util::{now_unix, sha256_hex};

fn temp_dir(tag: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!(
        "thox-agentos-test-{}-{}",
        tag,
        std::process::id()
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

fn base_manifest(name: &str, token: String) -> Manifest {
    Manifest {
        name: name.to_string(),
        command: vec!["/bin/true".to_string()],
        env: Default::default(),
        permissions: Permissions::default(),
        restart: Restart::default(),
        identity_token: token,
        autostart: false,
    }
}

#[test]
fn identity_refusal_wrong_key() {
    let issuer_key = generate_signing_key();
    let attacker_key = generate_signing_key();
    let trust = trust_with("thox", &issuer_key);
    // Token signed by a key the trust store does not hold for "thox".
    let token = issue_token(&attacker_key, &claims("worker", "thox"));
    let err = trust.verify(&token, "worker").unwrap_err();
    assert!(format!("{err}").contains("signature"), "got: {err}");
}

#[test]
fn identity_refusal_unsigned_expired_and_mismatched() {
    let key = generate_signing_key();
    let trust = trust_with("thox", &key);
    // Unsigned.
    assert!(trust.verify("", "worker").is_err());
    assert!(trust.verify("   ", "worker").is_err());
    // Expired.
    let mut c = claims("worker", "thox");
    c.expires_at = Some(now_unix().saturating_sub(10));
    let expired = issue_token(&key, &c);
    let err = trust.verify(&expired, "worker").unwrap_err();
    assert!(format!("{err}").contains("expired"), "got: {err}");
    // Subject mismatch.
    let other = issue_token(&key, &claims("someone-else", "thox"));
    let err = trust.verify(&other, "worker").unwrap_err();
    assert!(format!("{err}").contains("someone-else"), "got: {err}");
    // Unknown issuer.
    let unknown = issue_token(&key, &claims("worker", "nobody"));
    let err = trust.verify(&unknown, "worker").unwrap_err();
    assert!(format!("{err}").contains("unknown issuer"), "got: {err}");
    // The good token passes.
    let good = issue_token(&key, &claims("worker", "thox"));
    assert!(trust.verify(&good, "worker").is_ok());
}

#[test]
fn supervisor_refuses_unverifiable_agent() {
    let dir = temp_dir("refuse");
    let audit = Arc::new(AuditLog::open(dir.join("audit.log")).unwrap());
    let sup = Supervisor::new(dir.clone(), audit.clone());
    let key = generate_signing_key();
    let trust = trust_with("thox", &key);
    // Manifest with no token at all.
    let m = base_manifest("ghost", String::new());
    assert!(sup.register(m, &trust).is_err());
    // And it is not registered or running.
    assert!(sup.status("ghost").is_none());
    // The refusal is in the audit log.
    let entries = read_entries(&dir.join("audit.log"), 10);
    assert!(entries
        .iter()
        .any(|e| e.action == "identity.verify" && e.decision == "deny"));
}

#[test]
fn capability_denial_fs_and_exec_and_network() {
    let dir = temp_dir("broker");
    let audit = AuditLog::open(dir.join("audit.log")).unwrap();
    let broker = Broker::new(&audit);
    // A readable file inside the granted root, and one outside it.
    let root = dir.join("granted");
    std::fs::create_dir_all(&root).unwrap();
    std::fs::write(root.join("ok.txt"), "hello").unwrap();
    let outside = dir.join("secret.txt");
    std::fs::write(&outside, "nope").unwrap();
    let perms = Permissions {
        fs_read: vec![root.clone()],
        fs_write: vec![],
        exec_allow: vec![],
        network_egress: false,
    };
    // Allowed read passes.
    let ok = broker.execute("worker", &perms, "fs.read", &json!({"path": root.join("ok.txt")}));
    assert!(ok.allowed, "expected allow, got {}", ok.reason);
    // Read outside the root is denied.
    let denied = broker.execute("worker", &perms, "fs.read", &json!({"path": outside}));
    assert!(!denied.allowed);
    // Exec with an empty allowlist is denied even for /bin/true.
    let denied = broker.execute("worker", &perms, "exec", &json!({"program": "/bin/true"}));
    assert!(!denied.allowed);
    // Network is denied by default.
    let denied = broker.execute(
        "worker",
        &perms,
        "net.http_get",
        &json!({"url": "http://127.0.0.1/"}),
    );
    assert!(!denied.allowed);
    assert!(denied.reason.contains("not granted"), "got: {}", denied.reason);
    // Write outside any fs_write root is denied.
    let denied = broker.execute(
        "worker",
        &perms,
        "fs.write",
        &json!({"path": root.join("x.txt"), "content": "x"}),
    );
    assert!(!denied.allowed);
    // Every decision, allow and deny, is audited.
    let entries = read_entries(&dir.join("audit.log"), 50);
    assert!(entries.iter().any(|e| e.decision == "allow"));
    assert!(entries.iter().filter(|e| e.decision == "deny").count() >= 4);
}

#[test]
fn audit_append_is_monotonic_and_readable() {
    let dir = temp_dir("audit");
    let path = dir.join("audit.log");
    let log = AuditLog::open(path.clone()).unwrap();
    log.append("a", "one", "t", "ok", "first").unwrap();
    log.append("b", "two", "t", "deny", "second").unwrap();
    // Reopening continues the sequence instead of restarting it.
    let log2 = AuditLog::open(path.clone()).unwrap();
    let third = log2.append("c", "three", "t", "ok", "third").unwrap();
    assert_eq!(third.seq, 3);
    let entries = read_entries(&path, 10);
    assert_eq!(entries.len(), 3);
    assert_eq!(entries[0].seq, 1);
    assert_eq!(entries[2].actor, "c");
}

#[test]
fn supervisor_restarts_failing_agent_up_to_max() {
    let dir = temp_dir("restart");
    let audit = Arc::new(AuditLog::open(dir.join("audit.log")).unwrap());
    let sup = Supervisor::new(dir.clone(), audit);
    let key = generate_signing_key();
    let trust = trust_with("thox", &key);
    let token = issue_token(&key, &claims("crasher", "thox"));
    let mut m = base_manifest("crasher", token);
    m.command = vec![
        "/bin/sh".to_string(),
        "-c".to_string(),
        "exit 3".to_string(),
    ];
    m.restart = Restart {
        policy: RestartPolicy::OnFailure,
        max_restarts: 2,
        backoff_ms: 50,
    };
    sup.register(m, &trust).unwrap();
    sup.start("crasher").unwrap();
    // Wait for the monitor to burn through both restarts and give up.
    let deadline = Instant::now() + Duration::from_secs(10);
    loop {
        let st = sup.status("crasher").unwrap();
        if st.restarts >= 2 && st.state == AgentState::Failed {
            assert_eq!(st.last_exit_code, Some(3));
            break;
        }
        assert!(Instant::now() < deadline, "timed out waiting for restarts: {st:?}");
        std::thread::sleep(Duration::from_millis(50));
    }
}

#[test]
fn supervisor_clean_exit_does_not_restart_on_failure_policy() {
    let dir = temp_dir("cleanexit");
    let audit = Arc::new(AuditLog::open(dir.join("audit.log")).unwrap());
    let sup = Supervisor::new(dir.clone(), audit);
    let key = generate_signing_key();
    let trust = trust_with("thox", &key);
    let token = issue_token(&key, &claims("oneshot", "thox"));
    let m = base_manifest("oneshot", token); // /bin/true, exits 0
    sup.register(m, &trust).unwrap();
    sup.start("oneshot").unwrap();
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        let st = sup.status("oneshot").unwrap();
        if st.state == AgentState::Exited {
            assert_eq!(st.restarts, 0);
            assert_eq!(st.last_exit_code, Some(0));
            break;
        }
        assert!(Instant::now() < deadline, "timed out: {st:?}");
        std::thread::sleep(Duration::from_millis(50));
    }
}

#[test]
fn model_swap_and_rollback() {
    let dir = temp_dir("model");
    let weights = dir.join("fake-weights.bin");
    std::fs::write(&weights, b"not real weights, just a digest target").unwrap();
    let digest = sha256_hex(b"not real weights, just a digest target");
    let a = model::ModelManifest {
        name: "kernel-a".to_string(),
        source: weights.to_string_lossy().into_owned(),
        digest: digest.clone(),
        format: Some("gguf".to_string()),
    };
    let active = model::swap(&dir, &a).unwrap();
    assert_eq!(active.name, "kernel-a");
    assert_eq!(model::current(&dir).unwrap().name, "kernel-a");
    // Swap to a second model, then roll back to the first.
    let b = model::ModelManifest {
        name: "kernel-b".to_string(),
        source: "hf:example/kernel-b".to_string(),
        digest: "ab".repeat(32),
        format: None,
    };
    model::swap(&dir, &b).unwrap();
    assert_eq!(model::current(&dir).unwrap().name, "kernel-b");
    let restored = model::rollback(&dir).unwrap();
    assert_eq!(restored.name, "kernel-a");
    assert_eq!(model::current(&dir).unwrap().name, "kernel-a");
}

#[test]
fn model_swap_bad_digest_leaves_current_intact() {
    let dir = temp_dir("modelbad");
    let weights = dir.join("w.bin");
    std::fs::write(&weights, b"payload").unwrap();
    let good = model::ModelManifest {
        name: "good".to_string(),
        source: weights.to_string_lossy().into_owned(),
        digest: sha256_hex(b"payload"),
        format: None,
    };
    model::swap(&dir, &good).unwrap();
    // Candidate declares a digest that does not match its local source.
    let bad = model::ModelManifest {
        name: "bad".to_string(),
        source: weights.to_string_lossy().into_owned(),
        digest: "00".repeat(32),
        format: None,
    };
    let err = model::swap(&dir, &bad).unwrap_err();
    assert!(err.contains("digest mismatch"), "got: {err}");
    // Current model is untouched.
    assert_eq!(model::current(&dir).unwrap().name, "good");
    // Malformed digest is also rejected before any write.
    let malformed = model::ModelManifest {
        name: "bad2".to_string(),
        source: "hf:example/x".to_string(),
        digest: "xyz".to_string(),
        format: None,
    };
    assert!(model::swap(&dir, &malformed).is_err());
    assert_eq!(model::current(&dir).unwrap().name, "good");
}
