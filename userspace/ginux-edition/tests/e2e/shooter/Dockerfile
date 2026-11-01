# Screenshot helper for the ThoxOS web console (documentation captures only).
FROM docker.io/library/debian:trixie-slim@sha256:f6b08b09a05725f9431502d3b5714f5c4576e82c1a84fa1debe0c24a7e0c3ec4
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      chromium python3 python3-venv ca-certificates fonts-dejavu-core fonts-jetbrains-mono \
 && rm -rf /var/lib/apt/lists/*
COPY with-extra-ca.sh /usr/local/bin/with-extra-ca
RUN --mount=type=secret,id=extra_ca,required=false with-extra-ca sh -euc '\
      python3 -m venv /opt/shooter; \
      if [ -n "${SSL_CERT_FILE:-}" ]; then export PIP_CERT="$SSL_CERT_FILE"; fi; \
      /opt/shooter/bin/pip install --no-cache-dir playwright==1.55.0'
COPY shoot_console.py /usr/local/bin/shoot_console.py
ENTRYPOINT ["/opt/shooter/bin/python", "/usr/local/bin/shoot_console.py"]
