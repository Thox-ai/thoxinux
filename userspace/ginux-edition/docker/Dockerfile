# ThoxOS Ginux Edition demo image.
#
# Stages
#   pki      per-build registry PKI; the root private key never leaves this stage
#   efi      patched Ginux source -> GINUX.EFI trusting this build's registry root
#   seed     ThoxOS userspace image pushed into a registry store (OCI, gzip)
#   runtime  QEMU 11 + OVMF + DNS forwarder + read-only TLS registry + thoxos-g
#
# Build with `make demo-image` (it creates build/userspace.tar first). Behind a
# TLS-inspecting proxy, pass its CA as a secret: EXTRA_CA=/path/ca.pem make demo-image

ARG DEBIAN_IMAGE=docker.io/library/debian:trixie-slim@sha256:f6b08b09a05725f9431502d3b5714f5c4576e82c1a84fa1debe0c24a7e0c3ec4
ARG REGISTRY_IMAGE=docker.io/library/registry:2@sha256:a3d8aaa63ed8681a604f1dea0aa03f100d5895b6a58ace528858a7b332415373

FROM ${REGISTRY_IMAGE} AS registry

# ---------------------------------------------------------------- pki
FROM ${DEBIAN_IMAGE} AS pki
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends openssl coreutils \
 && rm -rf /var/lib/apt/lists/*
COPY scripts/make-local-ca.sh /usr/local/bin/make-local-ca.sh
RUN bash /usr/local/bin/make-local-ca.sh /pki

# ---------------------------------------------------------------- efi
FROM ${DEBIAN_IMAGE} AS efi
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates curl git make clang lld openssl \
 && rm -rf /var/lib/apt/lists/*
ENV RUSTUP_HOME=/opt/rustup CARGO_HOME=/opt/cargo PATH=/opt/cargo/bin:$PATH
COPY scripts/with-extra-ca.sh /usr/local/bin/with-extra-ca
RUN --mount=type=secret,id=extra_ca,required=false with-extra-ca sh -euc '\
      url=https://static.rust-lang.org/rustup/dist/x86_64-unknown-linux-gnu/rustup-init; \
      curl -fsSL -o /tmp/rustup-init "$url"; \
      expected="$(curl -fsSL "$url.sha256" | cut -d" " -f1)"; \
      echo "$expected  /tmp/rustup-init" | sha256sum -c -; \
      chmod +x /tmp/rustup-init; \
      /tmp/rustup-init -y --no-modify-path --profile minimal --default-toolchain none; \
      rm /tmp/rustup-init'
WORKDIR /work
COPY upstream.lock ./upstream.lock
COPY patches ./patches
COPY scripts ./scripts
RUN --mount=type=secret,id=extra_ca,required=false with-extra-ca bash scripts/ginux-source.sh /work/ginux-src
COPY --from=pki /pki/thoxos-local-root.pem /work/ginux-src/services/network/certs/thoxos-local-root.pem
RUN --mount=type=secret,id=extra_ca,required=false with-extra-ca bash scripts/build-efi.sh /work/ginux-src /out

# ---------------------------------------------------------------- seed
FROM ${DEBIAN_IMAGE} AS seed
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends skopeo ca-certificates python3 \
 && rm -rf /var/lib/apt/lists/*
COPY --from=registry /bin/registry /usr/local/bin/registry
COPY build/userspace.tar /seed/userspace.tar
ARG THOXOS_VERSION=0.1.0
RUN <<EOF
set -eu
cat >/seed/registry-seed.yml <<'YAML'
version: 0.1
log:
  level: warn
storage:
  filesystem:
    rootdirectory: /seed/registry
http:
  addr: 127.0.0.1:5000
YAML
registry serve /seed/registry-seed.yml &
registry_pid=$!
python3 - <<'PY'
import socket, sys, time
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    try:
        socket.create_connection(("127.0.0.1", 5000), timeout=1).close()
        sys.exit(0)
    except OSError:
        time.sleep(0.3)
sys.exit("seed registry did not start")
PY
skopeo copy --format oci --dest-compress-format gzip --dest-tls-verify=false \
    docker-archive:/seed/userspace.tar \
    "docker://127.0.0.1:5000/thoxos/userspace:${THOXOS_VERSION}"
skopeo inspect --tls-verify=false --raw "docker://127.0.0.1:5000/thoxos/userspace:${THOXOS_VERSION}" >/seed/manifest.json
python3 - <<'PY'
import json
manifest = json.load(open("/seed/manifest.json"))
layers = manifest["layers"]
assert manifest["mediaType"] == "application/vnd.oci.image.manifest.v1+json", manifest["mediaType"]
assert 1 <= len(layers) <= 16, len(layers)
assert all(layer["mediaType"].endswith("tar+gzip") for layer in layers), layers
print(f"seeded OCI manifest with {len(layers)} gzip layers")
PY
kill "$registry_pid"
wait "$registry_pid" 2>/dev/null || true
rm /seed/userspace.tar
EOF

# ---------------------------------------------------------------- runtime
FROM ${DEBIAN_IMAGE} AS runtime
ARG THOXOS_VERSION=0.1.0
# QEMU 11 from trixie-backports: trixie's QEMU 10.0.x fails Ginux virtio-net
# initialization (observed with 10.0.13).
RUN echo "deb http://deb.debian.org/debian trixie-backports main" >/etc/apt/sources.list.d/backports.list \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends -t trixie-backports qemu-system-x86 \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ovmf python3 dnsmasq-base ca-certificates tini util-linux passwd procps \
 && rm -rf /var/lib/apt/lists/*
ADD --checksum=sha256:8a217c968aba172e0dbf3f34447218dc015bc4d5e59bf51db2f2cd12b7be4f55 \
    https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.x86_64 /usr/local/bin/ttyd
COPY --from=registry /bin/registry /usr/local/bin/registry
COPY --from=efi /out/GINUX.EFI /out/GINUX.EFI.sha256 /usr/lib/thoxos-g/
COPY --from=seed /seed/registry /var/lib/thoxos-g/registry
COPY --from=seed /seed/manifest.json /usr/share/thoxos-g/userspace-manifest.json
COPY --from=pki /pki/thoxos-local-root.pem /pki/registry.crt /pki/registry.key /etc/thoxos-g/tls/
COPY runtime/thoxos_g.py /usr/lib/thoxos-g/thoxos_g.py
COPY runtime/registry.yml runtime/dnsmasq.conf /etc/thoxos-g/
COPY docker/entrypoint.sh /usr/local/bin/thoxos-g-entrypoint
RUN set -eu; \
    chmod 0755 /usr/local/bin/ttyd /usr/local/bin/thoxos-g-entrypoint; \
    printf '#!/bin/sh\nexec python3 -I /usr/lib/thoxos-g/thoxos_g.py "$@"\n' >/usr/bin/thoxos-g; \
    chmod 0755 /usr/bin/thoxos-g; \
    id dnsmasq >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin dnsmasq; \
    useradd --create-home --shell /bin/bash thoxos; \
    chmod 0600 /etc/thoxos-g/tls/registry.key; \
    chmod -R a-w /var/lib/thoxos-g/registry; \
    mkdir -p /var/lib/thoxos-g/state && chown thoxos:thoxos /var/lib/thoxos-g/state; \
    printf '%s\n' "$THOXOS_VERSION" >/usr/share/thoxos-g/VERSION; \
    cd /usr/lib/thoxos-g && sha256sum -c GINUX.EFI.sha256; \
    qemu-system-x86_64 --version | head -1
ENV THOXOS_G_STATE_DIR=/var/lib/thoxos-g/state \
    THOXOS_G_MEMORY=2G
LABEL org.opencontainers.image.title="ThoxOS Ginux Edition demo" \
      org.opencontainers.image.version="${THOXOS_VERSION}" \
      org.opencontainers.image.vendor="THOX.ai LLC" \
      org.opencontainers.image.description="ThoxOS userspace on the Ginux kernel inside QEMU, with console and web console"
EXPOSE 7681
VOLUME ["/var/lib/thoxos-g/state"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/local/bin/thoxos-g-entrypoint"]
CMD ["console"]
