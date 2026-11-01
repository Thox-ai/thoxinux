#!/usr/bin/env bash
# ThoxOS Ginux Edition: per-build local registry PKI.
#
# Creates an ECDSA P-256 root, signs one TLS leaf for registry.thoxos.internal,
# then destroys the root private key. The root certificate (public) is written
# into the patched Ginux tree so GINUX.EFI trusts exactly this build's registry
# leaf for exactly that host name. No other certificate can ever be issued
# under this root because its key no longer exists.
#
# Usage: scripts/make-local-ca.sh OUT_DIR [GINUX_SRC_DIR]
# Outputs:
#   OUT_DIR/thoxos-local-root.pem   root certificate (public)
#   OUT_DIR/registry.crt            leaf certificate (public)
#   OUT_DIR/registry.key            leaf private key (mode 0600)
#   GINUX_SRC_DIR/services/network/certs/thoxos-local-root.pem (when given)
set -euo pipefail

readonly host="registry.thoxos.internal"

fail() {
    echo "make-local-ca: $*" >&2
    exit 1
}

[[ $# -eq 1 || $# -eq 2 ]] || fail "usage: $0 OUT_DIR [GINUX_SRC_DIR]"
out="$1"
ginux_src="${2:-}"
command -v openssl >/dev/null 2>&1 || fail "openssl is required"
if [[ -n "$ginux_src" ]]; then
    [[ -d "$ginux_src/services/network/certs" ]] || fail "$ginux_src is not a Ginux source tree"
fi

mkdir -p "$out"
umask 077
work="$(mktemp -d)"
cleanup() {
    # The root key must not survive this script under any exit path.
    if [[ -f "$work/root.key" ]]; then
        shred -u "$work/root.key" 2>/dev/null || rm -f "$work/root.key"
    fi
    rm -rf "$work"
}
trap cleanup EXIT

# Backdate notBefore when the local OpenSSL supports it (3.4+). A dual-boot
# machine whose RTC holds Windows local time can run hours behind UTC until NTP
# corrects it; a two-day margin keeps the leaf valid through that window.
backdate=()
if openssl x509 -help 2>&1 | grep -q -- '-not_before'; then
    backdate=(-not_before "$(date -u -d '-2 days' +%Y%m%d%H%M%SZ)")
fi

openssl ecparam -name prime256v1 -genkey -noout -out "$work/root.key"
cat >"$work/root.cnf" <<'EOF'
[req]
distinguished_name = dn
x509_extensions = root_ext
prompt = no
[dn]
O = THOX.ai LLC
CN = ThoxOS Ginux Local Registry Root
[root_ext]
basicConstraints = critical, CA:TRUE, pathlen:0
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
EOF
openssl req -new -key "$work/root.key" -config "$work/root.cnf" -out "$work/root.csr"
openssl x509 -req -in "$work/root.csr" -signkey "$work/root.key" \
    -extfile "$work/root.cnf" -extensions root_ext -sha256 -days 3650 \
    "${backdate[@]}" -out "$work/root.pem"

openssl ecparam -name prime256v1 -genkey -noout -out "$work/registry.key"
cat >"$work/leaf.cnf" <<EOF
[leaf_ext]
basicConstraints = critical, CA:FALSE
keyUsage = critical, digitalSignature
extendedKeyUsage = serverAuth
subjectAltName = DNS:$host
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid
EOF
openssl req -new -key "$work/registry.key" -subj "/O=THOX.ai LLC/CN=$host" -out "$work/registry.csr"
openssl x509 -req -in "$work/registry.csr" -CA "$work/root.pem" -CAkey "$work/root.key" \
    -CAcreateserial -extfile "$work/leaf.cnf" -extensions leaf_ext -sha256 -days 1825 \
    "${backdate[@]}" -out "$work/registry.crt"

openssl verify -CAfile "$work/root.pem" "$work/registry.crt" >/dev/null ||
    fail "leaf certificate does not verify against the new root"

install -m 0644 "$work/root.pem" "$out/thoxos-local-root.pem"
install -m 0644 "$work/registry.crt" "$out/registry.crt"
install -m 0600 "$work/registry.key" "$out/registry.key"
if [[ -n "$ginux_src" ]]; then
    install -m 0644 "$work/root.pem" "$ginux_src/services/network/certs/thoxos-local-root.pem"
fi

# The Ginux network service decodes the anchor into a 2048-byte DER buffer.
der_size="$(openssl x509 -in "$work/root.pem" -outform DER | wc -c)"
((der_size <= 2048)) || fail "root certificate DER is $der_size bytes; limit is 2048"

echo "make-local-ca: root $(openssl x509 -in "$out/thoxos-local-root.pem" -noout -fingerprint -sha256 | cut -d= -f2)"
echo "make-local-ca: leaf for $host, root key destroyed"
