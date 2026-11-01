#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
set -euo pipefail
module_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../upstream.env
source "$module_root/upstream.env"
source_dir="${GINUX_SOURCE_DIR:-$module_root/.work/ginux}"
out="${GINUX_ARTIFACT_DIR:-$module_root/artifacts}"
for cmd in git cargo rustc clang make python3; do
    command -v "$cmd" >/dev/null || { echo "Missing prerequisite: $cmd" >&2; exit 1; }
done
"$module_root/scripts/prepare-source.sh" "$source_dir"
[[ "$(cd "$source_dir" && rustc --version | awk '{print $2}')" == "$GINUX_RUST_VERSION" ]] || {
    echo "Install Rust $GINUX_RUST_VERSION and x86_64-unknown-uefi/x86_64-unknown-none targets." >&2
    exit 1
}
(
    cd "$source_dir"
    cargo fetch --locked
    CARGO_NET_OFFLINE=true make build
)
mkdir -p "$out"
cp "$source_dir/build/esp/EFI/BOOT/BOOTX64.EFI" "$out/GINUX.EFI"
cp "$source_dir/LICENSE" "$out/GINUX_LICENSE"
cp "$source_dir/NOTICE" "$out/GINUX_NOTICE"
python3 "$module_root/scripts/write-build-receipt.py" "$source_dir" "$out"
(
    cd "$out"
    sha256sum GINUX.EFI build-receipt.json GINUX_LICENSE GINUX_NOTICE > SHA256SUMS
)
echo "Built $out/GINUX.EFI"
