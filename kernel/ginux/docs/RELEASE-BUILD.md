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
   verification build (for example `/mnt/d/w5-d-build/src`), wiped and
   recreated between runs. Wave 3 found no build-path strings in the
   EFI, but the control is kept so the procedure matches the proof.

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
kernel/ginux/scripts/build-unified.sh /path/to/fixed/src /path/to/out
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

1. Build once from a clean tree at the fixed path. Record the exit
   code, duration, and `sha256sum GINUX.EFI`.
2. Wipe the source and output trees. Build again at the same fixed
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
