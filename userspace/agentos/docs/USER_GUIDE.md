# User guide

## What this is

thox-agentos treats agents the way the OS treats system services: they are defined, identity-checked, supervised, permissioned, and logged. Four pieces do the work:

- **thox-agentd**, the supervisor daemon. It loads agent manifests, verifies each agent identity before registering it, starts agents marked `autostart`, restarts them per their policy, and appends each agent's output to a per-agent journal.
- **Identity tokens.** Every agent carries an ed25519-signed token in its manifest. The daemon verifies it offline against a local trust store of issuer public keys. Unsigned, expired, mismatched, or unknown-issuer agents are refused, and the refusal is written to the audit log.
- **The tool broker.** Agents ask the daemon to perform tools (read a file, write a file, run a program, fetch a URL). The broker checks the request against the capability grants in the agent's manifest, executes only what is granted, and audits every decision, allow or deny.
- **The model slot.** A record of which kernel model is active, swappable by the user at any time with rollback. THOX permission is neither needed nor asked (ruling D11, spec S10).

## Agent manifests

One JSON file per agent in the agents directory. Fields:

| Field | Meaning |
|---|---|
| `name` | Slug: lowercase letters, digits, hyphen, underscore |
| `command` | Program and arguments, executed without a shell |
| `env` | Extra environment variables |
| `identity_token` | Signed token from `thox-agent sign` |
| `autostart` | Start when the daemon starts |
| `permissions.fs_read` | Roots the broker may read for this agent |
| `permissions.fs_write` | Roots the broker may write for this agent |
| `permissions.exec_allow` | Programs the broker may run for this agent (exact path, or bare name) |
| `permissions.network_egress` | Default false. Only `net.http_get` is brokered in wave 1 |
| `restart.policy` | `always`, `on-failure`, or `never` |
| `restart.max_restarts` | Restart budget before the agent is marked failed |
| `restart.backoff_ms` | Delay before each restart |

Two enforcement details worth knowing:

- Paths are canonicalized before the root check, so a symlink inside a granted root cannot escape it. A grant for `/etc` alone will not cover `/etc/os-release` on systems where that file is a symlink to `/usr/lib/os-release`; grant `/usr/lib` as well if an agent needs it. The sample reporter manifest does exactly this.
- Broker requests are only honored for agents that are currently running under the supervisor.

## Issuers and signing

```sh
thox-agent keygen --out ./keys
# keys/issuer.key  (private, mode 0600, keep secret)
# keys/issuer.pub  (install as <key-id>.pub in the trust store)

thox-agent sign --key ./keys/issuer.key --issuer thox --agent reporter --expires-in-days 365
# prints the token; paste it into the manifest's identity_token field
```

The daemon reloads the trust store on every connection, so rotating an issuer key on disk takes effect without a restart. Note the current trust boundary honestly: the control socket is a local Unix socket owned by the user or system account running the daemon. Anyone who can write to that socket can issue control commands. Protect it with filesystem permissions the way you would an SSH agent socket. Per-agent broker authentication beyond "the named agent is running" is wave 2 work.

## The audit log

`audit.log` lives in the state directory, one JSON object per line, sequence numbers strictly increasing in file order. Read it with `thox-agent audit` (works without the daemon) or through the daemon's `audit` command. Entries cover identity verification, agent start, stop, exit and restart, every broker decision, and model swaps and rollbacks.

## The model slot

The slot is the `model-slot` directory in the state directory: `current.json` is the active model, `previous.json` is the rollback target. A swap validates the candidate first (name and source present, digest is a SHA-256 hex string, and for a local file source the file hash must match), writes atomically, and reads the record back before reporting success. On any failure the previously active model stays active.

## Day-to-day commands

```sh
thox-agent list
thox-agent status [name]
thox-agent start <name>
thox-agent stop <name>
thox-agent logs <name> [--lines N]
thox-agent reload            # rescan the agents directory (running agents are skipped)
thox-agent audit [--lines N]
thox-agent model show | swap <file> | rollback
```

Global options: `--socket PATH` and `--state-dir DIR`. Defaults derive from `THOX_AGENTOS_HOME` when set, else `~/.local/share/thox-agentos` for state and `~/.config/thox-agentos` for config.

## Layouts

User install: binaries in `~/.local/bin`, state in `~/.local/share/thox-agentos`, manifests in `~/.config/thox-agentos/agents`, trust store in `~/.config/thox-agentos/trust`, socket at `<state>/run/agentd.sock`.

System install (Omarchy/Arch track): binaries in `/usr/local/bin`, state in `/var/lib/thox-agentos`, manifests in `/etc/thox-agentos/agents`, trust store in `/etc/thox-agentos/trust`, socket at `/run/thox-agentos/agentd.sock`. CLI calls against a system instance need `--state-dir /var/lib/thox-agentos --socket /run/thox-agentos/agentd.sock`.
