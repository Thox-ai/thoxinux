# ThoxOS Ginux Edition host root file system.
#
# One Debian 13 host definition, two axes:
#   TARGET   knighthub  external SSD on KnightHub (generic kernel, firmware, tty1 console)
#            azure      Azure VM image (cloud kernel, Hyper-V drivers in the initrd,
#                       cloud-init + Azure Linux Agent, serial console, SSH)
#   DESKTOP  headless   console only (ThoxOS on Ginux on tty1)
#            desktop    ThoxOS Desktop (TXF 5.2 looks on XFCE, LightDM, xrdp)
#
# Ginux itself drives only QEMU virtio devices, so the host owns the hardware and
# runs Ginux under KVM with the validated QEMU profile. The ThoxOS runtime
# (GINUX.EFI, seeded registry, TLS leaf, thoxos-g) comes from the demo image.
#
# Built by installer/build-host-image.sh from a staged context; the result is
# exported into a disk image, never run as a container service.

ARG DEBIAN_IMAGE=docker.io/library/debian:trixie@sha256:2dc419c6d7fe3dad0a2f9fd469c34cc90b0f9ba642d8fde837fe3d7d34a0e7f1
ARG DEMO_IMAGE=thoxos-g/demo:0.1.0
ARG DESKTOP=headless

FROM ${DEMO_IMAGE} AS demo

# ------------------------------------------------------------ desktop assets
# Themes, wallpapers, splash, dock and terminal palettes are generated from the
# TXF desktop tokens here, so the host image never carries the generator's
# build dependencies.
FROM ${DEBIAN_IMAGE} AS desktop-gen-desktop
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-pil libgtk-3-0t64 libglib2.0-bin \
      fonts-inter fonts-jetbrains-mono papirus-icon-theme \
 && rm -rf /var/lib/apt/lists/*
COPY desktop/ /src/desktop/
RUN set -eu; \
    mkdir -p /tmp/adwaita /gen/usr/local/bin; \
    lib="$(readlink -f /usr/lib/x86_64-linux-gnu/libgtk-3.so.0)"; \
    for css in gtk-contained.css gtk-contained-dark.css; do \
        gresource extract "$lib" "/org/gtk/libgtk/theme/Adwaita/$css" >"/tmp/adwaita/$css"; \
        test -s "/tmp/adwaita/$css"; \
    done; \
    python3 /src/desktop/generator/txf_desktop_gen.py \
        --tokens /src/desktop/tokens/txf-tokens.json --adwaita-dir /tmp/adwaita \
        --fonts-dir /usr/share/fonts --papirus-dir /usr/share/icons --out /gen; \
    cp -a /src/desktop/overlay/. /gen/; \
    install -m 0755 /src/desktop/bin/* /gen/usr/local/bin/

FROM ${DEBIAN_IMAGE} AS desktop-gen-headless
RUN mkdir -p /gen

FROM desktop-gen-${DESKTOP} AS desktop-assets

# ---------------------------------------------------------------------- host
FROM ${DEBIAN_IMAGE} AS host
ARG TARGET=knighthub
ARG DESKTOP=headless
ARG THOXOS_VERSION=0.1.0
ARG HOST_VERSION=0.2.0
ENV DEBIAN_FRONTEND=noninteractive

# Packages per target and desktop choice. initramfs-tools with MODULES=most
# keeps USB storage in the KnightHub initrd; the Azure initrd gets the Hyper-V
# storage and network drivers Azure requires (hv_vmbus, hv_storvsc, hv_netvsc).
RUN set -eu; \
    case "$TARGET" in knighthub|azure) ;; *) echo "TARGET must be knighthub or azure" >&2; exit 2 ;; esac; \
    case "$DESKTOP" in headless|desktop) ;; *) echo "DESKTOP must be headless or desktop" >&2; exit 2 ;; esac; \
    echo "deb http://deb.debian.org/debian trixie non-free-firmware" >/etc/apt/sources.list.d/firmware.list; \
    echo "deb http://deb.debian.org/debian trixie-backports main" >/etc/apt/sources.list.d/backports.list; \
    apt-get update; \
    common="systemd systemd-sysv systemd-resolved dbus udev kmod initramfs-tools systemd-boot-efi \
        ovmf python3 dnsmasq-base ca-certificates util-linux passwd procps sudo less nano \
        iproute2 iputils-ping cloud-guest-utils e2fsprogs dosfstools kbd console-setup locales"; \
    if [ "$TARGET" = azure ]; then \
        target="linux-image-cloud-amd64 cloud-init waagent hyperv-daemons openssh-server chrony gdisk netbase"; \
    else \
        target="linux-image-amd64 systemd-timesyncd firmware-realtek firmware-misc-nonfree firmware-intel-misc"; \
    fi; \
    desktop=""; \
    if [ "$DESKTOP" = desktop ]; then \
        desktop="xfce4 xfce4-panel xfwm4 xfdesktop4 xfce4-session xfce4-settings xfconf thunar xfce4-terminal \
            xfce4-whiskermenu-plugin xfce4-appmenu-plugin appmenu-gtk3-module xfce4-genmon-plugin xfce4-notifyd \
            plank lightdm lightdm-gtk-greeter xserver-xorg-core xserver-xorg-input-libinput xserver-xorg-video-fbdev \
            xrdp xorgxrdp xauth x11-xserver-utils dbus-x11 dconf-cli dconf-gsettings-backend polkitd \
            fonts-inter fonts-jetbrains-mono papirus-icon-theme adwaita-icon-theme librsvg2-common \
            plymouth plymouth-themes firefox-esr fastfetch mousepad ristretto exo-utils xdg-utils xdg-user-dirs ssl-cert"; \
    fi; \
    # shellcheck disable=SC2086
    apt-get install -y --no-install-recommends $common $target $desktop; \
    apt-get install -y --no-install-recommends -t trixie-backports qemu-system-x86; \
    rm -rf /var/lib/apt/lists/*

# ThoxOS runtime from the demo image: one source of truth for GINUX.EFI, the
# seeded registry, its TLS leaf, and the thoxos-g driver.
COPY --from=demo /usr/lib/thoxos-g /usr/lib/thoxos-g
COPY --from=demo /usr/bin/thoxos-g /usr/bin/thoxos-g
COPY --from=demo /usr/local/bin/registry /usr/local/bin/registry
COPY --from=demo /usr/local/bin/ttyd /usr/local/bin/ttyd
COPY --from=demo /var/lib/thoxos-g/registry /var/lib/thoxos-g/registry
COPY --from=demo /etc/thoxos-g /etc/thoxos-g
COPY --from=demo /usr/share/thoxos-g /usr/share/thoxos-g

# Host overlay (all targets), then the target and desktop layers.
COPY overlay/ /
COPY overlay-azure/ /tmp/thoxos-overlay-azure/
COPY --from=desktop-assets /gen/ /tmp/thoxos-overlay-desktop/
COPY thox /usr/local/bin/thox
COPY thox_ai_relay.py /usr/lib/thoxos-g/thox_ai_relay.py

# The KnightHub admin password arrives as the BuildKit secret "admin_password"
# so it never lands in image history. Without it the account gets "thoxos",
# expired: the first login must set a new password. Azure images carry no
# login account at all: cloud-init creates the administrator at deployment.
COPY configure-host.sh /usr/lib/thoxos-g/configure-host.sh
RUN --mount=type=secret,id=admin_password,required=false \
    TARGET="$TARGET" DESKTOP="$DESKTOP" HOST_VERSION="$HOST_VERSION" THOXOS_VERSION="$THOXOS_VERSION" \
    bash /usr/lib/thoxos-g/configure-host.sh
