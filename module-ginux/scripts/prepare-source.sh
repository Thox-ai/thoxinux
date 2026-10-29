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
if git -C "$source_dir" apply --check "$module_root/patches/thox-banner.patch" 2>/dev/null; then
    [[ -z "$(git -C "$source_dir" status --porcelain --untracked-files=no)" ]] || {
        echo "Refusing to modify dirty source." >&2; exit 1;
    }
    git -C "$source_dir" apply "$module_root/patches/thox-banner.patch"
elif ! git -C "$source_dir" apply --reverse --check "$module_root/patches/thox-banner.patch" 2>/dev/null; then
    echo "Source does not match THOX banner patch." >&2
    exit 1
fi
# A matching HEAD alone does not rule out unrelated local edits. The generated
# boot catalog is rebuilt by make manifest; all other tracked source must match
# the pin except the exact four-line banner insertion.
python3 - "$source_dir" <<'PY'
import pathlib
import subprocess
import sys
root = pathlib.Path(sys.argv[1])
path = "control-plane/runtime/src/main.rs"
original = subprocess.check_output(["git", "-C", str(root), "show", f"HEAD:{path}"])
anchor = b'    write(console, b"\\r\\nGinux controller v0 (ring 3)\\r\\n");'
banner = (b'    // THOX.ai LLC modification: identify this research build; retain upstream ABI and prompt.\n'
          b'    write(console, b"\\r\\nThoxOS Ginux Research Edition\\r\\n");\n'
          b'    write(console, b"Engineering preview: QEMU guest; physical hardware unvalidated.\\r\\n");\n'
          b'    write(console, b"Based on Ginux by Gregory M. Kurtzer and contributors.\\r\\n");\n')
if original.count(anchor) != 1 or (root / path).read_bytes() != original.replace(anchor, banner + anchor):
    raise SystemExit("Controller bytes differ from the reviewed THOX banner modification.")
changed = subprocess.check_output(["git", "-C", str(root), "diff", "HEAD", "--name-only"], text=True).splitlines()
if set(changed) - {path, "boot/efi/src/generated_boot.rs"}:
    raise SystemExit("Refusing unrelated tracked source edits: " + ", ".join(changed))
if subprocess.check_output(["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"], text=True).strip():
    raise SystemExit("Refusing untracked source files in the dedicated build checkout.")
PY
printf '%s\n' "$source_dir"
