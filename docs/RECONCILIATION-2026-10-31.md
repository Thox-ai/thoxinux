# Reconciliation update: one patch series, one EFI identity (2026-10-31)

This record closes the two-implementation split preserved in docs/RECONCILIATION_2026-10-29.md. The original record is unchanged and keeps its provenance. From this date, ThoxInux has ONE patch series and ONE kernel identity. Historical numbers keep their lane and payload labels forever; they are not retroactively merged.

## The two predecessor sets

| Lane | Patches | EFI identity | Evidence home |
|---|---|---|---|
| module-ginux (Azure Compute) | thox-banner, thox-azure-profile, thox-kernel-startup (series file order) | Research banner plus Azure Compute profile line; EFIs of 12,497,920 B (Oct 28 record) and 12,507,648 B (0.2.0 Azure candidate) | evidence/azure/, kernel/ginux/artifacts/ receipts |
| ginux-edition | 0001 QEMU tools, 0002 controller identity line, 0003 registry anchor | Edition identity line after the upstream banner; separate binaries per its benches | userspace/ginux-edition/docs/ evidence |

## How each difference was resolved

1. **Identity (the only true conflict).** All three identity patches touch control-plane/runtime/src/main.rs. The module banner and Azure profile apply in series; the edition identity patch does NOT apply after them (verified 2026-10-31: git apply fails at main.rs:515 on the combined tree). Resolution: a single new patch, `thox-identity.patch`, hand-merged from all three, producing one identity block before the upstream banner: product identity (ThoxInux 0.9.0, ThoxOS Core, THOX.ai LLC), the engineering-preview line, the upstream attribution line, and one build-profile line ("ThoxInux unified (standalone UEFI)"). The Azure-specific profile line and the edition after-banner line are superseded. Both predecessor designs kept the upstream banner byte-identical; the unified patch keeps that property, so upstream console tests still match. The three originals are preserved at kernel/ginux/patches-legacy-module/ and userspace/ginux-edition/patches-legacy-edition/ as the record of what was merged.
2. **Kernel startup (module lane only).** `thox-kernel-startup.patch` has no edition counterpart and carries over unchanged as the first patch in the unified series.
3. **QEMU tools (edition 0001).** Host tooling only, no kernel overlap. Carries over as `thox-qemu-tools.patch`.
4. **Registry anchor (edition 0003).** Touches services/network/src/registry.rs, no overlap with the module set. Carries over as `thox-registry-anchor.patch`. This is the one functional (not cosmetic) edition change in the kernel identity, and it is why the unified EFI is a new identity rather than a rename of the Azure candidate: the unified EFI's network trust behavior differs from Payload A.

## The unified series (kernel/ginux/patches/series)

1. thox-kernel-startup.patch
2. thox-identity.patch
3. thox-qemu-tools.patch
4. thox-registry-anchor.patch

Verified 2026-10-31: the series applies cleanly in order to a pristine checkout of gmkurtzer/ginux @ 36503bda, and prepare_source.py's byte-exact verification passes for the prepared tree used by the unified build.

## Payload naming from here

- **Payload A**: the recorded module-ginux Azure candidate EFI and its receipts (pre-consolidation).
- **Payload B**: the Oct 28 research EFI (historical record only).
- **Payload E**: ginux-edition binaries and images (desktop, Docker demo, VHD benches).
- **Payload U**: the unified ThoxInux EFI built from this series. All new kernel claims cite Payload U with its build receipt and SHA-256.

## What did not converge

- The two Azure deployment variants (root azure/ Trusted Launch design vs ginux-edition Standard security) remain separate products with separate security models, now documented under docs/deployment-azure/ and userspace/ginux-edition/azure/. They are deployment shapes, not kernel identities, and forcing them together would falsify both.
- The desktop VHD line (Payload E) remains the experience reference. The v0.9 kernel story is the standalone EFI (Payload U); the host-wrapped desktop demo is a developer tool, not the release boot path.
