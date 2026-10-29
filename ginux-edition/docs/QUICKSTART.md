# Quick start

Every command below ran during validation on 2026-10-28 and 2026-10-29 (Ubuntu 24.04 build host, 2 vCPU, Docker 29.9, no KVM; the SSD writer on a loop device). Times are from those runs; KVM hosts are faster. Publishing to and deploying on Azure did not run here and are in [AZURE.md](AZURE.md).

## 1. Build the demo image (compiles Ginux the first time)

```bash
git clone -b ginux-edition-0.2.0 https://github.com/ttracx/thoxos-ginux.git
cd thoxos-ginux/ginux-edition
make test
make ci                                   # same checks, logged in build/local-ci/
bash scripts/install-pre-push-hook.sh     # optional: run the gate before every push
make demo-image
```

Behind a TLS-inspecting proxy, pass its CA once: `EXTRA_CA=/path/to/ca.pem make demo-image`.

## 2. Prove it boots (53 s without KVM on a 2 vCPU build host)

```bash
make selftest
```

Passes when the console shows `Welcome to ThoxOS 0.1.0 Ginux Edition!`, the ThoxOS issue banner and `login:`. Exit code 0.

## 3. Use it

```bash
make demo-shell    # ThoxOS shell on the Ginux kernel; try: thox status
make demo          # full systemd boot on the console; Ctrl-A then X stops the VM
make demo-web      # the systemd boot in a browser at http://127.0.0.1:7681 (credential in the log)
```

## 4. KnightHub external SSD

```bash
bash installer/build-host-image.sh --target knighthub --desktop headless \
    --demo-image thoxos-g/demo:0.1.0 --host-image thoxos-g/knighthub-host:0.2.0 --size 8G --out build/ssd
bash tests/e2e/boot-ssd-image.sh build/ssd/thoxos-ginux-knighthub-0.2.0.img build/e2e-ssd
sudo installer/install-to-ssd.sh --image build/ssd/thoxos-ginux-knighthub-0.2.0.img --device /dev/sdX
```

`make ssd-image` wraps the first command. The writer ran on a loop device for 0.1.0 (VALIDATION V10), not on a real SSD.

Then on KnightHub: disable Secure Boot, plug in the SSD, open the boot menu, pick the SSD's UEFI entry. tty1 shows the ThoxOS console; Ctrl-Alt-F2 is the host admin login (user `thox`, first login sets a new password).

The writer refuses a disk labeled THOXOS (the ThoxOS Vibe SSD) unless you add `--erase-existing-thoxos`. Use a spare SSD unless you mean to replace Vibe.

## 5. Azure image with ThoxOS Desktop

```bash
bash installer/build-host-image.sh --target azure --desktop desktop \
    --demo-image thoxos-g/demo:0.1.0 --host-image thoxos-g/azure-desktop-host:0.2.0 --size 8G --out build/azure
bash tests/e2e/boot-azure-image.sh build/azure/thoxos-ginux-azure-desktop-0.2.0.vhd build/e2e-azure 600
```

The build took about 2 minutes with a warm Docker cache (4 minutes when the desktop packages change). The bench boots the VHD in QEMU, provisions it with cloud-init the way Azure would, and writes `build/e2e-azure/report.json` plus screenshots of the splash, the greeter, the RDP login and each look; `600` gives ThoxOS on Ginux ten minutes to boot inside the desktop. Exit code 0 means every check passed. `--desktop headless` builds the SSH-only image; the bench then boots ThoxOS on Ginux for the administrator instead of taking screenshots.

Then publish and deploy from a machine signed in to Azure: [AZURE.md](AZURE.md).
