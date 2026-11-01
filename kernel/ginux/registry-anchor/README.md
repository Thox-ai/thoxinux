# Registry anchor (pinned)

`thoxos-local-root.pem` is the public certificate only for the ThoxOS
Ginux Local Registry Root used by release builds. It contains no
private key: verify with `grep -c "PRIVATE KEY" thoxos-local-root.pem`
(returning 0) and by the single `BEGIN CERTIFICATE` block.

Provenance: this is Payload U's own root certificate, generated during
the Payload U build by the edition lane's per-build CA step and retained
at the build host under `ca-u1/`. Its SHA-256 is
8ba5d94faafde8ee8df7fbc8bad6d97121f448eff3ed94f709c7205edcb6a149.
Wave 3 proved that two builds installing this exact certificate are
byte-identical under the other release controls (see
docs/RELEASE-BUILD.md in this module and the Wave 3 record in
docs/WAVES.md at the repository root).

Why it is pinned: the kernel embeds this certificate, so a fresh random
root per build changes the EFI bytes every time. Pinning the public
certificate makes release builds reproducible. The corresponding root
private key was destroyed by the CA generation script at creation time
and does not exist; no new certificates can be issued under this root.
That is the intended posture for an engineering preview whose registry
trust is a fixed, published anchor.

Rotation: replacing this file changes all future EFI bytes. A rotation
is a deliberate release decision: generate a new root, replace this
file, record the new SHA-256 here and in the release notes, and expect
a different EFI SHA-256 from that build onward.
