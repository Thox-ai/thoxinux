# Integrated continuation: desktop, shell and kernel evidence

Document ID: THOX-GINUX-CONTINUATION-20261030  
Audience: Tommy Xaypanya and Craig Ross  
Owner: Sadie Weaving / current Codex continuation  
Classification: Private engineering documentation  
Status: Engineering preview; source validation and target acceptance are separate  
Evidence date: October 30, 2026 (America/Chicago)

Your AI. Your Data. Your Rules.™

Read the complete illustrated report as [offline HTML](report.html) or [PDF](report.pdf). It includes the prior desktop captures, a fresh authentic guest screenshot, executed source-check results and the remaining target gates.

## What this continuation brings together

The current source combines the root Azure Compute kernel work with the newer Ginux Edition desktop and image implementation. A first-time user can now choose the [desktop, interactive browser shell or kernel lifecycle path](../../README.md#choose-your-experience) without mistaking one implementation's test limits for the other's.

The continuation reviews source preparation, Docker setting propagation, hosted-relay redirect handling and Azure credential setup before promoting the image implementation. Relevant code and tests remain in their owning `ginux-edition/` paths. Read the [current validation receipt](validation.json) and [fresh guest recording](media/live-guest.mp4) for the tests and captures actually rerun. This page does not convert planned or historical tests into new execution.

## Exact source inputs

| Input | Immutable revision | Use |
| --- | --- | --- |
| Existing repository main | `10787b1ae9dc024f069d229e83339876212afc5e` | Root Azure Compute code, preserved original evidence, merged 0.1.0 image implementation |
| Latest image/desktop implementation | `7f8f2007d3ae8da19ddb0309e99ee25904971cd1` | `ginux-edition/` desktop/Azure enhancements and local-CI change; same tree as `98845311dd79f09fb96c25e7e6e9200ece7631ff` |
| Pinned upstream kernel | `36503bda2d87465765e1b94e65f9d100f27ed5be` | Common upstream source; the two patch sets and compiled EFIs remain distinct |

The final remote commit and push/merge readback belong in the post-push receipt. A restored local snapshot has its own Git history; its commit must not be presented as the authenticated remote source SHA.

## Evidence map

| User-visible behavior | Evidence | Boundary |
| --- | --- | --- |
| Desktop splash, login, three looks and Ginux terminal | [Desktop screenshot inventory](../../ginux-edition/docs/DESKTOP.md#screenshots), [0.2.0 bench files](../../ginux-edition/docs/evidence/0.2.0/) | Prior image-team captures from a VHD in QEMU reached over RDP; Azure was not deployed |
| Docker boot, browser shell and ThoxOS commands on Ginux | [Image validation V5, V11, V12, V17 and V18](../../ginux-edition/docs/VALIDATION.md), [user guide](../../ginux-edition/docs/USER_GUIDE.md) | Prior image-team execution; OCI guest patch set and payload differ from the root Azure EFI |
| Desktop/headless VHD and USB-disk image boot | [Image validation V26, V30 and V31](../../ginux-edition/docs/VALIDATION.md) | 23 desktop, 13 headless and 6 USB-disk checks from the prior image team; virtualized image proof, not physical boot |
| Embedded `/sbin/init`, detached status, restart, failure recovery and persistence | [Root Azure lifecycle receipt](../../evidence/azure/lifecycle-results.json), [validation summary](../../evidence/azure/VALIDATION_SUMMARY.json) | Payload-bound QEMU TCG evidence for the root Azure EFI |
| Original Ginux screen recordings and user scenes | [Media introduction](../azure/media/README.md), [manifest](../azure/media/DELIVERY_MANIFEST.json) | Screen recordings are authentic; fictional user scenes retain their synthetic labels |
| Fresh continuation checks and guest capture | [Validation receipt](validation.json), [live guest recording](media/live-guest.mp4) | The receipt identifies the exact executed checks, environment, payload hash and capture limits; the recording uses the root Azure EFI |

Image-team evidence above is reviewed existing evidence, not a claim that this continuation rebuilt its VHDs. Any source changes affecting those images require a new image build and acceptance before redistributing a corrected binary as tested.

## First useful user journey

1. Read the [experience selector](../../README.md#choose-your-experience) and install that path's prerequisites.
2. For interaction, build the Docker image and run `make selftest`, then `make demo-shell`. Confirm `uname -srm`, `thox version` and `thox status` in the real Ginux guest.
3. For the browser shell, bind port 7681 to `127.0.0.1`, set shell mode, and sign in with the generated credential. The standard systemd login path has an upstream getty limitation; use the documented shell path.
4. For the complete desktop, build and boot the VHD in the [QEMU/RDP bench](../../ginux-edition/docs/AZURE.md#build). Inspect login, each look, About and a Ginux terminal before any cloud deployment.
5. Deploy only against an authorized Azure subscription with the intended image and security model. Select and inventory a spare SSD before a physical installation; never infer a target from an old label.

## Current target limits

This continuation environment has no Docker daemon or `/dev/kvm`, and its mount/user namespace operations are denied. A unit-test or shell-harness pass does not replace a Docker or VHD boot test. The connected KnightHub devices are offline. No Azure identity/subscription is configured in this runtime. These facts limit execution here; they do not invalidate the separately preserved image team's results.

Physical SSD write/boot, firmware changes, Windows writer execution, real Azure provisioning, nested KVM, hosted-model inference, and production qualification remain open. The unsigned desktop-image boot chain uses Standard security; the root Ubuntu marketplace-host design uses Trusted Launch. Keep their settings and acceptance separate. No stable Release is inferred from either version file.

## MeshStack proof

There is no established MeshStack runtime integration in this Ginux variant. A Ginux shell recording, desktop screenshot or local relay test is not evidence of distributed inference. MeshStack has its own owning repositories and execution lanes; any future cross-platform demonstration must name the actual coordinator connection, participating nodes, workload and result, and preserve fixture or virtual-profile labels.

## Operating and recovery

Follow the owning [Ginux Edition user guide](../../ginux-edition/docs/USER_GUIDE.md) for VM state, browser access, look switching and recovery, and the root [Azure Compute guide](../azure/START_HERE.md) for its independent payload. Preserve existing guest state and foreign source checkouts. A refused integrity, target, credential or ownership check is a stop signal for that action, not permission to remove a guard.

Current development uses [local CI](../../ginux-edition/docs/DEVELOPMENT.md#continuous-integration) rather than GitHub Actions under the existing cost decision. Successful tests need the exact source revision and log; a status badge, filename or staged artifact alone is insufficient.
