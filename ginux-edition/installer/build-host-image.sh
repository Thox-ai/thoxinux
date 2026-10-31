#!/usr/bin/env bash
# Copyright (c) 2026 THOX.ai LLC. Licensed under the Apache License, Version 2.0.
# ThoxOS Ginux Edition: build a host disk image for KnightHub or Azure.
#
# 1. Stages a clean Docker context (host Dockerfile, overlays, ThoxOS Desktop
#    sources, the thox CLI and the AI relay) and builds the Debian 13 host root
#    on top of the demo image's ThoxOS runtime.
# 2. Exports it and assembles a GPT disk image (ESP + ext4 root) inside a
#    disk-tools container. No loop devices or mounts on the build host.
# 3. For Azure, converts the image to a fixed VHD with a 1 MiB-aligned size and
#    verifies the VHD footer (azure/vhd_check.py).
#
# Usage:
#   installer/build-host-image.sh --target knighthub|azure --desktop headless|desktop \
#       --demo-image thoxos-g/demo:0.1.0 --host-image NAME:TAG --size 8G --out DIR \
#       [--admin-password-file FILE] [--extra-ca CA.pem] [--xz] [--keep-raw]
#
# KnightHub images are written to an SSD with installer/install-to-ssd.sh or
# installer/Install-ThoxOSGinux.ps1; Azure VHDs are published with
# azure/publish-image.sh and deployed with azure/main.bicep.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly tools_image="thoxos-g/disk-tools:2"
readonly debian_image="docker.io/library/debian:trixie@sha256:2dc419c6d7fe3dad0a2f9fd469c34cc90b0f9ba642d8fde837fe3d7d34a0e7f1"

target=knighthub
desktop=headless
demo_image=""
host_image=""
size="8G"
out=""
admin_password_file=""
extra_ca=""
compress=0
keep_raw=0

fail() {
    echo "build-host-image: $*" >&2
    exit 1
}

while (($#)); do
    case "$1" in
    --target) target="${2:?}"; shift 2 ;;
    --desktop) desktop="${2:?}"; shift 2 ;;
    --demo-image) demo_image="${2:?}"; shift 2 ;;
    --host-image) host_image="${2:?}"; shift 2 ;;
    --size) size="${2:?}"; shift 2 ;;
    --out) out="${2:?}"; shift 2 ;;
    --admin-password-file) admin_password_file="${2:?}"; shift 2 ;;
    --extra-ca) extra_ca="${2:?}"; shift 2 ;;
    --xz) compress=1; shift ;;
    --keep-raw) keep_raw=1; shift ;;
    -h | --help) sed -n '3,21p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) fail "unknown argument: $1" ;;
    esac
done
case "$target" in knighthub | azure) ;; *) fail "--target must be knighthub or azure" ;; esac
case "$desktop" in headless | desktop) ;; *) fail "--desktop must be headless or desktop" ;; esac
[[ -n "$demo_image" && -n "$host_image" && -n "$out" ]] ||
    fail "--demo-image, --host-image and --out are required"
command -v docker >/dev/null 2>&1 || fail "docker is required"
docker image inspect "$demo_image" >/dev/null 2>&1 || fail "demo image $demo_image not found; run make demo-image"
if [[ -n "$admin_password_file" ]]; then
    [[ "$target" == knighthub ]] || fail "--admin-password-file applies to KnightHub images; Azure creates the admin at deployment"
    [[ -s "$admin_password_file" ]] || fail "$admin_password_file is empty or missing"
