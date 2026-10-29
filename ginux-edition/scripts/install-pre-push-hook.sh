#!/usr/bin/env bash
# Copyright (c) 2026 THOX.ai LLC. Licensed under the Apache License, Version 2.0.
#
# install-pre-push-hook.sh: make `git push` run the local CI gate first.
# Pushes that change ginux-edition/ run scripts/local-ci.sh (make test); a red
# result stops the push. `git push --no-verify` skips the gate when you must.
# After the push, `make ci-report` posts the result on GitHub as a commit
# status. Replaces the retired GitHub Actions workflow (DECISIONS D32).
#
# Usage: scripts/install-pre-push-hook.sh        install or update the hook
#        scripts/install-pre-push-hook.sh --remove
set -euo pipefail

module_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
git_dir="$(git -C "$module_root" rev-parse --git-common-dir 2>/dev/null)" || {
    echo "install-pre-push-hook: not inside a git checkout" >&2
    exit 1
}
[[ "$git_dir" = /* ]] || git_dir="$module_root/$git_dir"
hook="$git_dir/hooks/pre-push"
marker="# thoxos-ginux local CI gate"

if [[ "${1:-}" == "--remove" ]]; then
    if [[ -f "$hook" ]] && grep -q "$marker" "$hook"; then
        rm -f "$hook"
        echo "install-pre-push-hook: removed $hook"
    else
        echo "install-pre-push-hook: no gate installed"
    fi
    exit 0
fi
[[ $# -eq 0 ]] || { echo "usage: $0 [--remove]" >&2; exit 2; }

if [[ -f "$hook" ]] && ! grep -q "$marker" "$hook"; then
    echo "install-pre-push-hook: $hook exists and is not ours; leaving it alone" >&2
    exit 1
fi

top="$(git -C "$module_root" rev-parse --show-toplevel)"
rel="${module_root#"$top"/}"
[[ "$rel" != "$module_root" ]] || rel="."
mkdir -p "$(dirname "$hook")"
cat >"$hook" <<EOF
#!/usr/bin/env bash
$marker (scripts/install-pre-push-hook.sh)
set -euo pipefail
top="\$(git rev-parse --show-toplevel)"
zero=0000000000000000000000000000000000000000
changed=0
while read -r _local_ref local_sha _remote_ref remote_sha; do
    [[ "\$local_sha" == "\$zero" ]] && continue
    if [[ "\$remote_sha" == "\$zero" ]]; then
        changed=1
    elif git diff --quiet "\$remote_sha" "\$local_sha" -- "$rel" 2>/dev/null; then
        :
    else
        changed=1
    fi
done
[[ "\$changed" -eq 1 ]] || exit 0
echo "pre-push: running the local CI gate for $rel"
exec bash "\$top/$rel/scripts/local-ci.sh"
EOF
chmod 0755 "$hook"
echo "install-pre-push-hook: installed $hook (gate for $rel)"
