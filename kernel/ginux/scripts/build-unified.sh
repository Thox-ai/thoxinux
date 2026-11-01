#!/usr/bin/env bash
# ThoxInux unified build: verified prepare (module lane) + per-build local
# registry anchor (edition lane) + upstream make build. See
# docs/RECONCILIATION-2026-10-31.md for why both steps exist.
set -euo pipefail
profile_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$profile_root/upstream.env"
src="${1:?usage: build-unified.sh SRC_DIR OUT_DIR [CA_OUT_DIR] [EXISTING_ROOT_PEM]}"
out="${2:?usage: build-unified.sh SRC_DIR OUT_DIR [CA_OUT_DIR] [EXISTING_ROOT_PEM]}"
ca_out="${3:-$out/ca}"
existing_pem="${4:-}"
edition_scripts="${THOX_EDITION_SCRIPTS:-$profile_root/../../userspace/ginux-edition/scripts}"
for cmd in git cargo rustc clang make python3 openssl; do
    command -v "$cmd" >/dev/null || { echo "Missing prerequisite: $cmd" >&2; exit 1; }
done
"$profile_root/scripts/prepare-source.sh" "$src"
[[ "$(cd "$src" && rustc --version | awk '{print $2}')" == "$GINUX_RUST_VERSION" ]] || {
    echo "Install Rust $GINUX_RUST_VERSION and the uefi/none targets." >&2; exit 1; }
if [[ -n "$existing_pem" ]]; then
    install -m 0644 "$existing_pem" "$src/services/network/certs/thoxos-local-root.pem"
    echo "Installed existing registry anchor: $existing_pem"
else
    bash "$edition_scripts/make-local-ca.sh" "$ca_out" "$src"
fi
( cd "$src" && cargo fetch --locked && CARGO_NET_OFFLINE=true make build )
mkdir -p "$out"
cp "$src/build/esp/EFI/BOOT/BOOTX64.EFI" "$out/GINUX.EFI"
cp "$src/LICENSE" "$out/GINUX_LICENSE"
cp "$src/NOTICE" "$out/GINUX_NOTICE"
python3 "$profile_root/scripts/write-build-receipt.py" "$src" "$out"
( cd "$out" && sha256sum GINUX.EFI build-receipt.json GINUX_LICENSE GINUX_NOTICE > SHA256SUMS )
echo "Built $out/GINUX.EFI"
