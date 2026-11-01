//! Parser robustness tests (Wave 4 item 12).
//!
//! The manifest parser (`manifest::Manifest`, including the capability
//! grants in `Permissions`) and the broker's tool-request handling are
//! fed malformed input: truncated documents, oversized documents,
//! invalid UTF-8, unknown capability strings, duplicate entries, and
//! integer overflow values. Every malformed input must produce an
//! error (or a broker denial), never a panic and never a hang.
//!
//! The fuzz-style coverage is a hand-rolled deterministic corpus plus a
//! seeded mutation sweep, rather than proptest: proptest is not in the
//! local cargo registry cache on the build host, and these tests must
//! run offline and reproducibly. Same seed, same cases, every run.

use std::path::PathBuf;
use std::time::{Duration, Instant};

use serde_json::{json, Value};

use thox_agentos::audit::AuditLog;
use thox_agentos::broker::Broker;
use thox_agentos::identity::{generate_signing_key, issue_token, Claims, TrustStore};
use thox_agentos::manifest::{Manifest, Permissions, MAX_MANIFEST_BYTES};
use thox_agentos::util::now_unix;

fn unique_dir(tag: &str) -> PathBuf {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.subsec_nanos())
        .unwrap_or(0);
    let dir = std::env::temp_dir().join(format!(
        "thox-agentos-parser-{}-{}-{}",
        tag,
        std::process::id(),
        nanos
    ));
    std::fs::create_dir_all(&dir).expect("create temp dir");
    dir
}

/// Parse exactly the way the daemon does: `Manifest::parse_str` is the
/// entry point `Manifest::load` uses after reading the file.
fn parse_and_validate(text: &str) -> Result<Manifest, String> {
    Manifest::parse_str(text)
}

const VALID_MANIFEST: &str = "{\"name\":\"worker\",\"command\":[\"/bin/true\"],\"env\":{\"A\":\"1\"},\"permissions\":{\"fs_read\":[\"/proc\"],\"fs_write\":[],\"exec_allow\":[\"true\"],\"network_egress\":false},\"restart\":{\"policy\":\"on-failure\",\"max_restarts\":3,\"backoff_ms\":1000},\"identity_token\":\"tok\",\"autostart\":false}";

#[test]
fn manifest_parser_accepts_valid_control_manifests() {
    // Every malformed case below is meaningful only if the controls pass.
    parse_and_validate(VALID_MANIFEST).expect("full manifest parses");
    parse_and_validate("{\"name\":\"ok\",\"command\":[\"/bin/true\"]}")
        .expect("minimal manifest parses");
    parse_and_validate(
        "{\"name\":\"r\",\"command\":[\"/bin/true\"],\"permissions\":{\"fs_read\":[\"/proc\",\"/etc\"]}}",
    )
    .expect("distinct capability entries parse");
}

