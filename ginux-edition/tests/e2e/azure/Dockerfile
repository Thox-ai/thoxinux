# Test bench for the Azure image: QEMU + OVMF to boot the VHD, a NoCloud seed
# builder, and an RDP client on a virtual X display for screenshots.
FROM docker.io/library/debian:trixie@sha256:2dc419c6d7fe3dad0a2f9fd469c34cc90b0f9ba642d8fde837fe3d7d34a0e7f1
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      qemu-system-x86 qemu-utils ovmf genisoimage freerdp3-x11 xvfb imagemagick xdotool \
      openssh-client sshpass python3 ca-certificates procps x11-utils dosfstools mtools \
 && rm -rf /var/lib/apt/lists/*
