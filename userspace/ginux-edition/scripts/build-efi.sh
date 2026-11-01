#!/usr/bin/env bash
# ThoxOS Ginux Edition: build GINUX.EFI from a patched source tree.
#
# Requires the toolchain declared by upstream rust-toolchain.toml (rustup
# installs it on first use), clang, and the x86_64-unknown-none Rust target.
# The local registry root must already exist in the tree (make-local-ca.sh).
#
# Usage: scripts/build-efi.sh GINUX_SRC_DIR OUT_DIR
# Outputs: OUT_DIR/GINUX.EFI and OUT_DIR/GINUX.EFI.sha256
set -euo pipefail

fail() {
    echo "build-efi: $*" >&2
    exit 1
}

[[ $# -eq 2 ]] || fail "usage: $0 GINUX_SRC_DIR OUT_DIR"
src="$1"
out="$2"
[[ -f "$src/Makefile" && -f "$src/rust-toolchain.toml" ]] || fail "$src is not a Ginux source tree"
[[ -s "$src/services/network/certs/thoxos-local-root.pem" ]] ||
    fail "missing local registry root; run scripts/make-local-ca.sh first"
command -v cargo >/dev/null 2>&1 || fail "cargo is required (install rustup)"
command -v clang >/dev/null 2>&1 || fail "clang is required"

# x86_64-unknown-none hosts the controller and service runtimes; upstream's
# toolchain file only lists the UEFI target.
if command -v rustup >/dev/null 2>&1; then
    (cd "$src" && rustup target add x86_64-unknown-none >/dev/null)
fi

make -C "$src" build PROFILE=release
efi="$src/build/esp/EFI/BOOT/BOOTX64.EFI"
[[ -s "$efi" ]] || fail "build finished without $efi"

mkdir -p "$out"
install -m 0644 "$efi" "$out/GINUX.EFI"
(cd "$out" && sha256sum GINUX.EFI >GINUX.EFI.sha256)
echo "build-efi: $(cat "$out/GINUX.EFI.sha256")"