#[test]
fn manifest_parser_rejects_structured_malformed_corpus() {
    // Each entry must be rejected by parse or by validate. A panic in
    // any iteration fails the test outright, which is the point.
    let corpus: Vec<String> = vec![
        // Empty and non-JSON documents.
        String::new(),
        "   ".to_string(),
        "null".to_string(),
        "[]".to_string(),
        "\"worker\"".to_string(),
        "42".to_string(),
        "{".to_string(),
        "{\"name\":\"worker\"".to_string(),
        // Valid JSON but missing required fields.
        "{}".to_string(),
        "{\"name\":\"worker\"}".to_string(),
        "{\"command\":[\"/bin/true\"]}".to_string(),
        // Bad names (validate).
        "{\"name\":\"\",\"command\":[\"/bin/true\"]}".to_string(),
        "{\"name\":\"Worker\",\"command\":[\"/bin/true\"]}".to_string(),
        "{\"name\":\"has space\",\"command\":[\"/bin/true\"]}".to_string(),
        "{\"name\":\"a/b\",\"command\":[\"/bin/true\"]}".to_string(),
        "{\"name\":\"..\",\"command\":[\"/bin/true\"]}".to_string(),
        // Empty or mistyped command.
        "{\"name\":\"w\",\"command\":[]}".to_string(),
        "{\"name\":\"w\",\"command\":[\"\"]}".to_string(),
        "{\"name\":\"w\",\"command\":\"/bin/true\"}".to_string(),
        "{\"name\":\"w\",\"command\":[42]}".to_string(),
        "{\"name\":\"w\",\"command\":[null]}".to_string(),
        // Mistyped scalar fields.
        "{\"name\":123,\"command\":[\"/bin/true\"]}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"autostart\":\"yes\"}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"env\":{\"A\":1}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"identity_token\":123}".to_string(),
        // Integer overflow and out-of-range restart values. u32 max is
        // 4294967295 and u64 max is 18446744073709551615; these exceed
        // them, go negative, or are fractional, and must not wrap.
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"restart\":{\"policy\":\"never\",\"max_restarts\":4294967296}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"restart\":{\"policy\":\"never\",\"max_restarts\":-1}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"restart\":{\"policy\":\"never\",\"max_restarts\":1.5}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"restart\":{\"policy\":\"never\",\"max_restarts\":\"3\"}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"restart\":{\"policy\":\"never\",\"backoff_ms\":18446744073709551616}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"restart\":{\"policy\":\"never\",\"backoff_ms\":-5}}".to_string(),
        // Unknown restart policy strings (the policy is a capability
        // surface: an unrecognized policy must not silently default).
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"restart\":{\"policy\":\"sometimes\"}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"restart\":{\"policy\":\"ON-FAILURE\"}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"restart\":{\"policy\":\"\"}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"restart\":{\"policy\":3}}".to_string(),
        // Unknown capability strings and unknown fields. A misspelled
        // grant must fail loudly instead of being ignored.
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"permissions\":{\"teleport\":true}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"permissions\":{\"fs_read_all\":[]}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"permissions\":{\"network\":true}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"capabilities\":{\"fs_read\":[]}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"restart\":{\"policy\":\"never\",\"jitter_ms\":5}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"surprise\":1}".to_string(),
        // Mistyped capability collections.
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"permissions\":{\"fs_read\":\"/proc\"}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"permissions\":{\"fs_read\":[42]}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"permissions\":{\"exec_allow\":[\"/bin/true\",42]}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"permissions\":{\"network_egress\":\"true\"}}".to_string(),
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"permissions\":[]}".to_string(),
        // Array forms of object nodes (serde would otherwise accept
        // them positionally) and a positional top-level document.
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"restart\":[]}".to_string(),
        "[\"w\",[\"/bin/true\"],{},{},{},\"tok\",false]".to_string(),
        // Duplicate JSON object key for a struct field.
        "{\"name\":\"a\",\"name\":\"b\",\"command\":[\"/bin/true\"]}".to_string(),
        // Trailing garbage after an otherwise valid document.
        format!("{VALID_MANIFEST} garbage"),
        format!("{VALID_MANIFEST}{VALID_MANIFEST}"),
    ];
    for (i, case) in corpus.iter().enumerate() {
        let started = Instant::now();
        let result = parse_and_validate(case);
        assert!(
            started.elapsed() < Duration::from_secs(5),
            "corpus case {i} took too long (hang?): {case:.80}"
        );
        assert!(
            result.is_err(),
            "corpus case {i} was accepted but must be rejected: {case}"
        );
    }
}

#[test]
fn capability_duplicate_entries_are_rejected() {
    // Duplicate grant entries are an authoring error and validate
    // refuses them, one list at a time.
    for field_json in [
        "\"permissions\":{\"fs_read\":[\"/proc\",\"/proc\"]}",
        "\"permissions\":{\"fs_write\":[\"/tmp\",\"/tmp\"]}",
        "\"permissions\":{\"exec_allow\":[\"true\",\"true\"]}",
    ] {
        let text = format!(
            "{{\"name\":\"w\",\"command\":[\"/bin/true\"],{field_json}}}"
        );
        let err = parse_and_validate(&text).unwrap_err();
        assert!(
            err.contains("duplicate"),
            "expected duplicate error for {field_json}, got: {err}"
        );
    }
    // Same values in different lists are fine; only repeats within one
    // list are duplicates.
    parse_and_validate(
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"permissions\":{\"fs_read\":[\"/data\"],\"fs_write\":[\"/data\"]}}",
    )
    .expect("same path in different lists is not a duplicate");
}

