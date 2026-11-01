# Development

## Architecture

One Rust package, one library, three binaries. The library holds every mechanism; the binaries are thin shells. Synchronous std-only concurrency (threads, Unix sockets, child processes) is a deliberate choice: no async runtime, so the same binaries run in a full desktop session and in the minimal Ginux guest userspace, and the dependency tree stays small enough to vendor.

| Module | Responsibility |
|---|---|
| `manifest` | Agent definition schema and validation. Deny-by-default permissions. |
| `identity` | ed25519 token issue and verify, trust store loading. |
| `audit` | Append-only JSONL audit log. Sequence assignment and the file write happen under one lock, so file order is sequence order under concurrency. |
| `broker` | Capability checks and tool execution: `fs.read`, `fs.write`, `exec`, `net.http_get`. Canonical-path root enforcement. |
| `supervisor` | Registration gated on identity, spawn, journals, 100 ms monitor tick, restart policy with backoff and budget. |
| `model` | Model slot: validate, atomic swap with read-back, rollback. Local sources are digest-verified. |
| `client` | Line-delimited JSON over the Unix socket. |

## Control protocol

One JSON object per line in each direction on the daemon socket.

Requests: `ping`, `list`, `status` (optional `name`), `start`, `stop`, `logs` (`name`, `lines`), `audit` (`lines`), `reload`, `tool` (`agent`, `tool`, `params`), `model.show`, `model.swap` (`manifest`), `model.rollback`.

Responses: `{"ok": bool, ...}` with `error` or `reason` strings on failure. Tool responses carry `result` and the audit-written `reason`.

## Performance basis

Rust for the daemon per the standing performance-first rule: a supervisor is long-lived, latency-sensitive on process events, and must stay resident on small devices (ThoxAir floor is 2 GB RAM). The wave 1 debug daemon plus one agent idles in a few MB of RSS; release builds are the shipping artifact. The Python reference pattern (thox-entitlement) informed the token design only, not the runtime.

## Build and test

```sh
cargo build
cargo build --release
cargo test
```

`cargo test` runs `tests/integration.rs`: 9 tests covering the acceptance list (identity refusal in three forms plus supervisor refusal, capability denial across fs, exec, and network, audit monotonicity across reopen, restart-to-budget, clean-exit no-restart, model swap plus rollback, bad-digest swap leaving the active model intact).

## Bugs found by our own end-to-end run, fixed in wave 1

1. Key generation read `/dev/urandom` with `fs::read`, which never sees EOF on a character device and allocates without bound. The first full test run was OOM-killed (SIGKILL) because of it. Fixed to `read_exact` on 32 bytes.
2. The sample reporter was denied `/etc/os-release` because that path is a symlink to `/usr/lib/os-release` and the broker canonicalizes before the root check (the enforcement working as designed). Fixed by granting `/usr/lib` in the reporter manifest and documenting the behavior in the user guide.
3. Audit entries could land in the file out of sequence order under concurrent appends. Fixed by holding the sequence lock across the write.
4. `reload` could replace the handle of a running agent and orphan its child. The daemon now skips running agents on reload.

## Known limits (wave 1)

- Control socket trust boundary is filesystem permissions on the socket; there is no per-caller authentication yet.
- Broker `exec` polls for completion with a 15 second timeout; no streaming output.
- `net.http_get` is plain HTTP/1.0, no TLS. Treat it as a capability gate demonstration, not a fetch stack.
- Supervisor state is in-memory; a daemon restart re-registers from manifests (autostart agents come back) but restart budgets reset.
- Model slot validates local file digests; remote sources (`hf:`, `ollama:`) are recorded as declared and verified at fetch time by the fetching component, which is wave 2.
