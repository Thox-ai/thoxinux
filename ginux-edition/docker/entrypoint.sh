#!/usr/bin/env bash
# ThoxOS Ginux Edition demo container entrypoint.
#
# Starts the two host-side services the Ginux guest needs (DNS forwarder and
# read-only TLS registry, both on 127.0.0.1), then runs one mode:
#
#   console   interactive serial console (docker run -it ...)       [default]
#   shell     interactive ThoxOS shell domain (no systemd)            (-it)
#   web       browser console with ttyd on port 7681
#   selftest  headless boot; exits 0 when systemd welcomes ThoxOS and the
#             login prompt appears
#   doctor    prerequisite report
#   qemu      print the QEMU command line
#   exec CMD  run CMD as the runtime user once the services are up (scripted
#             demos and end-to-end checks)
set -euo pipefail

readonly mode="${1:-console}"
readonly run_user="thoxos"
readonly state_dir="${THOXOS_G_STATE_DIR:-/var/lib/thoxos-g/state}"
export THOXOS_G_STATE_DIR="$state_dir"

log() {
    printf 'thoxos-g-demo: %s\n' "$*" >&2
}

fail() {
    log "$*"
    exit 1
}

start_dns() {
    dnsmasq --conf-file=/etc/thoxos-g/dnsmasq.conf --resolv-file=/etc/resolv.conf \
        --pid-file=/run/thoxos-g-dnsmasq.pid --user=dnsmasq ||
        fail "dnsmasq failed to start"
}

start_registry() {
    registry serve /etc/thoxos-g/registry.yml >/var/log/thoxos-g-registry.log 2>&1 &
    # Ready means a verified TLS handshake for the exact name GINUX.EFI trusts.
    python3 - <<'EOF' || fail "registry did not become ready; see /var/log/thoxos-g-registry.log"
import socket, ssl, sys, time
context = ssl.create_default_context(cafile="/etc/thoxos-g/tls/thoxos-local-root.pem")
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    try:
        with socket.create_connection(("127.0.0.1", 443), timeout=2) as raw:
            with context.wrap_socket(raw, server_hostname="registry.thoxos.internal"):
                sys.exit(0)
    except OSError:
        time.sleep(0.5)
sys.exit(1)
EOF
}

grant_kvm() {
    # Give the unprivileged runtime user the group that owns /dev/kvm, whatever
    # GID the Docker host uses for it.
    [[ -c /dev/kvm ]] || return 0
    local gid group
    gid="$(stat -c '%g' /dev/kvm)"
    group="$(getent group "$gid" | cut -d: -f1 || true)"
    if [[ -z "$group" ]]; then
        group="kvmhost"
        groupadd --gid "$gid" "$group"
    fi
    usermod -aG "$group" "$run_user"
}

prepare_state() {
    mkdir -p "$state_dir"
    chown "$run_user:$run_user" "$state_dir"
    chmod 0750 "$state_dir"
}

as_runtime_user() {
    setpriv --reuid="$run_user" --regid="$run_user" --init-groups --inh-caps=-all \
        --reset-env -- env \
        HOME="/home/$run_user" TERM="${TERM:-xterm-256color}" LANG=C.UTF-8 \
        THOXOS_G_STATE_DIR="$state_dir" \
        ${THOXOS_G_MEMORY:+THOXOS_G_MEMORY="$THOXOS_G_MEMORY"} \
        ${THOXOS_G_ACCEL:+THOXOS_G_ACCEL="$THOXOS_G_ACCEL"} \
        ${THOXOS_G_BOOT_TIMEOUT:+THOXOS_G_BOOT_TIMEOUT="$THOXOS_G_BOOT_TIMEOUT"} \
        ${THOXOS_G_DOMAIN_MEMORY_MIB:+THOXOS_G_DOMAIN_MEMORY_MIB="$THOXOS_G_DOMAIN_MEMORY_MIB"} \
        "$@"
}

case "$mode" in
console | shell | web | selftest | doctor | qemu) ;;
exec) [[ $# -ge 2 ]] || fail "exec needs a command" ;;
*) fail "unknown mode '$mode' (console, shell, web, selftest, doctor, qemu, exec)" ;;
esac

start_dns
start_registry
grant_kvm
prepare_state
log "dns 127.0.0.1:53 and registry https://registry.thoxos.internal (127.0.0.1:443) ready"

case "$mode" in
console)
    [[ -t 0 ]] || fail "console mode needs a terminal: docker run -it ..."
    as_runtime_user /usr/bin/thoxos-g console
    ;;
shell)
    [[ -t 0 ]] || fail "shell mode needs a terminal: docker run -it ..."
    as_runtime_user /usr/bin/thoxos-g console --shell
    ;;
web)
    credential="${THOXOS_G_WEB_CREDENTIAL:-}"
    if [[ -z "$credential" ]]; then
        credential="thox:$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
        log "web console credential (generated for this container): $credential"
    fi
    [[ "$credential" == *:* ]] || fail "THOXOS_G_WEB_CREDENTIAL must be user:password"
    # One client at a time: each connection boots its own VM on the same volume.
    exec ttyd --port 7681 --interface 0.0.0.0 --max-clients 1 --writable \
        --credential "$credential" \
        -t 'titleFixed=ThoxOS Ginux Edition' \
        -t 'fontFamily=JetBrains Mono, ui-monospace, monospace' \
        -t 'fontSize=15' \
        -t 'theme={"background":"#09090B","foreground":"#E4E4E7","cursor":"#05A451","selectionBackground":"#05A45155","green":"#05A451","brightGreen":"#05A451"}' \
        setpriv --reuid="$run_user" --regid="$run_user" --init-groups --inh-caps=-all \
        env HOME="/home/$run_user" THOXOS_G_STATE_DIR="$state_dir" /usr/bin/thoxos-g console
    ;;
selftest)
    as_runtime_user /usr/bin/thoxos-g console \
        --until 'Welcome to ThoxOS' \
        --until 'ThoxOS 0.1.0 Ginux Edition  (Rocky Linux 10 userspace' \
        --until 'login:'
    ;;
doctor)
    as_runtime_user /usr/bin/thoxos-g doctor
    ;;
qemu)
    as_runtime_user /usr/bin/thoxos-g print-qemu
    ;;
exec)
    shift
    as_runtime_user "$@"
    ;;
esac
