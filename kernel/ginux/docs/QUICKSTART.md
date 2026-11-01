# Ginux research demo QuickStart

This module builds and runs a THOX-branded Ginux serial-console guest in QEMU. Physical KnightHub boot and NVIDIA support are unvalidated. A Linux host on the external SSD supplies the hardware support.

1. Open a terminal in the module directory. Install Docker with Compose v2.
2. Build the demo with `docker compose build`.
3. Run `docker compose run --rm ginux` and wait for `ginux>`.
4. Enter `status`, `components`, `domain list` and `help`. The first guest boot creates a persistent sparse 64 GiB volume.
5. Enter `shutdown` for a clean exit. The Docker volume remains for future runs. Control-C is an emergency stop.

The delivered EFI passed controller and saved-configuration recovery checks under native QEMU. An embedded-domain start panicked in both the THOX and pristine upstream builds. Docker, KVM and KnightHub hardware have not been run here. The following explicit outbound OCI workflow is an unqualified upstream experiment:

```text
domain new alpine
domain set alpine image=alpine:latest init=/bin/sh
domain start alpine --attach
```

Control-] returns to the Ginux controller. This is an upstream workflow example, not evidence that this package passed an Alpine compatibility test.

Export the EFI installer payload without starting a guest:

```bash
docker build --platform linux/amd64 --target artifacts --output type=local,dest=artifacts .
(cd artifacts && sha256sum --strict -c SHA256SUMS)
sha256sum artifacts/build-receipt.json
```

Use the displayed receipt digest with the SSD host installer. See the module README for native-build commands, the KVM override, artifact provenance and claim limits. Do not flash `GINUX.EFI` directly to an external SSD and expect a supported desktop.

Your AI. Your Data. Your Rules.™