#[test]
fn manifest_load_rejects_invalid_utf8_and_oversized_files() {
    let dir = unique_dir("load");

    // Invalid UTF-8 bytes: read_to_string fails, load reports an error.
    let bad_utf8 = dir.join("bad-utf8.json");
    std::fs::write(&bad_utf8, [0xff, 0xfe, 0x00, 0x7b, 0x22]).unwrap();
    assert!(Manifest::load(&bad_utf8).is_err());

    // Invalid UTF-8 embedded in an otherwise JSON-shaped document.
    let mut embedded = b"{\"name\":\"w\xff\",\"command\":[\"/bin/true\"]}".to_vec();
    embedded.extend_from_slice(&[0xc3, 0x28]);
    let bad_embedded = dir.join("bad-embedded.json");
    std::fs::write(&bad_embedded, &embedded).unwrap();
    assert!(Manifest::load(&bad_embedded).is_err());

    // Oversized: a syntactically valid manifest padded past the size
    // cap with a huge env value must be refused by size, before parse.
    let huge_value = "x".repeat((MAX_MANIFEST_BYTES as usize) + 1024);
    let oversized = format!(
        "{{\"name\":\"w\",\"command\":[\"/bin/true\"],\"env\":{{\"PAD\":\"{huge_value}\"}}}}"
    );
    let big_path = dir.join("oversized.json");
    std::fs::write(&big_path, &oversized).unwrap();
    let err = Manifest::load(&big_path).unwrap_err();
    assert!(err.contains("exceeds"), "expected size error, got: {err}");

    // Truncated file on disk.
    let truncated = dir.join("truncated.json");
    std::fs::write(&truncated, &VALID_MANIFEST[..VALID_MANIFEST.len() / 2]).unwrap();
    assert!(Manifest::load(&truncated).is_err());

    // Missing file.
    assert!(Manifest::load(&dir.join("does-not-exist.json")).is_err());

    // Control: the valid manifest loads from disk.
    let good = dir.join("good.json");
    std::fs::write(&good, VALID_MANIFEST).unwrap();
    assert!(Manifest::load(&good).is_ok());
}

#[test]
fn manifest_parser_truncation_sweep_never_accepts_and_never_panics() {
    // Every proper prefix of a valid manifest is incomplete JSON and
    // must be an error. Sweeping all lengths also proves no prefix
    // length panics the parser.
    for len in 0..VALID_MANIFEST.len() {
        let prefix = &VALID_MANIFEST[..len];
        assert!(
            parse_and_validate(prefix).is_err(),
            "prefix of length {len} was accepted: {prefix}"
        );
    }
    assert!(parse_and_validate(VALID_MANIFEST).is_ok());
}

/// Small deterministic PRNG (xorshift64star) so the mutation sweep is
/// identical on every run and every machine.
struct XorShift(u64);

impl XorShift {
    fn next(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.0 = x;
        x.wrapping_mul(0x2545F4914F6CDD1D)
    }
    fn below(&mut self, n: usize) -> usize {
        (self.next() % (n.max(1) as u64)) as usize
    }
}

#[test]
fn manifest_parser_mutation_fuzz_never_panics() {
    let mut rng = XorShift(0x9E3779B97F4A7C15);
    let interesting: &[u8] = b"{}[]\",:0123456789truefalsn\\ \xff\x00\xc3\x28";
    let started = Instant::now();
    for _ in 0..3000 {
        let mut bytes = VALID_MANIFEST.as_bytes().to_vec();
        let mutations = 1 + rng.below(6);
        for _ in 0..mutations {
            match rng.below(3) {
                // Replace one byte.
                0 if !bytes.is_empty() => {
                    let i = rng.below(bytes.len());
                    bytes[i] = interesting[rng.below(interesting.len())];
                }
                // Truncate at a random point.
                1 if !bytes.is_empty() => {
                    let i = rng.below(bytes.len());
                    bytes.truncate(i);
                }
                // Insert one byte.
                _ => {
                    let i = rng.below(bytes.len() + 1);
                    let b = interesting[rng.below(interesting.len())];
                    bytes.insert(i, b);
                }
            }
        }
        // Bytes-level entry point: invalid UTF-8 must error, valid
        // UTF-8 goes through the string parser. An Ok result is only
        // acceptable when validation also passes and the manifest
        // re-serializes and re-parses cleanly.
        match serde_json::from_slice::<Manifest>(&bytes) {
            Ok(m) => {
                if let Ok(()) = m.validate() {
                    let text = serde_json::to_string(&m).expect("re-serialize");
                    parse_and_validate(&text).expect("re-parse of fuzz survivor");
                }
            }
            Err(_) => {}
        }
        if let Ok(text) = std::str::from_utf8(&bytes) {
            let _ = parse_and_validate(text);
        }
    }
    assert!(
        started.elapsed() < Duration::from_secs(30),
        "mutation sweep took too long: {:?}",
        started.elapsed()
    );
}

