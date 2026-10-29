# Quick start

Every command below ran during validation on 2026-10-28 and 2026-10-29 (Ubuntu 24.04 build host, Docker 29.9, no KVM; the SSD writer on a loop device). Times are from those runs; KVM hosts are faster.

## 1. Build the demo image (compiles Ginux the first time)

```bash
git clone -b ginux-edition-0.1.0 https://github.com/ttracx/thoxos-ginux.git
cd thoxos-ginux/ginux-edition
make test
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
make ssd-image
sudo installer/install-to-ssd.sh --image build/ssd/thoxos-ginux-knighthub-0.1.0.img --device /dev/sdX
```

Then on KnightHub: disable Secure Boot, plug in the SSD, open the boot menu, pick the SSD's UEFI entry. tty1 shows the ThoxOS console; Ctrl-Alt-F2 is the host admin login (user `thox`, first login sets a new password).

The writer refuses a disk labeled THOXOS (the ThoxOS Vibe SSD) unless you add `--erase-existing-thoxos`. Use a spare SSD unless you mean to replace Vibe.