fi
guest_version="$(cat "$repo_root/VERSION")"
host_version="$(cat "$repo_root/HOST_VERSION")"
[[ "$host_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "HOST_VERSION must be semver"

mkdir -p "$out"
out="$(cd "$out" && pwd)"
context="$(mktemp -d "${TMPDIR:-/tmp}/thoxos-host-context.XXXXXX")"
container=""
cleanup() {
    rm -rf "$context"
    if [[ -n "$container" ]]; then docker rm -f "$container" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT

echo "build-host-image: staging context ($target, $desktop)"
cp "$repo_root/installer/host/Dockerfile" "$repo_root/installer/host/configure-host.sh" "$context/"
cp -a "$repo_root/installer/host/overlay" "$context/overlay"
cp -a "$repo_root/azure/overlay" "$context/overlay-azure"
mkdir -p "$context/desktop"
cp -a "$repo_root/desktop/tokens" "$repo_root/desktop/generator" "$repo_root/desktop/bin" \
    "$repo_root/desktop/overlay" "$context/desktop/"
find "$context/desktop" -name '__pycache__' -prune -exec rm -rf {} +
cp "$repo_root/rootfs/overlay/usr/local/bin/thox" "$context/thox"
cp "$repo_root/runtime/thox_ai_relay.py" "$context/thox_ai_relay.py"

secrets=()
[[ -n "$admin_password_file" ]] && secrets+=(--secret "id=admin_password,src=$admin_password_file")
[[ -n "$extra_ca" ]] && secrets+=(--secret "id=extra_ca,src=$extra_ca")

echo "build-host-image: building host root $host_image"
docker build "${secrets[@]}" \
    --build-arg "DEMO_IMAGE=$demo_image" \
    --build-arg "TARGET=$target" \
    --build-arg "DESKTOP=$desktop" \
    --build-arg "THOXOS_VERSION=$guest_version" \
    --build-arg "HOST_VERSION=$host_version" \
    -t "$host_image" "$context"

echo "build-host-image: exporting host root"
container="$(docker create "$host_image" /bin/true)"
docker export -o "$out/host-rootfs.tar" "$container"
docker rm -f "$container" >/dev/null
container=""

echo "build-host-image: preparing disk tools"
docker build -q -t "$tools_image" - >/dev/null <<EOF
FROM $debian_image
RUN apt-get update \\
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \\
      e2fsprogs dosfstools mtools fdisk uuid-runtime xz-utils coreutils tar qemu-utils python3 \\
 && rm -rf /var/lib/apt/lists/*
EOF

docker run --rm \
    -v "$repo_root/installer/assemble-disk.sh:/usr/local/bin/assemble-disk.sh:ro" \
    -v "$out:/out" \
    "$tools_image" bash /usr/local/bin/assemble-disk.sh /out/host-rootfs.tar /out "$size" "$host_version" \
    --target "$target" --desktop "$desktop"
rm -f "$out/host-rootfs.tar"

if [[ "$target" == knighthub && "$desktop" == headless ]]; then
    stem="thoxos-ginux-knighthub-$host_version"
else
    stem="thoxos-ginux-$target-$desktop-$host_version"
fi
image="$stem.img"
[[ -s "$out/$image" ]] || fail "assembly did not produce $image"

if [[ "$target" == azure ]]; then
    echo "build-host-image: converting to a fixed VHD for Azure"
    docker run --rm \
        -v "$repo_root/azure/build-vhd.sh:/usr/local/bin/build-vhd.sh:ro" \
        -v "$repo_root/azure/vhd_check.py:/usr/local/bin/vhd_check.py:ro" \
        -v "$out:/out" \
        "$tools_image" bash /usr/local/bin/build-vhd.sh "/out/$image" "/out/$stem.vhd"
    if ((keep_raw == 0)); then
        rm -f "$out/$image" "$out/$image.sha256"
    fi
fi

if ((compress)); then
    artifact="$image"
    [[ "$target" == azure ]] && artifact="$stem.vhd"
    echo "build-host-image: compressing $artifact (xz)"
    docker run --rm -v "$out:/out" "$tools_image" \
        sh -c "xz -T0 -6 -k -f /out/$artifact && cd /out && sha256sum $artifact.xz > $artifact.xz.sha256"
fi
echo "build-host-image: done"
ls -la "$out"
