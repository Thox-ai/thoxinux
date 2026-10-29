#!/usr/bin/env bash
# ThoxOS Ginux Edition: build the KnightHub external-SSD disk image.
#
# 1. Builds the Debian 13 host root (installer/host) on top of the demo image's
#    ThoxOS runtime (GINUX.EFI, seeded registry, TLS leaf, thoxos-g).
# 2. Exports it and assembles a GPT disk image (ESP + ext4 root) inside a
#    disk-tools container. No loop devices, mounts or root on the build host
#    beyond Docker itself.
#
# Usage:
#   installer/build-ssd-image.sh --demo-image thoxos-g/demo:0.1.0 \
#       --host-image thoxos-g/knighthub-host:0.1.0 --size 8G --out build/ssd \
#       [--admin-password-file FILE] [--extra-ca CA.pem] [--xz]
#
# Write the result to the SSD with installer/install-to-ssd.sh (Linux),
# installer/Install-ThoxOSGinux.ps1 (Windows), or Rufus/balenaEtcher (DD mode).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly tools_image="thoxos-g/disk-tools:1"
readonly debian_image="docker.io/library/debian:trixie@sha256:2dc419c6d7fe3dad0a2f9fd469c34cc90b0f9ba642d8fde837fe3d7d34a0e7f1"

demo_image=""
host_image=""
size="8G"
out=""
admin_password_file=""
extra_ca=""
compress=0

fail() {
    echo "build-ssd-image: $*" >&2
    exit 1
}

while (($#)); do
    case "$1" in
    --demo-image) demo_image="${2:?}"; shift 2 ;;
    --host-image) host_image="${2:?}"; shift 2 ;;
    --size) size="${2:?}"; shift 2 ;;
    --out) out="${2:?}"; shift 2 ;;
    --admin-password-file) admin_password_file="${2:?}"; shift 2 ;;
    --extra-ca) extra_ca="${2:?}"; shift 2 ;;
    --xz) compress=1; shift ;;
    -h | --help) sed -n '2,18p' "$0"; exit 0 ;;
    *) fail "unknown argument: $1" ;;
    esac
done
[[ -n "$demo_image" && -n "$host_image" && -n "$out" ]] ||
    fail "--demo-image, --host-image and --out are required"
command -v docker >/dev/null 2>&1 || fail "docker is required"
docker image inspect "$demo_image" >/dev/null 2>&1 || fail "demo image $demo_image not found; run make demo-image"
if [[ -n "$admin_password_file" ]]; then
    [[ -s "$admin_password_file" ]] || fail "$admin_password_file is empty or missing"
fi
version="$(cat "$repo_root/VERSION")"

mkdir -p "$out"
out="$(cd "$out" && pwd)"

secrets=()
[[ -n "$admin_password_file" ]] && secrets+=(--secret "id=admin_password,src=$admin_password_file")
[[ -n "$extra_ca" ]] && secrets+=(--secret "id=extra_ca,src=$extra_ca")

echo "build-ssd-image: building host root $host_image"
docker build "${secrets[@]}" \
    --build-arg "DEMO_IMAGE=$demo_image" \
    --build-arg "THOXOS_VERSION=$version" \
    -t "$host_image" "$repo_root/installer/host"

echo "build-ssd-image: exporting host root"
container="$(docker create "$host_image" /bin/true)"
trap 'docker rm -f "$container" >/dev/null 2>&1 || true' EXIT
docker export -o "$out/host-rootfs.tar" "$container"

echo "build-ssd-image: preparing disk tools"
docker build -q -t "$tools_image" - >/dev/null <<EOF
FROM $debian_image
RUN apt-get update \\
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \\
      e2fsprogs dosfstools mtools fdisk uuid-runtime xz-utils coreutils tar \\
 && rm -rf /var/lib/apt/lists/*
EOF

docker run --rm \
    -v "$repo_root/installer/assemble-disk.sh:/usr/local/bin/assemble-disk.sh:ro" \
    -v "$out:/out" \
    "$tools_image" bash /usr/local/bin/assemble-disk.sh /out/host-rootfs.tar /out "$size" "$version"
rm -f "$out/host-rootfs.tar"

image="$out/thoxos-ginux-knighthub-$version.img"
if ((compress)); then
    echo "build-ssd-image: compressing (xz)"
    docker run --rm -v "$out:/out" "$tools_image" \
        sh -c "xz -T0 -6 -k -f /out/$(basename "$image") && cd /out && sha256sum $(basename "$image").xz > $(basename "$image").xz.sha256"
fi
echo "build-ssd-image: done"
ls -la "$out"
