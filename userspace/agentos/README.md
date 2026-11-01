# thox-agentos

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-05A451.svg)](LICENSE)
[![Stage: Wave 1, working and tested](https://img.shields.io/badge/stage-wave_1_working-05A451.svg)](.agents/HANDOFF.md)
[![Language: Rust](https://img.shields.io/badge/language-Rust-05A451.svg)](docs/DEVELOPMENT.md)

thox-agentos is the agentic layer of ThoxOS: the software that makes agents first-class citizens of the operating system. One portable Rust codebase serves both ThoxOS tracks, the Omarchy desktop and the Ginux kernel track. It provides an agent supervisor daemon (thox-agentd), signed agent identities verified offline, a capability tool broker with an append-only audit log, the user-swappable kernel model slot, and a sample first-boot agent that proves the whole loop against real OS state.

Your AI. Your Data. Your Rules.™

## Preview

Wave 1 is a daemon and CLI, so the preview is the live loop itself, captured from a development run on 2026-10-31 (full logs in [.agents/HANDOFF.md](.agents/HANDOFF.md)):

```text
$ thox-agent logs reporter --lines 2
STATUS os="Ubuntu 24.04.5 LTS" uptime_seconds=2251 source=broker

$ thox-agent audit --lines 4
#4  actor=reporter action=tool.fs.read target=/proc/uptime decision=allow read 16 bytes
#5  actor=reporter action=tool.fs.read target=/etc/os-release decision=allow read 446 bytes
```

The reporter agent never reads those files directly. It asks the tool broker, the broker checks its manifest grants, and every decision lands in the audit log.

## Quick start

Only commands verified in wave 1 are listed here. Rust stable is the only build prerequisite.

```sh
cargo test                       # 9 integration tests, all passing
scripts/run-dev.sh               # build, seed the reporter agent, run the daemon
```

In a second terminal, from the repo root:

```sh
export THOX_AGENTOS_HOME="$PWD/target/dev-home/state"
target/debug/thox-agent --state-dir "$THOX_AGENTOS_HOME" list
target/debug/thox-agent --state-dir "$THOX_AGENTOS_HOME" logs reporter
target/debug/thox-agent --state-dir "$THOX_AGENTOS_HOME" audit
```

For an installed system, use `scripts/install.sh` (user install) or `scripts/install.sh --system` (Omarchy/Arch desktop track), then run the daemon under systemd. See [docs/QUICKSTART.md](docs/QUICKSTART.md) and [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

## Repository layout

| Path | What lives there |
|---|---|
| `src/lib.rs` plus modules | Core library: manifests, identity, audit, broker, supervisor, model slot, socket client |
| `src/bin/thox-agentd.rs` | The supervisor daemon and control API |
| `src/bin/thox-agent.rs` | The user CLI: control, audit reading, key generation, token signing, model slot |
| `src/bin/thox-reporter.rs` | Sample first-boot agent (system status from real OS state, through the broker) |
| `tests/integration.rs` | Acceptance tests: identity refusal, capability denial, audit, restart, model rollback |
| `examples/` | Agent manifest template used by the seed script |
| `scripts/` | `first-boot-seed.sh`, `install.sh`, `run-dev.sh` |
| `packaging/systemd/` | System and user units for thox-agentd |

## Documentation map

- [docs/USER_GUIDE.md](docs/USER_GUIDE.md): concepts, manifests, capability grants, the model slot, day-to-day operation.
- [docs/QUICKSTART.md](docs/QUICKSTART.md): the five-minute path from clone to a running, audited agent.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md): architecture, protocol, build and test, design decisions and their basis.
- [.agents/HANDOFF.md](.agents/HANDOFF.md): status, evidence, and integration notes for the desktop and kernel teams.

## Releases

No release has been cut. Wave 1 is a local workspace deliverable; publication is a separate founder step and follows the THOX public release boundary (an announcement is not a code publication, and a code publication needs its own explicit order).

## Agent handoff

Agents resuming this work start at [.agents/HANDOFF.md](.agents/HANDOFF.md).

## Governance note

thox-agentos is THOX.ai work product, developed under the ThoxOS agentic OS operation (coordinator: Sadie Weaving, CAO). Public publishing of any kind (repository flips, releases, listings, posts) requires the founder order for that specific item. The kernel model slot follows ruling D11: the user swaps their own kernel model; no THOX permission is needed or asked.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md). Agent identity follows the signed-token pattern proven by the thox-entitlement crate in the THOX handoffs lane thoxos-open; this crate is an independent clean implementation of that pattern for agent subjects.
