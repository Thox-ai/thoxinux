# thox-agentos — Verification and Adoption Report

- **Lane:** thox-agentos verification and adoption prep for the ThoxInux monorepo run
- **Date:** 2026-10-31 (America/Chicago)
- **Host:** KnightHub (WSL2, Linux 6.18.33.2-microsoft-standard-WSL2 x86_64), cargo 1.99.1 (5f94df478 2026-08-27), rustc 1.99.1 (58cf8f9c3 2026-10-13), 24 cores, 94 GiB RAM
- **Source (unmodified):** `~/workspace/thoxos-ginux-agentic-os-20261031/thox-agentos/` on Sadie's VM
- **Working copy:** `/mnt/d/thoxinux-build/agentos/` on KnightHub (`/mnt/d` is drvfs/9p backed by `D:\`, 345 GB free at start; WSL root `/` is ext4, 94% full)
- **Copy method:** `rsync -avz --exclude target/` (the source `target/` held 346 MB of stale VM build artifacts; excluded so KnightHub built fresh). Checksum rsync (`rsync -c`) after all work confirms the copy differs from the original in exactly one file: `src/bin/thox-agentd.rs` (fix F1 below). `Cargo.toml` and `Cargo.lock` are byte-identical to the originals (md5 `6cfbdfdf49135de50b58a18fd65d9399` and `d2f14a4c7ce11429cff2cdeff950a520` on both sides); cargo did not rewrite the lockfile.
- **Artifacts in the copy:** `cargo-build.log` (35 lines), `cargo-test.log` (48 lines), `smoke.log` (258 lines, phases 1, 2, 3a, 3b), `smoke.sh`, `smoke2.sh` (the harness scripts that produced the smoke log), this report.

## 1. Build — exact result

`cargo build` (debug profile, from `cargo clean`): **PASS, exit 0.**

- 33 `Compiling` lines: 32 dependency crates + `thox-agentos v0.1.0`.
- Final line as printed: `Finished dev profile [unoptimized + debuginfo] target(s) in 26.35s`.
- Zero warnings, zero errors in the clean build.
- Binaries produced (debug): `thox-agent` 12M, `thox-agentd` 13M, `thox-reporter` 11M, plus `libthox_agentos.rlib`.
- Direct dependencies (6, from `Cargo.toml`): serde 1 (derive), serde_json 1, ed25519-dalek 2, sha2 0.10, hex 0.4, base64 0.22. No build script, no async runtime, synchronous std-only concurrency by design.

## 2. Tests — exact counts

`cargo test` (full workspace; the workspace is a single package): **PASS, exit 0.** The suite was run three times with identical results: pre-fix, post-fix, and on the final clean build. Per-target results exactly as printed:

| Test target | Passed | Failed | Ignored | Measured | Filtered out |
|---|---|---|---|---|---|
| unittests `src/lib.rs` | 0 | 0 | 0 | 0 | 0 |
| unittests `src/bin/thox-agent.rs` | 0 | 0 | 0 | 0 | 0 |
| unittests `src/bin/thox-agentd.rs` | 0 | 0 | 0 | 0 | 0 |
| unittests `src/bin/thox-reporter.rs` | 0 | 0 | 0 | 0 | 0 |
| `tests/integration.rs` | **9** | **0** | **0** | 0 | 0 |
| Doc-tests `thox_agentos` | 0 | 0 | 0 | 0 | 0 |
| **Total** | **9** | **0** | **0** | 0 | 0 |

Integration tests, all `ok`, suite finished in 0.51s as printed: `audit_append_is_monotonic_and_readable`, `capability_denial_fs_and_exec_and_network`, `model_swap_and_rollback`, `model_swap_bad_digest_leaves_current_intact`, `supervisor_refuses_unverifiable_agent`, `identity_refusal_wrong_key`, `identity_refusal_unsigned_expired_and_mismatched`, `supervisor_clean_exit_does_not_restart_on_failure_policy`, `supervisor_restarts_failing_agent_up_to_max`. There are no unit tests in `src/` and no doc-tests; all coverage is the 9 integration tests, matching the README and `docs/QUICKSTART.md` claim of "9 integration tests, all passing" — that claim is verified true.

**No test was deleted, weakened, or edited.** `tests/integration.rs` in the copy is md5-identical to the original (`414be440fcf40ef80f5c538534642dd2`).

## 3. Fixes made in the copy

Exactly one source fix. Nothing else in the source tree was changed.

### F1 — FIXED: daemon autostarted agents before binding its control socket (orphan-on-bind-failure)

- **File:** `src/bin/thox-agentd.rs`, `main()` (only file changed; diff is one moved block plus a 5-line comment).
- **What:** moved the `UnixListener::bind` (and stale-socket removal) to *before* `load_agents(...)`, which is what registers and autostarts agents. Added a comment stating why the order matters.
- **Why / root cause:** in the original order, `main()` loaded manifests, verified identities, and *autostarted agents first*, then bound the socket. If the bind failed, the daemon printed `cannot bind ...` and called `process::exit(1)` with supervised children already running and no cleanup (there is no `Drop` for `Supervisor` and no shutdown path). Proven live in smoke phase 1: with the state dir on drvfs the bind failed with `Operation not permitted (os error 1)`, the daemon exited, and the reporter (PID 220932) was left orphaned, looping every 5 s on `STATUS unavailable: broker read failed: cannot connect to daemon ...` into its journal until killed manually.
- **Verification:** after the fix, smoke phase 3a repeats the identical drvfs setup: daemon prints `cannot bind ...`, exits 1, audit log has zero entries, journals dir is empty, and `ps` shows no thox processes. `cargo test` after the fix: still 9 passed / 0 failed / 0 ignored.

## 4. Remaining failures and findings (not fixed, with root causes)

### F2 — OPEN (genuine bug): daemon shutdown does not stop supervised agents

- **Evidence:** smoke phases 2 and 3b. After `kill <daemon-pid>` (SIGTERM, daemon wait exit 143), the running reporter survived as an orphan in both runs (PIDs 223292 and 229173) and had to be killed manually.
- **Root cause:** `thox-agentd` installs no signal handler and `Supervisor` has no `Drop`/shutdown that kills children; `Supervisor::stop` (child.kill) is only reachable per-agent through the control API while the daemon is alive. Default SIGTERM termination therefore abandons children.
- **Why not fixed here:** the crate is deliberately std-only with no signal API in std; a correct fix needs a dependency decision (e.g. `signal-hook` or `libc` self-pipe) or a design decision to rely on the init system. That is a design call for adoption, not a mechanical fix.
- **Mitigation already present:** under the shipped systemd units, systemd's default `KillMode=control-group` kills the whole cgroup on service stop, so installed operation is covered. Bare-metal/dev runs (`scripts/run-dev.sh`, manual daemon) are not. Recommendation at adoption: add signal-driven graceful stop of all agents, and add an integration test that starts the daemon, SIGTERMs it, and asserts no child survives.

### F3 — OPEN (environment assumption): the dev state dir cannot live on a filesystem without Unix-socket support

- **Evidence:** smoke phase 1. `scripts/run-dev.sh` puts state under `<repo>/target/dev-home/state`, so the socket path is `<repo>/target/dev-home/state/run/agentd.sock`. On KnightHub the checkout is on `/mnt/d` (drvfs, mount type 9p, `path=D:\`), where binding a Unix socket fails: a controlled Python bind test printed `BIND FAIL /mnt/d/.../test.sock: [Errno 1] Operation not permitted` and `BIND OK` for both `/tmp/...` and `$HOME/...` (ext4). The daemon fails the same way; the shipped `packaging/systemd` layouts (`/var/lib/thox-agentos`, `~/.local/share/thox-agentos`) are on native filesystems and unaffected.
- **Root cause:** drvfs/9p does not support Unix domain sockets. This will bite any WSL drvfs, Windows-checkout, or network-mount workflow, not just this host.
- **Workaround verified:** keep the checkout and binaries on `/mnt/d` but put `THOX_AGENTOS_HOME`/`THOX_AGENTOS_CONFIG` on native ext4 (smoke phases 2 and 3b run exactly this way and pass end to end).
- **Recommendation at adoption:** document "state dir must be on a native Linux filesystem" in `docs/QUICKSTART.md`, and consider having `run-dev.sh` place the dev state under `${XDG_RUNTIME_DIR:-/tmp}` instead of `target/dev-home`. With F1 fixed, the failure mode is now a clean exit-1 with nothing started, instead of orphaned agents.

### F4 — MINOR (doc/behavior divergence, not fixed): `THOX_AGENTOS_CONFIG` is honored by the seed script but not by the daemon/CLI defaults

- `scripts/first-boot-seed.sh` resolves config from `THOX_AGENTOS_CONFIG` (default `~/.config/thox-agentos`), but `src/util.rs` `config_dir()` reads `THOX_AGENTOS_HOME` and returns `$THOX_AGENTOS_HOME/config`; it never reads `THOX_AGENTOS_CONFIG`. `run-dev.sh` sets both variables consistently and passes explicit `--agents-dir`/`--trust-dir`, so the shipped flow works. A user who sets only `THOX_AGENTOS_CONFIG`, seeds, and then starts the daemon with default flags will have the daemon look in a different agents/trust location than the seed wrote (agents silently not loaded; if the trust store is empty there, every agent is refused, with the daemon's empty-trust warning as the only hint). Not changed here because aligning it changes path-resolution behavior; adoption should pick one variable contract and make code, scripts, and docs agree.

### F5 — MINOR (build environment): incremental rebuilds on drvfs emit a rustc hard-link fallback warning

- An incremental rebuild on `/mnt/d` printed: `warning: hard linking files in the incremental compilation cache failed. copying files instead.` (attributed to `thox-agentos` bin "thox-agentd", 1 warning). It is a filesystem limitation of drvfs, not a code warning; the from-clean build is warning-free. For heavy iteration in the monorepo, a native-fs `CARGO_TARGET_DIR` avoids the copy fallback and will be faster. No action needed for correctness.

### Non-findings (checked, healthy)

- `Cargo.lock` is complete and consistent: clean build and test ran without modifying the lockfile.
- No compiler warnings from the crate's own code in any run. No test flakiness observed: the two timing-sensitive supervisor tests passed in all three full runs (0.51s suite time each run, as printed).
- Audit timestamps in smoke logs (e.g. `1793486947`) are the host's Unix time as printed by the tools; not adjusted.

## 5. Daemon smoke path — exists, and exercised

The workspace has a real smoke path: `scripts/run-dev.sh` (build, seed via `scripts/first-boot-seed.sh`, run daemon in foreground) plus the second-terminal CLI flow in README/`docs/QUICKSTART.md`. Full output is in `smoke.log`:

- **Phase 1** (state on drvfs, as `run-dev.sh` would lay it out under the `/mnt/d` checkout): seed exit 0; daemon registered and autostarted reporter, then failed to bind (F3) and orphaned it (F1). CLI `audit` (local file read) still worked and showed `identity.verify allow` and `agent.start ok`; all socket commands failed with `No such file or directory (os error 2)`.
- **Phase 2** (identical flow, state/config on native ext4): **full pass.** Daemon: `registered agent reporter`, `autostarted agent reporter`, `listening on .../agentd.sock`. CLI, all exit 0: `list` and `status` show reporter `running` with a live pid and `restarts: 0`; `logs reporter` shows real broker-mediated status lines (`STATUS os="Ubuntu 26.04 LTS" uptime_seconds=16343 source=broker` — the WSL host's `/etc/os-release` and `/proc/uptime`, read through the broker); `audit` shows the allow chain (`identity.verify`, `agent.start`, `daemon.start`, repeated `tool.fs.read` allows for `/proc/uptime` and `/etc/os-release`); `model show` returns `{"model": null, "ok": true}` (empty slot, correct for a fresh state); `reload` returns `skipped agent reporter: already running`; `stop reporter` moves it to `state: "stopped"`, `pid: null`; `start reporter` restarts it and fresh STATUS lines resume. Also verified outside the daemon flow: `thox-agentd --help` exits 0; bare `thox-agent` prints usage and exits 2.
- **Phase 3a:** F1 regression check on drvfs (clean failure, nothing started) — pass.
- **Phase 3b:** happy path re-run on the final clean-built binaries — pass; also re-confirms F2 (reporter orphaned by daemon SIGTERM, then cleaned up manually).

No thox processes were left running at the end of any phase; temporary native-fs smoke state (`~/thox-agentos-smoke`) was removed after capture.

## 6. Public surface (as verified from source and live runs)

**Crates:** one package, `thox-agentos 0.1.0` (edition 2021, `license = "Apache-2.0"`), producing library crate `thox_agentos` and three binaries. It declares its own `[workspace] members = ["."]`.

**Library modules** (`src/lib.rs`): `manifest`, `identity`, `audit`, `broker`, `supervisor`, `model`, `client`, `util`.

- `manifest`: `Manifest`, `Permissions` (`fs_read`, `fs_write`, `exec_allow`, `network_egress`), `Restart`/`RestartPolicy` (`always`, `on-failure`, `never`), `Manifest::load`, `validate`.
- `identity`: ed25519 tokens — `Claims`, `IdentityError`, `TrustStore` (`load_dir`, `insert`, `verify`, `is_empty`), `generate_signing_key`, `issue_token`, hex key codecs.
- `audit`: `AuditLog` (`open`, `append`), `AuditEntry`, `read_entries`; append-only JSONL, sequence assigned under lock.
- `broker`: `Broker::execute`, `ToolOutcome`; tools `fs.read`, `fs.write`, `exec`, `net.http_get` with canonical-path root enforcement, every decision audited.
- `supervisor`: `Supervisor` (`register` gated on identity verification, `start`, `stop`, `status`, `list`, `manifest`, `is_running`, `journal_path`), `AgentState`, `AgentStatus`; per-agent journals under `<state>/journals/`.
- `model`: the kernel model slot — `ModelManifest`, `ActiveModel`, `current`, `swap` (digest-verified for local sources, atomic with read-back), `rollback`, `validate_manifest`.
- `client`: `request(socket, Value)` — one JSON object per line over the Unix socket.
- `util`: `now_unix`, `sha256_hex`, `base_dir`/`config_dir` (see F4), `read_text_limited`, `tail_lines`.

**Binaries and CLI:**

- `thox-agentd [--state-dir DIR] [--agents-dir DIR] [--trust-dir DIR] [--socket PATH]`, `-h|--help`. Defaults derive from `THOX_AGENTOS_HOME` / XDG-style home paths; socket defaults to `<state-dir>/run/agentd.sock`.
- `thox-agent [--socket PATH] [--state-dir DIR] <command>` — control: `list`, `status [name]`, `start <name>`, `stop <name>`, `logs <name> [--lines N]`, `reload`, `model show`, `model swap <model-manifest.json>`, `model rollback`; local: `audit [--lines N]`, `keygen --out DIR`, `sign --key FILE --issuer ID --agent NAME [--expires-in-days N]`.
- `thox-reporter` — sample first-boot agent; env `THOX_AGENT_NAME`, `THOX_AGENTD_SOCKET`; reports OS/uptime every 5 s exclusively through broker `fs.read` calls.
- **Daemon socket protocol** (line-delimited JSON, `{"ok": bool, ...}` responses): `ping`, `list`, `status`, `start`, `stop`, `logs`, `audit`, `reload`, `tool` (`agent`, `tool`, `params`; requires the named agent to be running), `model.show`, `model.swap`, `model.rollback`. Trust store is reloaded per connection (key rotation without restart).
- **Scripts:** `scripts/run-dev.sh`, `scripts/first-boot-seed.sh` (issuer keygen, trust install, signed reporter manifest from `examples/reporter.manifest.template.json`), `scripts/install.sh` (user install; `--system` for the Omarchy/Arch track).
- **Packaging:** `packaging/systemd/thox-agentd.service` (system, `/var/lib/thox-agentos`, `/etc/thox-agentos`) and `thox-agentd.user.service` (user instance).
- **Platform scope:** Unix-only (`std::os::unix` sockets and process handling, tests use `/bin/true` and `/bin/sh`). Linux targets only; it will not build for Windows. That is correct for ThoxInux userspace but should be stated in the monorepo README.

## 7. License and header issues

Blocking for monorepo adoption under the THOX Repository Creation Standard v1.0 — all are missing files, not code problems:

1. **`LICENSE` is missing.** `Cargo.toml` declares Apache-2.0 and the README badge and license section link to `LICENSE`, but no LICENSE file exists in the tree. The link is broken as shipped.
2. **`NOTICE.md` is missing**, though the README license section references it ("See LICENSE and NOTICE.md").
3. **`.agents/HANDOFF.md` is missing.** The `.agents/` directory exists but is empty, while the README badge and its "Agent handoff" section point at `.agents/HANDOFF.md` as the status/evidence record. Broken link, and the standard requires the handoff to exist and be current.
4. **`docs/previews/` is empty.** The standard requires preview artifacts; for a daemon/CLI the honest preview is captured terminal output (the README's inline preview block is a good start, but the directory itself is empty).
5. **No per-file license/SPDX headers.** Every source file opens with `//!` module documentation and no copyright or SPDX line. The crate-level posture is clear (Apache-2.0 in `Cargo.toml` + README), so this is a consistency gap, not an ambiguity — but if the monorepo standard wants SPDX headers, they must be added to all 12 Rust files.
6. Present and correct: `README.md` with badges, governance note, and license section; `docs/USER_GUIDE.md`, `docs/QUICKSTART.md`, `docs/DEVELOPMENT.md`. No `CHANGELOG`, no release cut yet (README states this honestly: "No release has been cut").

## 8. Recommendation: adoption into the monorepo under `userspace/agentos/`

**Adopt. Copy as-is, with the F1 fix and the four missing standard files added. No restructuring needed.**

- The code is verified healthy on its own terms: clean build with zero warnings, 9/9 integration tests green across three runs, and the full daemon/CLI/broker/audit loop proven live, including stop/start and reload semantics. The one code change worth carrying is F1 (already applied and re-verified in this copy; its diff vs the original is exactly one moved block in `src/bin/thox-agentd.rs`).
- **Workspace shape:** the crate is self-rooted (`[workspace]` in its own `Cargo.toml`). Under `userspace/agentos/`, either (a) keep it self-contained and list it in the parent workspace's `exclude` — recommended for the first adoption step, since it preserves the verified build exactly — or (b) absorb it as a parent-workspace member by deleting its `[workspace]` table. Do not leave a nested `[workspace]` inside a parent member path without an exclude; cargo will error.
- **Before or during the move (additive only):** add `LICENSE` (Apache-2.0 full text), `NOTICE.md`, `.agents/HANDOFF.md`, and one captured-output preview under `docs/previews/`; cut the formal v0.1.0 release per the repo standard once it lands in the monorepo.
- **Schedule, do not block on:** F2 (signal-driven shutdown that stops all agents, plus a daemon-level integration test) and F4 (one config-path variable contract). F2 is mitigated under systemd (default control-group kill) in installed operation.
- **Document at adoption:** state dir must be on a native Linux filesystem (F3) — this matters for exactly the WSL/drvfs development setup used across the fleet; and the crate is Linux/Unix-only by design.
- **Do not** fold the sample `thox-reporter` out or rename binaries during adoption; the systemd units, seed script, manifest template, and docs all reference the current names and paths consistently, and every one of those references was exercised in the smoke runs.

## Appendix — evidence map

| Claim in this report | Evidence |
|---|---|
| Build pass, 33 crates, exit 0 | `/mnt/d/thoxinux-build/agentos/cargo-build.log` |
| Tests 9/0/0 per target, exit 0 (x3 runs) | `/mnt/d/thoxinux-build/agentos/cargo-test.log` (final run); identical summaries printed in the two earlier runs |
| Smoke phases 1, 2, 3a, 3b | `/mnt/d/thoxinux-build/agentos/smoke.log` (258 lines), produced by `smoke.sh` / `smoke2.sh` kept alongside it |
| Copy vs original delta = 1 file | checksum rsync (`rsync -avznc`) dry run: only `src/bin/thox-agentd.rs` differs |
| drvfs cannot host Unix sockets | Python bind test, smoke phase 1 section of `smoke.log`: bind FAIL on `/mnt/d` (Errno 1), OK on `/tmp` and `$HOME` |
