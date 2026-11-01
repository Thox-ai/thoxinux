# Agent Handoff: userspace/agentos

Current as of 2026-10-31 (ThoxInux consolidation run, D14).

## State

- thox-agentos 0.1.0 adopted into the ThoxInux monorepo at userspace/agentos.
- Verified on KnightHub (WSL2, cargo 1.99.1): cargo build PASS with zero
  warnings; cargo test 9 passed, 0 failed, 0 ignored (integration suite,
  three identical runs); live daemon smoke PASS (supervisor up, reporter
  identity-verified and autostarted, broker-mediated fs.read granted and
  audit-logged, stop/start/reload verified, model slot surface present).
- Fix F1 applied at adoption: thox-agentd binds its control socket BEFORE
  loading and autostarting agents. Previously a bind failure orphaned
  already-started agents. Diff vs the source workspace is exactly that one
  moved block in src/bin/thox-agentd.rs.

## Known defects

- F2 (open): daemon SIGTERM does not stop supervised agents; children are
  orphaned on bare runs. Mitigated under systemd (default control-group
  kill). Fix needs a signal-handling dependency or design decision; add a
  daemon-level integration test with the fix.
- F4 (open, minor): THOX_AGENTOS_CONFIG is honored by the seed script but
  not by daemon and CLI defaults (they use THOX_AGENTOS_HOME). Pick one
  variable contract and align code, scripts, and docs.
- F3 (documented constraint): the state directory must be on a native Linux
  filesystem; drvfs/9p cannot host Unix sockets. The dev script's default
  state path under target/ fails on such mounts with a clean exit-1 (post-F1).

## Next

- Guest integration: run under the ThoxInux QEMU guest and capture the same
  loop there; host-loop evidence exists, guest-loop does not yet.
- Formal v0.1.0 release of the crate inside the monorepo release process.
