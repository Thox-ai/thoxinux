# ThoxOS Ginux Azure Compute Edition

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE) [![Stage: Research candidate](https://img.shields.io/badge/stage-research_candidate-orange.svg)](docs/THOX_Ginux_Research_Guide.pdf)

**Current Azure variant:** [Start here](docs/azure/START_HERE.md) · [PDF guide](docs/azure/THOX_Ginux_Azure_Deployment_Guide.pdf) · [HTML guide](docs/azure/html/THOX_Ginux_Azure_Deployment_Guide.html) · [Deployment commands](azure/README.md)

Version `0.2.0-azure-candidate` builds the independent Ginux Rust kernel with THOX branding and startup fixes, packages the compiled EFI with verified provenance, and supplies a private Azure Compute deployment. Ubuntu 24.04 Gen2 remains the Azure host; QEMU TCG runs THOX Ginux inside that host. Docker/QEMU and external Linux SSD host workflows remain available.

**Your AI. Your Data. Your Rules.™**

## Readiness

The final customized THOX Azure EFI was built and passed 22 real local QEMU commands across a cold boot and a second boot on the same guest volume. Embedded `/sbin/init` starts, detached execution reports PID 100, stop/start/restart and failure recovery work, and clean shutdown and saved-configuration recovery pass. See [current validation](docs/azure/validation.json) and the [payload-bound lifecycle receipt](evidence/azure/lifecycle-results.json).

The fixes reserve the complete Linux auxiliary-vector stack layout, separate local TCP lifetime from network-backed sockets, repair detached output and restart behavior, and align invalid mount-pointer fixtures with existing owned-namespace validation. These results cover the tested embedded minimal userspace workflow, not broad Linux application compatibility.

120 unit checks pass across the kernel stack (5), upstream libraries (53), module (17), SSD (15) and Azure (30) lanes; formatting and clippy with warnings denied pass. These are separate from the 22 actual guest commands. The Azure module also has locked-schema checks. The untouched strict Microsoft.Resources schema result fails; 13 checks pass only with two documented schema adaptations. [The schema receipt](azure/ARM_SCHEMA_VALIDATION.json) preserves both results. Azure authentication, server-side ARM validation, what-if, deployment, cloud bootstrap and Compute Gallery capture have **not run** here.

Docker execution, KVM, full Linux SSD host-image construction and physical KnightHub boot remain unrun. Fresh-media installation is blocked by the historical host-image/writer layout mismatch; no SSD was written. This remains an engineering candidate. The SSD host remains Linux. No graphical Ginux desktop, native Azure Ginux boot, Windows Azure Virtual Desktop session host, NVIDIA/CUDA, native USB/NVMe or deployed THOX AI/mesh/workspace services are claimed.

## Quick start

From this source checkout, build and launch with Docker Engine/Desktop and Compose v2:

```bash
cd module-ginux
docker compose build
docker compose run --rm ginux
```

At `ginux>` enter `status`, `components`, `domain list` and `help`, then `shutdown` for a clean exit. The default profile uses one vCPU, 2 GiB RAM and an explicit 48-bit virtual IOMMU. Persistent guest storage is a sparse 64 GiB ordinary file. Docker execution is a prepared workflow and has not been validated in this session.

The accepted EFI is 12,507,648 bytes, SHA-256 `3ebcc9043ef9dc8b7e75abc15b113a5810c8d39c0ad47143476a41caed24d5ba`. Its build-receipt SHA-256 is `c4ac916269f053a689801af6a9214b6613090a35bd0a247eeb3e2d10d6ccf31b`.

Git contains source, patch series, build receipts, checksums and attribution. Compiled `GINUX.EFI` is deliberately excluded from Git. Build it locally or use the compiled payload in the separately delivered `THOX_Ginux_Azure_Release.zip`; a source-only ZIP is not the runtime release. The October 28 EFI SHA-256 `4fd25157b9f0348346a56fcb3e8d51d29414094f0f3aaa533ffddb52932e69e8` identifies the historical installation kit only.

See [module build instructions](module-ginux/README.md), [SSD host integration](ssd-module/README.md) and [fresh-media limits](ssd-module/docs/EXTERNAL_SSD.md). The postboot installer never repartitions, flashes, changes firmware or reboots.

## Azure deployment and host image

Follow [Azure Start Here](docs/azure/START_HERE.md) to package the built EFI and supply the explicit subscription, resource group, Ubuntu image version, private artifact container and administrator public key. The infrastructure uses `Standard_D4s_v5`, Trusted Launch, Secure Boot/vTPM, accelerated networking, no VM public IP and explicit outbound NAT. A user-assigned managed identity downloads the private SHA-256-pinned ZIP. Default acceptance access uses Azure Run Command; private SSH and billable Standard Bastion are explicit options.

The linked Microsoft master-image article describes Windows Azure Virtual Desktop. This project uses a Linux host image lifecycle. [Linux master-image capture](azure/CAPTURE_MASTER_IMAGE.md) is manual and follows live host acceptance. Deployment does not automatically generalize a VM, create an AVD pool or publish an image.

## Historical research evidence

The following artifacts describe the **October 28 predecessor**, including its embedded-domain panic. They remain unchanged for audit and do not describe the current patched payload.

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

Ginux upstream is `gmkurtzer/ginux` commit `36503bda2d87465765e1b94e65f9d100f27ed5be`, Apache-2.0. The kernel remains attributed to its upstream authors. THOX work includes the research/Azure banners, documented startup corrections, packaging, integration and documentation. Preserve component notices, patch provenance and source manifests. See [LICENSE](LICENSE), [NOTICE.md](NOTICE.md) and [module provenance](module-ginux/SOURCE_MANIFEST.json).

Copyright 2026 THOX.ai LLC for original THOX work. Private engineering repository; no public publication or physical acceptance is implied.

## Internal engineering continuity

[Agent pickup](AGENTS.md) and [handoff](.agents/HANDOFF.md). Keep these instructions out of user installation archives.

## Governance and releases

This private engineering candidate is reviewed through source changes and evidence-bound acceptance. Public publication, production qualification and physical boot require their own actual review and evidence. The [releases page](https://github.com/ttracx/thoxos-ginux/releases) contains no stable release from this build; deployment downloads are supplied with separate exact payload receipts.

## Introduction and recorded demos

See the [solution introduction, actual screen recordings and labeled user scenes](docs/azure/media/README.md), with [download provenance](docs/azure/media/DELIVERY_MANIFEST.json). The source-bound media package and five-email introduction were delivered privately to Tommy and Craig.
