# ThoxOS Ginux Edition build entry points.
#
#   make test          unit tests and static checks (no QEMU, no Docker)
#   make ci            local CI gate (make test, logged); ci-report also posts a GitHub commit status
#   make efi           patched GINUX.EFI on this machine -> build/dist/
#   make userspace     ThoxOS userspace image -> build/userspace.tar
#   make demo-image    Docker demo image thoxos-g/demo:$(VERSION)
#   make demo          interactive console in Docker (systemd boot)
#   make demo-shell    interactive ThoxOS shell in Docker (no systemd)
#   make demo-web      browser console on http://127.0.0.1:7681
#   make selftest      headless boot gate in Docker (systemd welcome + login)
#   make ssd-image     KnightHub external-SSD disk image -> build/ssd/ (DESKTOP=desktop for ThoxOS Desktop)
#   make azure-image   Azure VHD (fixed, MiB-aligned) -> build/azure/ (AZURE_DESKTOP=desktop|headless)
#   make azure-boot    boot the Azure VHD in QEMU, check it, capture the desktop over RDP
#   make clean
#
# Behind a TLS-inspecting proxy: EXTRA_CA=/path/to/ca.pem make demo-image

SHELL := /bin/bash
VERSION := $(shell cat VERSION)
HOST_VERSION := $(shell cat HOST_VERSION)
DOCKER ?= docker
DEMO_IMAGE := thoxos-g/demo:$(VERSION)
USERSPACE_IMAGE := thoxos-g/userspace:$(VERSION)
HOST_IMAGE := thoxos-g/knighthub-host:$(HOST_VERSION)
DESKTOP ?= headless
AZURE_DESKTOP ?= desktop
AZURE_IMAGE := thoxos-g/azure-$(AZURE_DESKTOP)-host:$(HOST_VERSION)
AZURE_SIZE ?= 8G
ROCKY_BASE := $(shell sed -n 's/^ROCKY_BASE=//p' upstream.lock)
EXTRA_CA ?=
comma := ,
SECRET_FLAG := $(if $(EXTRA_CA),--secret id=extra_ca$(comma)src=$(EXTRA_CA),)
KVM_FLAG := $(shell test -c /dev/kvm && echo --device /dev/kvm)
STATE_VOLUME ?= thoxos-g-state
SHELL_SOURCES := $(wildcard scripts/*.sh docker/*.sh installer/*.sh installer/host/*.sh azure/*.sh \
	installer/host/overlay/usr/lib/thoxos-g/*.sh azure/overlay/usr/lib/thoxos-g/*.sh installer/host/overlay/usr/local/bin/thoxos-ginux \
	desktop/bin/thoxos-ask desktop/bin/thoxos-looks-menu desktop/bin/thoxos-hold desktop/overlay/usr/lib/thoxos-desktop/*.sh tests/e2e/*.sh)
SSD_SIZE ?= 8G
ADMIN_PASSWORD_FILE ?=

.DEFAULT_GOAL := help
.PHONY: help test ci ci-report efi userspace demo-image demo demo-shell demo-web selftest ssd-image azure-image azure-boot clean

help:
	@sed -n '3,18p' Makefile | sed -e 's/^#$$//' -e 's/^# //'

test:
	python3 -m pytest -q tests
	for f in $(SHELL_SOURCES); do bash -n "$$f" || exit 1; done
	@if command -v shellcheck >/dev/null; then \
		shellcheck -x $(SHELL_SOURCES); \
	else echo "shellcheck not installed; skipped"; fi

ci:
	bash scripts/local-ci.sh $(if $(FULL),--full,)

ci-report:
	bash scripts/local-ci.sh --report $(if $(FULL),--full,)

efi:
	bash scripts/ginux-source.sh build/ginux-src
	bash scripts/make-local-ca.sh build/pki build/ginux-src
	bash scripts/build-efi.sh build/ginux-src build/dist

userspace:
	mkdir -p build
	$(DOCKER) build -f rootfs/Containerfile --build-arg ROCKY_BASE=$(ROCKY_BASE) \
		--build-arg THOXOS_VERSION=$(VERSION) -t $(USERSPACE_IMAGE) rootfs
	$(DOCKER) save -o build/userspace.tar $(USERSPACE_IMAGE)

demo-image: userspace
	$(DOCKER) build $(SECRET_FLAG) -f docker/Dockerfile --build-arg THOXOS_VERSION=$(VERSION) \
		-t $(DEMO_IMAGE) .

demo:
	$(DOCKER) run -it --rm $(KVM_FLAG) -v $(STATE_VOLUME):/var/lib/thoxos-g/state $(DEMO_IMAGE) console

demo-shell:
	$(DOCKER) run -it --rm $(KVM_FLAG) -v $(STATE_VOLUME):/var/lib/thoxos-g/state $(DEMO_IMAGE) shell

demo-web:
	$(DOCKER) run --rm $(KVM_FLAG) -p 127.0.0.1:7681:7681 \
		-v $(STATE_VOLUME):/var/lib/thoxos-g/state $(DEMO_IMAGE) web

selftest:
	$(DOCKER) run --rm $(KVM_FLAG) -e THOXOS_G_BOOT_TIMEOUT=$${THOXOS_G_BOOT_TIMEOUT:-1800} \
		$(DEMO_IMAGE) selftest

ssd-image: demo-image
	bash installer/build-ssd-image.sh --desktop $(DESKTOP) --demo-image $(DEMO_IMAGE) --host-image $(HOST_IMAGE) \
		--size $(SSD_SIZE) --out build/ssd $(if $(EXTRA_CA),--extra-ca $(EXTRA_CA),) \
		$(if $(ADMIN_PASSWORD_FILE),--admin-password-file $(ADMIN_PASSWORD_FILE),)

azure-image: demo-image
	bash installer/build-host-image.sh --target azure --desktop $(AZURE_DESKTOP) --demo-image $(DEMO_IMAGE) \
		--host-image $(AZURE_IMAGE) --size $(AZURE_SIZE) --out build/azure $(if $(EXTRA_CA),--extra-ca $(EXTRA_CA),)

azure-boot:
	bash tests/e2e/boot-azure-image.sh build/azure/thoxos-ginux-azure-$(AZURE_DESKTOP)-$(HOST_VERSION).vhd \
		build/e2e-azure $${GINUX_WAIT:-0}

clean:
	rm -rf build
