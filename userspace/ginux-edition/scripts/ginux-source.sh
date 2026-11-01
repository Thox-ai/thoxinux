#!/usr/bin/env bash
# ThoxOS Ginux Edition: prepare the patched Ginux source tree.
#
# Clones upstream Ginux at the commit pinned in upstream.lock, verifies the
# checkout, and applies patches-legacy-edition/*.patch in order. The result lives in
# build/ginux-src (or the directory passed as $1). Re-running is cheap: when the
# tree already sits at the pinned commit with the exact patch set applied, the
# script exits without touching it. Existing trees are never deleted or reset;
# source drift is an error, so local work survives a failed integrity check.
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
command -v mktemp >/dev/null 2>&1 || fail "mktemp is required"

work=""
index=""
cleanup() {
    [[ -z "$index" ]] || rm -f -- "$index"
    [[ -z "$work" ]] || rm -rf -- "$work"
}
trap cleanup EXIT

# shellcheck source=/dev/null
source "$repo_root/upstream.lock"
[[ -n "${GINUX_REPO:-}" ]] || fail "GINUX_REPO missing from upstream.lock"
[[ "${GINUX_COMMIT:-}" =~ ^[0-9a-f]{40}$ ]] || fail "GINUX_COMMIT must be a full 40-character SHA"

shopt -s nullglob
patches=("$repo_root"/patches-legacy-edition/*.patch)
shopt -u nullglob
((${#patches[@]} > 0)) || fail "no patches found in $repo_root/patches-legacy-edition"

# Identity of the requested tree: pinned commit plus the exact patch bytes.
patch_set_id="$(
    {
        printf '%s\n' "$GINUX_COMMIT"
        cat "${patches[@]}"
    } | sha256sum | awk '{print $1}'
)"
marker="$dest/.thoxos-patch-set"

if [[ -e "$dest" || -L "$dest" ]]; then
    [[ ! -L "$dest" && -d "$dest/.git" && ! -L "$dest/.git" && -f "$marker" && ! -L "$marker" ]] ||
        fail "$dest exists and is not an owned ThoxOS Ginux checkout; nothing was changed"
    [[ "$(cat "$marker")" == "$patch_set_id" ]] ||
        fail "$dest has a different patch set; use a new destination (existing files were preserved)"
    [[ "$(git -C "$dest" rev-parse HEAD)" == "$GINUX_COMMIT" ]] ||
        fail "$dest HEAD differs from the pinned source; existing files were preserved"
    [[ "$(git -C "$dest" remote get-url origin)" == "$GINUX_REPO" ]] ||
        fail "$dest origin differs from upstream.lock; existing files were preserved"

    # Reconstruct the requested patched index separately. Neither the user's
    # index nor working files are changed by this verification.
    index="$(mktemp)"
    GIT_INDEX_FILE="$index" git -C "$dest" read-tree "$GINUX_COMMIT"
    for patch in "${patches[@]}"; do
        GIT_INDEX_FILE="$index" git -C "$dest" apply --cached --check "$patch" ||
            fail "cannot verify patch $(basename "$patch") against pinned source"
        GIT_INDEX_FILE="$index" git -C "$dest" apply --cached "$patch"
    done
    GIT_INDEX_FILE="$index" git -C "$dest" diff --no-ext-diff --quiet -- ||
        fail "$dest contains changed source bytes; use a fresh destination (existing files were preserved)"
    untracked="$(git -C "$dest" ls-files --others --exclude-standard)"
    while IFS= read -r path; do
        # The PKI step intentionally installs this one per-build public root.
        case "$path" in "" | .thoxos-patch-set | services/network/certs/thoxos-local-root.pem) ;;
        *) fail "$dest contains untracked source: $path; existing files were preserved" ;;
        esac
    done <<< "$untracked"
    echo "ginux-source: verified $dest at $GINUX_COMMIT with the exact patch set"
    exit 0
fi

mkdir -p "$(dirname "$dest")"
work="$(mktemp -d "$(dirname "$dest")/.ginux-source.XXXXXXXX")"
git init -q "$work"
git -C "$work" remote add origin "$GINUX_REPO"
# Shallow fetch of the exact pinned commit keeps the download small.
if ! git -C "$work" fetch -q --depth 1 origin "$GINUX_COMMIT"; then
    fail "could not fetch $GINUX_COMMIT from $GINUX_REPO"
fi
git -C "$work" checkout -q --detach FETCH_HEAD
actual="$(git -C "$work" rev-parse HEAD)"
[[ "$actual" == "$GINUX_COMMIT" ]] || fail "checked out $actual, expected $GINUX_COMMIT"

for patch in "${patches[@]}"; do
    if ! git -C "$work" apply --check "$patch"; then
        fail "patch does not apply cleanly: $(basename "$patch")"
    fi
    git -C "$work" apply "$patch"
    echo "ginux-source: applied $(basename "$patch")"
done

printf '%s\n' "$patch_set_id" >"$work/.thoxos-patch-set"
mv -T -- "$work" "$dest"
work=""
echo "ginux-source: ready at $dest ($GINUX_COMMIT + ${#patches[@]} ThoxOS patches)"
