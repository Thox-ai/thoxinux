#!/bin/sh
# Run a command trusting one extra CA bundle in addition to the system store.
#
# Used inside Docker build steps that fetch over HTTPS (rustup, crates.io,
# GitHub) behind a TLS-inspecting corporate proxy. The extra bundle arrives as
# the BuildKit secret "extra_ca", so it is visible only to the RUN step that
# mounts it and never lands in an image layer. Without the secret the command
# runs unchanged against the system trust store.
#
# Usage: with-extra-ca.sh COMMAND [ARG...]
set -eu

secret=/run/secrets/extra_ca
if [ -s "$secret" ]; then
    bundle="$(mktemp)"
    trap 'rm -f "$bundle"' EXIT INT TERM
    cat /etc/ssl/certs/ca-certificates.crt "$secret" >"$bundle"
    SSL_CERT_FILE="$bundle"
    CURL_CA_BUNDLE="$bundle"
    CARGO_HTTP_CAINFO="$bundle"
    GIT_SSL_CAINFO="$bundle"
    export SSL_CERT_FILE CURL_CA_BUNDLE CARGO_HTTP_CAINFO GIT_SSL_CAINFO
    "$@"
    exit $?
fi
exec "$@"
