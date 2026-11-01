#!/bin/sh
# Install thox-agentos.
#
# Usage:
#   scripts/install.sh            user install (default)
#   scripts/install.sh --system   system install (needs root for writes)
#
# User install: binaries to ~/.local/bin, user systemd unit to
# ~/.config/systemd/user, then seed the reporter agent.
# System install (Omarchy/Arch desktop track): binaries to
# /usr/local/bin, system unit to /etc/systemd/system, config skeleton
# under /etc/thox-agentos. Seeding on a system install is a first-boot
# job for the OS image, not for this script.
set -eu

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PATH="$HOME/.cargo/bin:$PATH"

cd "$REPO_ROOT"
cargo build --release --offline 2>/dev/null || cargo build --release

if [ "${1:-}" = "--system" ]; then
    install -Dm755 target/release/thox-agentd /usr/local/bin/thox-agentd
    install -Dm755 target/release/thox-agent /usr/local/bin/thox-agent
    install -Dm755 target/release/thox-reporter /usr/local/bin/thox-reporter
    install -Dm644 packaging/systemd/thox-agentd.service \
        /etc/systemd/system/thox-agentd.service
    mkdir -p /etc/thox-agentos/agents /etc/thox-agentos/trust /var/lib/thox-agentos
    echo "installed (system). Next:"
    echo "  systemctl daemon-reload"
    echo "  place issuer public keys in /etc/thox-agentos/trust/<key-id>.pub"
    echo "  place signed agent manifests in /etc/thox-agentos/agents/"
    echo "  systemctl enable --now thox-agentd"
else
    mkdir -p "$HOME/.local/bin" "$HOME/.config/systemd/user"
    install -Dm755 target/release/thox-agentd "$HOME/.local/bin/thox-agentd"
    install -Dm755 target/release/thox-agent "$HOME/.local/bin/thox-agent"
    install -Dm755 target/release/thox-reporter "$HOME/.local/bin/thox-reporter"
    install -Dm644 packaging/systemd/thox-agentd.user.service \
        "$HOME/.config/systemd/user/thox-agentd.service"
    THOX_AGENTOS_HOME=${THOX_AGENTOS_HOME:-"$HOME/.local/share/thox-agentos"} \
        scripts/first-boot-seed.sh "$HOME/.local/bin"
    echo "installed (user). Next:"
    echo "  systemctl --user daemon-reload"
    echo "  systemctl --user enable --now thox-agentd"
    echo "  thox-agent list"
fi
