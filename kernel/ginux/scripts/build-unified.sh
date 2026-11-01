#!/usr/bin/env bash
# ThoxInux unified build: verified prepare (module lane) + pinned registry
# anchor by default (edition lane origin) + upstream make build. See
# docs/RECONCILIATION-2026-10-31.md for why both steps exist, and
# docs/RELEASE-BUILD.md for the controlled release procedure.
set -euo pipefail
profile_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$profile_root/upstream.env"
src="${1:?usage: build-unified.sh SRC_DIR OUT_DIR [CA_OUT_DIR] [EXISTING_ROOT_PEM]}"
out="${2:?usage: build-unified.sh SRC_DIR OUT_DIR [CA_OUT_DIR] [EXISTING_ROOT_PEM]}"
ca_out="${3:-$out/ca}"
existing_pem="${4:-}"
edition_scripts="${THOX_EDITION_SCRIPTS:-$profile_root/../../userspace/ginux-edition/scripts}"
# Controlled-build defaults (Wave 5): SOURCE_DATE_EPOCH from the pin unless
# the caller already set it, so the PE TimeDateStamp is reproducible.
if [[ -z "${SOURCE_DATE_EPOCH:-}" ]]; then
    SOURCE_DATE_EPOCH="${GINUX_SOURCE_DATE_EPOCH:?GINUX_SOURCE_DATE_EPOCH missing from upstream.env}"
    echo "build-unified: SOURCE_DATE_EPOCH defaulted from upstream.env pin: $SOURCE_DATE_EPOCH"
else
    echo "build-unified: SOURCE_DATE_EPOCH from caller: $SOURCE_DATE_EPOCH"
fi
export SOURCE_DATE_EPOCH
for cmd in git cargo rustc clang make python3 openssl; do
    command -v "$cmd" >/dev/null || { echo "Missing prerequisite: $cmd" >&2; exit 1; }
done
"$profile_root/scripts/prepare-source.sh" "$src"
[[ "$(cd "$src" && rustc --version | awk '{print $2}')" == "$GINUX_RUST_VERSION" ]] || {
    echo "Install Rust $GINUX_RUST_VERSION and the uefi/none targets." >&2; exit 1; }
if [[ -n "$existing_pem" ]]; then
    install -m 0644 "$existing_pem" "$src/services/network/certs/thoxos-local-root.pem"
    echo "build-unified: registry anchor mode=explicit-arg ($existing_pem)"
elif [[ "${THOX_BUILD_FRESH_CA:-0}" == "1" ]]; then
    echo "build-unified: registry anchor mode=fresh-ca (THOX_BUILD_FRESH_CA=1, development opt-out; bytes will differ per build)"
    bash "$edition_scripts/make-local-ca.sh" "$ca_out" "$src"
else
    pinned_anchor="$profile_root/registry-anchor/thoxos-local-root.pem"
    [[ -f "$pinned_anchor" ]] || { echo "Pinned registry anchor missing: $pinned_anchor" >&2; exit 1; }
    install -m 0644 "$pinned_anchor" "$src/services/network/certs/thoxos-local-root.pem"
    echo "build-unified: registry anchor mode=pinned-default ($pinned_anchor)"
fi
( cd "$src" && cargo fetch --locked && CARGO_NET_OFFLINE=true make build )
mkdir -p "$out"
cp "$src/build/esp/EFI/BOOT/BOOTX64.EFI" "$out/GINUX.EFI"
cp "$src/LICENSE" "$out/GINUX_LICENSE"
cp "$src/NOTICE" "$out/GINUX_NOTICE"
python3 "$profile_root/scripts/write-build-receipt.py" "$src" "$out"
( cd "$out" && sha256sum GINUX.EFI build-receipt.json GINUX_LICENSE GINUX_NOTICE > SHA256SUMS )
echo "Built $out/GINUX.EFI"
