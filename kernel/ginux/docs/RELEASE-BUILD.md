# Controlled release build procedure

This is the release build procedure for the unified Ginux kernel line
(`scripts/build-unified.sh`). It encodes the controls that Wave 3 proved
make the build byte-reproducible, as defaults, so a release build needs
no manual arguments beyond source and output directories.

## Defaults (no manual control arguments)

1. SOURCE_DATE_EPOCH: `build-unified.sh` exports `SOURCE_DATE_EPOCH`
   from `GINUX_SOURCE_DATE_EPOCH` in `upstream.env` unless the caller
   already set it. The pinned value is 1793077647, the timestamp of the
   upstream pin commit 36503bda2d87465765e1b94e65f9d100f27ed5be. This
   fixes the PE TimeDateStamp and the LLD RSDS debug GUID derived from
   it. The script logs whether the value came from the pin or the caller.
2. Registry anchor: with no `EXISTING_ROOT_PEM` argument (argument 4),
   the build installs the pinned public certificate at
   `registry-anchor/thoxos-local-root.pem` (SHA-256
   8ba5d94faafde8ee8df7fbc8bad6d97121f448eff3ed94f709c7205edcb6a149,
   certificate only, no private key; see that directory's README.md).
   The script logs `registry anchor mode=pinned-default`.
3. Fixed build path: use the same absolute source path for every
   verification build, wiped and recreated between runs. The canonical
   release path is `/mnt/d/thoxinux-build/repro/run-fixed/src`, the
   path Wave 3 used for its controlled builds. Wave 5 measured why the
   path matters: two new-default builds at a different fixed path were
   byte-identical to each other but differed from the Wave 3 hash in
   exactly 8 bytes, a single cluster at file offset 1652532-1652539,
   the first 8 bytes of the RSDS debug GUID, with identical
   TimeDateStamp and identical intermediates (initramfs, generated
   boot code, network service). A third build with the new defaults at
   the canonical path reproduced the Wave 3 hash exactly. The path
   therefore leaks through the RSDS GUID (a hash over linker debug
   data that embeds absolute paths), not through any path string in
   the EFI; Wave 3's strings scan could not see this channel. Same
   path is a hard requirement, and matching a published hash requires
   the canonical path.

## Opt-outs and overrides

- Explicit anchor: pass a different root PEM as argument 4. The script
  logs `registry anchor mode=explicit-arg`. Use only with a recorded
  reason; the resulting EFI will differ from the pinned-anchor build.
- Fresh CA (development only): set `THOX_BUILD_FRESH_CA=1` in the
  environment with no argument 4. The build then generates a fresh
  per-build registry CA exactly as the pre-Wave-5 script did, and logs
  `registry anchor mode=fresh-ca`. Bytes will differ on every build.
  Never use this mode for a release.
- Caller SOURCE_DATE_EPOCH: set it in the environment to override the
  pin default. The script logs the caller value. Release builds should
  not override it.

## Build

```bash
kernel/ginux/scripts/build-unified.sh /mnt/d/thoxinux-build/repro/run-fixed/src /path/to/out
```

A successful run exits 0. The output directory contains `GINUX.EFI`,
`GINUX_LICENSE`, `GINUX_NOTICE`, `build-receipt.json`, and `SHA256SUMS`
covering all four. The receipt records the EFI SHA-256, the upstream
commit, toolchain versions, every patch hash in `patches/series`
(including `thox-identity.patch` under `identity_patch_sha256`), and
the Cargo lockfile hash.

Historical note: before Wave 5 the receipt step referenced a legacy
`thox-banner.patch` that does not exist in the unified series, so the
script exited 1 after copying the EFI. That wart is fixed; exit 1 from
a release build is now a real failure.

## Verification procedure

1. Build once from a clean tree at the canonical path. Record the exit
   code, duration, and `sha256sum GINUX.EFI`.
2. Wipe the source and output trees. Build again at the same canonical
   path with the same defaults and no manual control arguments.
3. Compare: the two EFI SHA-256 values must be identical, and
   `cmp GINUX.EFI <second-build>/GINUX.EFI` must report no differences.
4. Publish the EFI SHA-256 as the verification hash beside the release.
   Anyone with this repository, the pinned toolchain, and this
   procedure can reproduce the same bytes and check the hash.

## Claim limits

Reproducibility is proven on the build host class and toolchain pinned
in `upstream.env` (in-tree rustc 1.99.0, clang 21). A different
toolchain is a different build until measured. This procedure says
nothing about hardware acceptance: see the release notes for the
evidence scope and the Secure Boot posture.
