# syntax=docker/dockerfile:1
FROM rust:1.99.0-bookworm AS build
RUN apt-get update && apt-get install -y --no-install-recommends \
    clang make git python3 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN --mount=type=secret,id=proxy_ca \
    if [ -s /run/secrets/proxy_ca ]; then \
      export SSL_CERT_FILE=/run/secrets/proxy_ca CURL_CA_BUNDLE=/run/secrets/proxy_ca; \
    fi; \
    rustup component add clippy rustfmt \
    && rustup target add x86_64-unknown-uefi x86_64-unknown-none
WORKDIR /kit
COPY upstream.env ./
COPY scripts ./scripts
COPY patches ./patches
RUN --mount=type=secret,id=proxy_ca \
    if [ -s /run/secrets/proxy_ca ]; then \
      export SSL_CERT_FILE=/run/secrets/proxy_ca CURL_CA_BUNDLE=/run/secrets/proxy_ca \
        GIT_SSL_CAINFO=/run/secrets/proxy_ca CARGO_HTTP_CAINFO=/run/secrets/proxy_ca; \
    fi; \
    chmod +x scripts/*.sh \
    && GINUX_ARTIFACT_DIR=/out ./scripts/build-native.sh

FROM scratch AS artifacts
COPY --from=build /out/ /

FROM ubuntu:24.04 AS runtime
LABEL org.opencontainers.image.title="ThoxOS Ginux Research Edition" \
      org.opencontainers.image.version="0.2.0-azure-candidate" \
      org.opencontainers.image.source="https://github.com/ttracx/thoxos-ginux" \
      ai.thox.ginux.upstream-commit="36503bda2d87465765e1b94e65f9d100f27ed5be" \
      ai.thox.ginux.hardware-status="QEMU guest; physical hardware unvalidated"
RUN apt-get update && apt-get install -y --no-install-recommends \
    qemu-system-x86 ovmf bash coreutils util-linux ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --user-group --create-home thox \
    && mkdir /data && chown 10001:10001 /data
COPY --from=build /out /opt/thox/ginux/artifacts
COPY scripts/run-vm.sh /opt/thox/ginux/scripts/run-vm.sh
RUN chmod 755 /opt/thox/ginux/scripts/run-vm.sh
USER 10001:10001
ENV GINUX_ARTIFACT_DIR=/opt/thox/ginux/artifacts GINUX_STATE_DIR=/data QEMU_ACCEL=tcg GINUX_MEMORY=2G
VOLUME ["/data"]
ENTRYPOINT ["/opt/thox/ginux/scripts/run-vm.sh"]