#[test]
fn manifest_parser_extreme_inputs_complete_without_hang() {
    // Deeply nested JSON: serde_json recursion limit must turn this
    // into an error, not a stack overflow.
    let mut deep = String::from("{\"name\":\"w\",\"command\":[\"/bin/true\"],\"permissions\":");
    deep.push_str(&"[".repeat(5000));
    deep.push_str(&"]".repeat(5000));
    deep.push('}');
    assert!(parse_and_validate(&deep).is_err());
    let deep_value = "[".repeat(10000) + &"]".repeat(10000);
    assert!(serde_json::from_str::<Value>(&deep_value).is_err());

    // A very large flat capability list parses and validates in bounded
    // time (distinct entries, so the duplicate check passes).
    let mut big = String::from(
        "{\"name\":\"w\",\"command\":[\"/bin/true\"],\"permissions\":{\"fs_read\":[",
    );
    for i in 0..50_000 {
        if i > 0 {
            big.push(',');
        }
        big.push_str(&format!("\"/root-{i}\""));
    }
    big.push_str("]}}");
    let started = Instant::now();
    parse_and_validate(&big).expect("large distinct grant list parses");
    assert!(
        started.elapsed() < Duration::from_secs(20),
        "large grant list took too long: {:?}",
        started.elapsed()
    );

    // A giant run of one repeated byte and a giant whitespace document:
    // both invalid, both must fail fast.
    for junk in ["a".repeat(1_000_000), " ".repeat(1_000_000)] {
        let started = Instant::now();
        assert!(parse_and_validate(&junk).is_err());
        assert!(started.elapsed() < Duration::from_secs(5));
    }
}

#[test]
fn broker_malformed_tool_requests_are_denied_never_panic() {
    let dir = unique_dir("broker");
    let audit = AuditLog::open(dir.join("audit.log")).unwrap();
    let broker = Broker::new(&audit);

    // Grants the tests exercise against: one readable/writable root and
    // one allowlisted program.
    let root = dir.join("granted");
    std::fs::create_dir_all(&root).unwrap();
    std::fs::write(root.join("ok.txt"), "hello").unwrap();
    let perms = Permissions {
        fs_read: vec![root.clone()],
        fs_write: vec![root.clone()],
        exec_allow: vec!["/bin/true".to_string()],
        network_egress: false,
    };
    let no_perms = Permissions::default();

    // Control: a well-formed allowed request succeeds, so the denials
    // below are decisions, not a broken broker.
    let ok = broker.execute(
        "worker",
        &perms,
        "fs.read",
        &json!({"path": root.join("ok.txt")}),
    );
    assert!(ok.allowed, "control read should pass: {}", ok.reason);

    // Unknown capability (tool) strings must be denied, including ones
    // that merely look like real tools.
    for tool in [
        "",
        "fs.delete",
        "fs.read.all",
        "FS.READ",
        "exec.sudo",
        "net.http_post",
        "shell",
        "tool.fs.read",
        "fs.read\u{0}",
    ] {
        let out = broker.execute("worker", &perms, tool, &json!({"path": "/etc/passwd"}));
        assert!(!out.allowed, "unknown tool {tool:?} was allowed");
    }

    // Malformed params for real tools, under full grants and under no
    // grants: wrong types, missing fields, NUL bytes, absurd lengths.
    // All must be denied (or fail closed), never panic.
    let huge = "a".repeat(1_000_000);
    let cases: Vec<(Value, &str)> = vec![
        (json!({}), "missing params"),
        (json!({"path": 42}), "numeric path"),
        (json!({"path": null}), "null path"),
        (json!({"path": ["/etc/passwd"]}), "array path"),
        (json!({"path": {"x": 1}}), "object path"),
        (json!({"path": ""}), "empty path"),
        (json!({"path": "\u{0}\u{0}"}), "NUL path"),
        (json!({"path": huge}), "huge path"),
        (json!({"path": "/definitely/not/here.bin"}), "missing file"),
        (json!(["not", "an", "object"]), "array params"),
        (json!("just a string"), "string params"),
        (json!(null), "null params"),
        (json!(12345), "numeric params"),
    ];
    for (params, label) in &cases {
        for tool in ["fs.read", "fs.write", "exec", "net.http_get"] {
            for p in [&perms, &no_perms] {
                let started = Instant::now();
                let out = broker.execute("worker", p, tool, params);
                assert!(
                    started.elapsed() < Duration::from_secs(10),
                    "broker case {label} tool {tool} took too long"
                );
                assert!(
                    !out.allowed,
                    "broker case {label} tool {tool} was allowed with params {params}"
                );
            }
        }
    }

    // exec with a granted program but malformed args: non-string args
    // are dropped by the broker; the remaining (empty) arg list runs
    // /bin/true, which is the documented allowlisted behavior. Assert
    // only that it does not panic and returns promptly.
    let out = broker.execute(
        "worker",
        &perms,
        "exec",
        &json!({"program": "/bin/true", "args": [123, null, {"x": 1}]}),
    );
    assert!(out.allowed, "filtered-args exec of allowlisted /bin/true: {}", out.reason);

    // net.http_get with egress granted but unusable URLs must fail
    // closed without DNS lookups that could hang: connection refused on
    // loopback is immediate.
    let egress = Permissions {
        network_egress: true,
        ..Default::default()
    };
    for url in ["", "https://127.0.0.1/", "http://", "http://127.0.0.1:1/"] {
        let started = Instant::now();
        let out = broker.execute("worker", &egress, "net.http_get", &json!({"url": url}));
        assert!(!out.allowed, "url {url:?} should not be allowed");
        assert!(
            started.elapsed() < Duration::from_secs(12),
            "url {url:?} took too long"
        );
    }
}

