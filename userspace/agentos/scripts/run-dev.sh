#!/bin/sh
# Development run mode: no systemd, no install. Builds debug binaries,
# seeds the reporter agent into a throwaway home under ./target/dev-home,
# and starts thox-agentd in the foreground. Use thox-agent against the
# printed socket from another terminal. This is also the run mode to use
# inside the Ginux guest, where systemd may not be present.
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PATH="$HOME/.cargo/bin:$PATH"
cd "$REPO_ROOT"

cargo build --offline 2>/dev/null || cargo build

export THOX_AGENTOS_HOME="$REPO_ROOT/target/dev-home/state"
export THOX_AGENTOS_CONFIG="$REPO_ROOT/target/dev-home/config"
scripts/first-boot-seed.sh "$REPO_ROOT/target/debug"

echo "run-dev: socket at $THOX_AGENTOS_HOME/run/agentd.sock"
echo "run-dev: try: target/debug/thox-agent --state-dir $THOX_AGENTOS_HOME list"
exec "$REPO_ROOT/target/debug/thox-agentd" \
    --state-dir "$THOX_AGENTOS_HOME" \
    --agents-dir "$THOX_AGENTOS_CONFIG/agents" \
    --trust-dir "$THOX_AGENTOS_CONFIG/trust"
