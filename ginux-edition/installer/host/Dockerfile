# ThoxOS Ginux Edition KnightHub host root filesystem.
#
# A minimal Debian 13 host that boots from the external SSD on real hardware
# (NVMe, USB, NIC, GPU stay with the Linux kernel) and runs the Ginux kernel
# under KVM with the validated QEMU profile, console on tty1. Ginux itself has
# no NVMe, USB or physical NIC drivers yet, so this hosted path is the working
# way to boot ThoxOS Ginux Edition on KnightHub.
#
# Built by installer/build-ssd-image.sh; the result is exported, not run.

ARG DEBIAN_IMAGE=docker.io/library/debian:trixie@sha256:2dc419c6d7fe3dad0a2f9fd469c34cc90b0f9ba642d8fde837fe3d7d34a0e7f1
ARG DEMO_IMAGE=thoxos-g/demo:0.1.0

FROM ${DEMO_IMAGE} AS demo

FROM ${DEBIAN_IMAGE} AS host
ARG THOXOS_VERSION=0.1.0
ENV DEBIAN_FRONTEND=noninteractive

# Kernel, boot loader, systemd and firmware for common desktop NICs and GPUs.
# initramfs-tools with MODULES=most keeps USB storage (uas, usb-storage, xhci)
# in the initrd so the root file system on the external SSD is found.
RUN echo "deb http://deb.debian.org/debian trixie non-free-firmware" >/etc/apt/sources.list.d/firmware.list \
 && echo "deb http://deb.debian.org/debian trixie-backports main" >/etc/apt/sources.list.d/backports.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      systemd systemd-sysv systemd-resolved systemd-timesyncd dbus udev kmod \
      linux-image-amd64 initramfs-tools systemd-boot-efi \
      firmware-realtek firmware-misc-nonfree firmware-intel-misc \
      ovmf python3 dnsmasq-base ca-certificates util-linux passwd procps \
      sudo less nano iproute2 iputils-ping cloud-guest-utils e2fsprogs dosfstools \
      kbd console-setup locales \
 && apt-get install -y --no-install-recommends -t trixie-backports qemu-system-x86 \
 && rm -rf /var/lib/apt/lists/*

# ThoxOS runtime from the demo image: one source of truth for GINUX.EFI, the
# seeded registry, its TLS leaf, and the thoxos-g driver.
COPY --from=demo /usr/lib/thoxos-g /usr/lib/thoxos-g
COPY --from=demo /usr/bin/thoxos-g /usr/bin/thoxos-g
COPY --from=demo /usr/local/bin/registry /usr/local/bin/registry
COPY --from=demo /usr/local/bin/ttyd /usr/local/bin/ttyd
COPY --from=demo /var/lib/thoxos-g/registry /var/lib/thoxos-g/registry
COPY --from=demo /etc/thoxos-g /etc/thoxos-g
COPY --from=demo /usr/share/thoxos-g /usr/share/thoxos-g

# Host overlay: systemd units, network, kernel hooks, configuration.
COPY overlay/ /

# The admin password arrives as the BuildKit secret "admin_password" so it never
# lands in image history. Without it the account gets "thoxos", expired: the
# first login must set a new password.
RUN --mount=type=secret,id=admin_password,required=false set -eu; \
    admin_password=thoxos; \
    if [ -s /run/secrets/admin_password ]; then admin_password="$(head -n1 /run/secrets/admin_password)"; fi; \
    echo 'MODULES=most' >/etc/initramfs-tools/conf.d/thoxos-g-modules; \
    printf '%s\n' uas usb_storage xhci_pci xhci_hcd nvme ext4 vfat >>/etc/initramfs-tools/modules; \
    kernel="$(ls /lib/modules | sort -V | tail -1)"; \
    update-initramfs -c -k "$kernel" >/dev/null 2>&1 || update-initramfs -u -k "$kernel"; \
    test -s "/boot/initrd.img-$kernel"; \
    test -s /usr/lib/systemd/boot/efi/systemd-bootx64.efi; \
    # /etc/hostname, /etc/hosts and /etc/resolv.conf are bind mounts during a
    # Docker build; installer/assemble-disk.sh writes them into the disk image.
    sed -i 's/^# *en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen && locale-gen >/dev/null; \
    useradd --system --no-create-home --shell /usr/sbin/nologin thoxos-registry; \
    useradd --create-home --shell /bin/bash --groups kvm thoxos; \
    useradd --create-home --shell /bin/bash --groups sudo,kvm,adm,systemd-journal thox; \
    printf 'thox:%s\n' "$admin_password" | chpasswd; \
    chage -d 0 thox; \
    passwd -l root >/dev/null; \
    chown thoxos-registry:thoxos-registry /etc/thoxos-g/tls/registry.key; \
    chmod 0600 /etc/thoxos-g/tls/registry.key; \
    mkdir -p /var/lib/thoxos-g/state /boot/efi; \
    chown thoxos:thoxos /var/lib/thoxos-g/state; \
    chmod 0750 /var/lib/thoxos-g/state; \
    chmod 0755 /usr/lib/thoxos-g/*.sh /etc/kernel/postinst.d/zz-thoxos-g-esp /etc/initramfs/post-update.d/zz-thoxos-g-esp; \
    systemctl enable systemd-networkd systemd-resolved systemd-timesyncd \
        thoxos-g-dns.service thoxos-g-registry.service thoxos-g-console.service \
        thoxos-g-growroot.service >/dev/null; \
    systemctl mask getty@tty1.service >/dev/null; \
    systemctl set-default multi-user.target >/dev/null; \
    printf '%s\n' "$THOXOS_VERSION" >/usr/share/thoxos-g/HOST_VERSION; \
    cd /usr/lib/thoxos-g && sha256sum -c GINUX.EFI.sha256
