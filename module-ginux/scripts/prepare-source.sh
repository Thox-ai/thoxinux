#!/usr/bin/env bash
# shellcheck source-path=SCRIPTDIR
set -euo pipefail
module_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../upstream.env
source "$module_root/upstream.env"
source_dir="${1:-$module_root/.work/ginux}"
if [[ ! -d "$source_dir/.git" ]]; then
    if [[ -e "$source_dir" ]]; then
        echo "Refusing to overwrite existing non-git path: $source_dir" >&2
        exit 1
    fi
    mkdir -p "$source_dir"
    git -C "$source_dir" init -q
    git -C "$source_dir" remote add origin "$GINUX_REPOSITORY"
    git -C "$source_dir" fetch --depth 1 origin "$GINUX_COMMIT"
    git -C "$source_dir" checkout --detach -q FETCH_HEAD
fi
[[ "$(git -C "$source_dir" rev-parse HEAD)" == "$GINUX_COMMIT" ]] || {
    echo "Source commit mismatch; use a fresh dedicated directory." >&2; exit 1;
}
python3 "$module_root/scripts/prepare_source.py" "$source_dir" "$GINUX_COMMIT" "$module_root/patches"
printf '%s\n' "$source_dir"
