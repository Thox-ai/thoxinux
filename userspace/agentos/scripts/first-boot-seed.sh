#!/bin/sh
# First-boot seed for thox-agentos.
#
# Creates the local issuer key pair (once), installs the issuer public
# key into the trust store, signs an identity token for the sample
# reporter agent, and writes the reporter manifest into the agents
# directory. After this runs, starting thox-agentd brings the reporter
# up automatically and its broker calls start landing in the audit log.
#
# Usage: scripts/first-boot-seed.sh [BIN_DIR]
#   BIN_DIR defaults to ./target/debug relative to the repo root.
# Environment:
#   THOX_AGENTOS_HOME    state base (default ~/.local/share/thox-agentos)
#   THOX_AGENTOS_CONFIG  config base (default ~/.config/thox-agentos)
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BIN_DIR=${1:-"$REPO_ROOT/target/debug"}
STATE_DIR=${THOX_AGENTOS_HOME:-"$HOME/.local/share/thox-agentos"}
CONFIG_DIR=${THOX_AGENTOS_CONFIG:-"$HOME/.config/thox-agentos"}
KEYS_DIR="$CONFIG_DIR/keys"
TRUST_DIR="$CONFIG_DIR/trust"
AGENTS_DIR="$CONFIG_DIR/agents"
SOCKET="$STATE_DIR/run/agentd.sock"

mkdir -p "$KEYS_DIR" "$TRUST_DIR" "$AGENTS_DIR" "$STATE_DIR/run"

if [ ! -f "$KEYS_DIR/issuer.key" ]; then
    "$BIN_DIR/thox-agent" keygen --out "$KEYS_DIR"
    echo "seed: created issuer key pair in $KEYS_DIR"
fi
cp "$KEYS_DIR/issuer.pub" "$TRUST_DIR/thox.pub"
echo "seed: trust store now holds issuer key id 'thox'"

TOKEN=$("$BIN_DIR/thox-agent" sign --key "$KEYS_DIR/issuer.key" \
    --issuer thox --agent reporter --expires-in-days 365)

sed -e "s|__REPORTER_BIN__|$BIN_DIR/thox-reporter|" \
    -e "s|__SOCKET__|$SOCKET|" \
    -e "s|__TOKEN__|$TOKEN|" \
    "$REPO_ROOT/examples/reporter.manifest.template.json" \
    > "$AGENTS_DIR/reporter.json"
echo "seed: wrote agent manifest $AGENTS_DIR/reporter.json"
echo "seed: done. Start the daemon with:"
echo "  $BIN_DIR/thox-agentd --state-dir $STATE_DIR --agents-dir $AGENTS_DIR --trust-dir $TRUST_DIR"