#[test]
fn identity_token_parser_malformed_corpus_never_panics() {
    // The supervisor feeds manifest identity_token strings to this
    // parser before anything is spawned; malformed tokens must be
    // errors, never panics. (Bonus coverage alongside the manifest and
    // capability parsers above.)
    let key = generate_signing_key();
    let mut trust = TrustStore::default();
    trust.insert("thox".to_string(), key.verifying_key());
    let good = issue_token(
        &key,
        &Claims {
            agent: "worker".to_string(),
            issuer: "thox".to_string(),
            issued_at: now_unix(),
            expires_at: None,
        },
    );
    assert!(trust.verify(&good, "worker").is_ok(), "control token verifies");

    let malformed: Vec<String> = vec![
        String::new(),
        " ".to_string(),
        ".".to_string(),
        "..".to_string(),
        "abc".to_string(),
        "abc.".to_string(),
        ".abc".to_string(),
        "a.b.c".to_string(),
        "!!!.???".to_string(),
        "AAAA.AAAA".to_string(), // valid base64, not JSON / wrong sig size
        format!("{}.{}", "A".repeat(100_000), "B".repeat(100_000)),
        good.replace('.', ""),
        format!("{good}extra"),
    ];
    for case in &malformed {
        assert!(
            trust.verify(case, "worker").is_err(),
            "malformed token was accepted: {case:.60}"
        );
    }
    // Every prefix of a good token fails verification.
    for len in 0..good.len() {
        assert!(
            trust.verify(&good[..len], "worker").is_err(),
            "token prefix of length {len} verified"
        );
    }
    // Deterministic byte flips in the payload region break the token;
    // flips are asserted to error only in the first half, where every
    // base64 character carries payload bits that change the JSON or
    // the signed bytes. No position may panic.
    let mut rng = XorShift(0xDEADBEEFCAFEF00D);
    let bytes = good.as_bytes().to_vec();
    for _ in 0..500 {
        let mut mutated = bytes.clone();
        let i = rng.below(mutated.len());
        mutated[i] ^= 0x01;
        if let Ok(text) = std::str::from_utf8(&mutated) {
            let result = trust.verify(text, "worker");
            if i < mutated.len() / 2 {
                assert!(result.is_err(), "early token flip at {i} verified");
            }
        }
    }
}
