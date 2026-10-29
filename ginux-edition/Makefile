# ThoxOS Ginux Edition build entry points.
#
#   make test          unit tests and static checks (no QEMU, no Docker)
#   make efi           patched GINUX.EFI on this machine -> build/dist/
#   make userspace     ThoxOS userspace image -> build/userspace.tar
#   make demo-image    Docker demo image thoxos-g/demo:$(VERSION)
#   make demo          interactive console in Docker (systemd boot)
#   make demo-shell    interactive ThoxOS shell in Docker (no systemd)
#   make demo-web      browser console on http://127.0.0.1:7681
#   make selftest      headless boot gate in Docker (systemd welcome + login)
#   make ssd-image     KnightHub external-SSD disk image -> build/ssd/
#   make clean
#
# Behind a TLS-inspecting proxy: EXTRA_CA=/path/to/ca.pem make demo-image

SHELL := /bin/bash
VERSION := $(shell cat VERSION)
DOCKER ?= docker
DEMO_IMAGE := thoxos-g/demo:$(VERSION)
USERSPACE_IMAGE := thoxos-g/userspace:$(VERSION)
HOST_IMAGE := thoxos-g/knighthub-host:$(VERSION)
ROCKY_BASE := $(shell sed -n 's/^ROCKY_BASE=//p' upstream.lock)
EXTRA_CA ?=
comma := ,
SECRET_FLAG := $(if $(EXTRA_CA),--secret id=extra_ca$(comma)src=$(EXTRA_CA),)
KVM_FLAG := $(shell test -c /dev/kvm && echo --device /dev/kvm)
STATE_VOLUME ?= thoxos-g-state
SHELL_SOURCES := $(wildcard scripts/*.sh docker/*.sh installer/*.sh installer/host/overlay/usr/lib/thoxos-g/*.sh tests/e2e/*.sh)
SSD_SIZE ?= 8G
ADMIN_PASSWORD_FILE ?=

.DEFAULT_GOAL := help
.PHONY: help test efi userspace demo-image demo demo-shell demo-web selftest ssd-image clean

help:
	@sed -n '3,15p' Makefile | sed -e 's/^#$$//' -e 's/^# //'

test:
	python3 -m pytest -q tests
	for f in $(SHELL_SOURCES); do bash -n "$$f" || exit 1; done
	@if command -v shellcheck >/dev/null; then \
		shellcheck -x $(SHELL_SOURCES); \
	else echo "shellcheck not installed; skipped"; fi

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
	bash installer/build-ssd-image.sh --demo-image $(DEMO_IMAGE) --host-image $(HOST_IMAGE) \
		--size $(SSD_SIZE) --out build/ssd $(if $(EXTRA_CA),--extra-ca $(EXTRA_CA),) \
		$(if $(ADMIN_PASSWORD_FILE),--admin-password-file $(ADMIN_PASSWORD_FILE),)

clean:
	rm -rf build
