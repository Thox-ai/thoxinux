#!/usr/bin/env bash
# Copyright (c) 2026 THOX.ai LLC. Licensed under the Apache License, Version 2.0.
#
# local-ci.sh: continuous integration for ThoxOS Ginux Edition on your own
# machine, with no GitHub Actions minutes. It runs the checks the retired
# Actions workflow ran and, with --report, records the result on GitHub as a
# commit status (context "thox/local-ci"), so pull requests still show a
# green or red check.
#
# Usage: scripts/local-ci.sh [--full] [--report] [--dry-run]
#   (default)  make test: pytest, bash -n and shellcheck (about 10 s)
#   --full     also the full desktop theme generation test in a Debian 13
#              container with the real fonts and icon theme (needs Docker)
#   --report   post the result as a commit status on HEAD (needs gh signed in
#              with access to the repository; refuses a dirty tree, because
#              the status must describe exactly the committed files)
#   --dry-run  print the steps and the status call, run nothing
#
# Results: build/local-ci/<sha>.log and build/local-ci/<sha>.json.
# Exit status: 0 when every check passed, 1 when one failed, 2 on bad usage.
set -euo pipefail

module_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
context="thox/local-ci"
full=0
report=0
dry_run=0

usage() { sed -n '10,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
fail() { echo "local-ci: $*" >&2; exit 1; }

for arg in "$@"; do
    case "$arg" in
    --full) full=1 ;;
    --report) report=1 ;;
    --dry-run) dry_run=1 ;;
    -h | --help) usage; exit 0 ;;
    *) echo "local-ci: unknown option $arg" >&2; usage >&2; exit 2 ;;
    esac
done

cd "$module_root"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "not inside a git checkout"
sha="$(git rev-parse HEAD)"
short="${sha:0:12}"

# owner/repo from the origin URL (https or ssh form).
repo_slug() {
    local url
    url="$(git remote get-url origin 2>/dev/null)" || return 1
    url="${url%.git}"
    url="${url#git@github.com:}"
    url="${url#https://github.com/}"
    url="${url#http://github.com/}"
    url="${url##*github.com/}"
    [[ "$url" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]] || return 1
    printf '%s\n' "$url"
}

if [[ "$report" -eq 1 ]]; then
    slug="$(repo_slug)" || fail "origin is not a GitHub repository URL"
    if [[ "$dry_run" -eq 0 ]]; then
        command -v gh >/dev/null || fail "--report needs the GitHub CLI (gh)"
        [[ -z "$(git status --porcelain)" ]] || fail "--report needs a clean tree: commit or stash first"
    fi
fi

steps=("make test")
[[ "$full" -eq 1 ]] && steps+=("desktop theme generation in debian:trixie")

if [[ "$dry_run" -eq 1 ]]; then
    echo "local-ci: commit $sha"
    for step in "${steps[@]}"; do echo "local-ci: would run: $step"; done
    if [[ "$report" -eq 1 ]]; then
        echo "local-ci: would post: gh api repos/$slug/statuses/$sha -f state=success|failure -f context=$context"
    fi
    exit 0
fi

out="$module_root/build/local-ci"
mkdir -p "$out"
log="$out/$short.log"
: >"$log"
started=$SECONDS
status=0
summary=""

run_step() {
    local name="$1"
    shift
    echo "local-ci: $name" | tee -a "$log"
    if "$@" >>"$log" 2>&1; then
        echo "local-ci: ok   $name" | tee -a "$log"
        return 0
    fi
    echo "local-ci: FAIL $name (see $log)" | tee -a "$log"
    return 1
}

# shellcheck disable=SC2317  # called through run_step
full_generation() {
    command -v docker >/dev/null || { echo "docker not found"; return 1; }
    docker run --rm -v "$module_root:/src:ro" debian:trixie bash -euc '
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y -qq --no-install-recommends python3-pytest python3-pil \
            fonts-inter fonts-jetbrains-mono papirus-icon-theme >/dev/null
        cp -r /src/desktop /src/tests /tmp/
        cd /tmp && python3 -m pytest -q -p no:cacheprovider tests/test_txf_desktop_gen.py'
}

if run_step "make test" make test; then
    tests="$(grep -Eo '[0-9]+ passed(, [0-9]+ skipped)?' "$log" | tail -1 || true)"
    # make test skips shellcheck when it is not installed; say so instead of "clean".
    if grep -q 'shellcheck not installed' "$log"; then lint="shellcheck not installed"; else lint="shellcheck clean"; fi
    summary="${tests:-make test passed}; $lint"
else
    status=1
    summary="make test failed"
fi

if [[ "$full" -eq 1 && "$status" -eq 0 ]]; then
    if run_step "desktop theme generation in debian:trixie" full_generation; then
        summary="$summary; full theme generation passed"
    else
        status=1
        summary="$summary; full theme generation failed"
    fi
fi

elapsed=$((SECONDS - started))
state=success
[[ "$status" -eq 0 ]] || state=failure
description="$summary (local, ${elapsed} s)"
description="${description:0:140}"   # GitHub limits status descriptions to 140 characters

python3 - "$out/$short.json" "$sha" "$state" "$description" "$elapsed" "$full" <<'PY'
import json, platform, sys
path, sha, state, description, elapsed, full = sys.argv[1:]
json.dump({"sha": sha, "state": state, "description": description, "seconds": int(elapsed),
           "full": full == "1", "host": platform.node(), "system": platform.platform()},
          open(path, "w"), indent=2)
PY

echo "local-ci: $state: $description"
if [[ "$report" -eq 1 ]]; then
    gh api "repos/$slug/statuses/$sha" --method POST \
        -f state="$state" -f context="$context" -f description="$description" >/dev/null \
        || fail "could not post the commit status; the checks ended in $state"
    echo "local-ci: posted $context=$state on $short"
fi
exit "$status"
