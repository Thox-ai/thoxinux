# ThoxOS Ginux Research Edition

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE) [![Stage: Research candidate](https://img.shields.io/badge/stage-research_candidate-orange.svg)](docs/THOX_Ginux_Research_Guide.pdf)

THOX-branded Ginux research source with Docker/QEMU launchers, verified-payload installation on an existing Linux SSD host, a source-pinned host-image integration builder and actual validation evidence.

**Your AI. Your Data. Your Rules.™**

## Readiness

The original THOX EFI was built and booted under QEMU TCG. Controller commands, clean shutdown and saved configuration recovery passed. Nine upstream library packages passed 53 tests, launcher guards passed 10 tests and SSD integration passed 15 tests.

Starting the embedded Linux domain panics in both THOX and pristine upstream in the tested environment. Docker execution, KVM, full Linux host-image construction and physical KnightHub boot remain unrun. Fresh-media installation is blocked by the current host-image/writer layout mismatch. No SSD was written.

This is a controller and architecture research candidate. The external SSD host remains Linux. No graphical Ginux desktop, NVIDIA/CUDA, native USB/NVMe or deployed THOX AI/mesh/workspace services are claimed.

## Quick start

From this source checkout, build and launch with Docker Engine/Desktop and Compose v2:

```bash
cd module-ginux
docker compose build
docker compose run --rm ginux
```

At `ginux>` enter `status`, `components`, `domain list` and `help`, then `shutdown` for a clean exit. The default profile uses one vCPU, 2 GiB RAM and an explicit 48-bit virtual IOMMU. Persistent guest storage is a sparse 64 GiB ordinary file. Docker execution is a prepared workflow and has not been validated in this session.

Git contains build receipts, checksums and attribution. The originally tested EFI is distributed in the verified installation kit rather than checked into Git. Its SHA-256 is `4fd25157b9f0348346a56fcb3e8d51d29414094f0f3aaa533ffddb52932e69e8`.

See [module build instructions](module-ginux/README.md), [SSD host integration](ssd-module/README.md) and [fresh-media limits](ssd-module/docs/EXTERNAL_SSD.md). The postboot installer never repartitions, flashes, changes firmware or reboots.

## Documentation and actual evidence

- [Illustrated PDF guide](docs/THOX_Ginux_Research_Guide.pdf)
- [HTML guide and authentic controller transcript](docs/html/THOX_Ginux_Research_Guide.html)
- [Installation-kit QuickStart](START_HERE.md), applicable to the original kit containing the EFI
- [Validation summary](evidence/VALIDATION_SUMMARY.json)
- [Delivered-payload QEMU receipt](evidence/qemu-delivered-payload.json)
- [Configuration recovery receipt](evidence/qemu-recovery.json)
- [Pristine upstream failure comparison](evidence/qemu-upstream-domain.json)

These guides distinguish actual CLI tests, fixtures, architecture illustrations and unrun hardware validation. No stable release has been issued.

## Source, ownership and license

Extracted from the research module in `ttracx/thoxos-desktop-debian` commit `1390b8a18334e91d03725b177c813760f4b38579`. The predecessor evidence and image-lane boundaries remain intact.

Ginux upstream is `gmkurtzer/ginux` commit `36503bda2d87465765e1b94e65f9d100f27ed5be`, Apache-2.0. The upstream kernel remains independently owned. THOX additions are the banner, packaging, integration and documentation. Preserve component notices and source manifests. See [LICENSE](LICENSE), [NOTICE.md](NOTICE.md) and [module provenance](module-ginux/SOURCE_MANIFEST.json).

Copyright 2026 THOX.ai LLC for original THOX work. Private engineering repository; no public publication or physical acceptance is implied.

## Internal engineering continuity

[Agent pickup](AGENTS.md) and [handoff](.agents/HANDOFF.md). Keep these instructions out of user installation archives.
