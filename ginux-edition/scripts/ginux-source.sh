#!/usr/bin/env bash
# ThoxOS Ginux Edition: prepare the patched Ginux source tree.
#
# Clones upstream Ginux at the commit pinned in upstream.lock, verifies the
# checkout, and applies patches/*.patch in order. The result lives in
# build/ginux-src (or the directory passed as $1). Re-running is cheap: when the
# tree already sits at the pinned commit with the same patch set applied, the
# script exits without touching it.
#
# Usage: scripts/ginux-source.sh [DEST_DIR]
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest="${1:-$repo_root/build/ginux-src}"

fail() {
    echo "ginux-source: $*" >&2
    exit 1
}

command -v git >/dev/null 2>&1 || fail "git is required"
command -v sha256sum >/dev/null 2>&1 || fail "sha256sum is required"

# shellcheck source=/dev/null
source "$repo_root/upstream.lock"
[[ -n "${GINUX_REPO:-}" ]] || fail "GINUX_REPO missing from upstream.lock"
[[ "${GINUX_COMMIT:-}" =~ ^[0-9a-f]{40}$ ]] || fail "GINUX_COMMIT must be a full 40-character SHA"

shopt -s nullglob
patches=("$repo_root"/patches/*.patch)
shopt -u nullglob
((${#patches[@]} > 0)) || fail "no patches found in $repo_root/patches"

# Identity of the requested tree: pinned commit plus the exact patch bytes.
patch_set_id="$(
    {
        printf '%s\n' "$GINUX_COMMIT"
        cat "${patches[@]}"
    } | sha256sum | awk '{print $1}'
)"
marker="$dest/.thoxos-patch-set"

if [[ -f "$marker" ]] && [[ "$(cat "$marker")" == "$patch_set_id" ]]; then
    echo "ginux-source: $dest already at $GINUX_COMMIT with the current patch set"
    exit 0
fi

if [[ -e "$dest" ]]; then
    # Only replace trees this script created; never delete an arbitrary path.
    [[ -f "$marker" || -d "$dest/.git" ]] || fail "$dest exists and is not a ThoxOS Ginux tree"
    rm -rf "$dest"
fi

mkdir -p "$(dirname "$dest")"
git init -q "$dest"
git -C "$dest" remote add origin "$GINUX_REPO"
# Shallow fetch of the exact pinned commit keeps the download small.
if ! git -C "$dest" fetch -q --depth 1 origin "$GINUX_COMMIT"; then
    fail "could not fetch $GINUX_COMMIT from $GINUX_REPO"
fi
git -C "$dest" checkout -q --detach FETCH_HEAD
actual="$(git -C "$dest" rev-parse HEAD)"
[[ "$actual" == "$GINUX_COMMIT" ]] || fail "checked out $actual, expected $GINUX_COMMIT"

for patch in "${patches[@]}"; do
    if ! git -C "$dest" apply --check "$patch"; then
        fail "patch does not apply cleanly: $(basename "$patch")"
    fi
    git -C "$dest" apply "$patch"
    echo "ginux-source: applied $(basename "$patch")"
done

printf '%s\n' "$patch_set_id" >"$marker"
echo "ginux-source: ready at $dest ($GINUX_COMMIT + ${#patches[@]} ThoxOS patches)"
