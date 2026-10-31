# Genuine kernel capture

Captured 2026-10-30 America/Chicago (UTC timestamps in receipts), in this ChatGPT runtime. These are real Xterm screen pixels from a newly executing QEMU guest. They are not a transcript animation, generated imagery or footage of a person operating a device. Inputs were automated and paced; responses and kernel behavior came from the actual guest.

The reused compiled EFI is 12,507,648 bytes, SHA-256 `3ebcc9043ef9dc8b7e75abc15b113a5810c8d39c0ad47143476a41caed24d5ba`. Its established build/source provenance is included in the existing Azure runtime release; this run does not claim a new kernel build. The continuation source work does not constitute a new build of this payload.

Cold boot executed eleven checked operator commands: sealed controller status, create/configure a domain, start, running status, restart, contained failure, failed status, start/recover, running status and stop. The recovered boot reused the same local persistent volume and verified retained configuration, start, running status and stop. Each boot then issued shutdown, observed `GINUX_KERNEL_OK` and exited QEMU with status zero. This is fifteen checked operator commands plus two clean shutdowns.

The Xvfb native framebuffer was sampled at 10 fps and encoded to H.264 without audio. Source screenshots at 10/20 seconds are unedited framebuffer pixels. Changing sampled pixel hashes, command timestamps, serial logs and full video decode results are supplied. Both 1920×1080 movies were visually sampled and decoded without an error.

QEMU8.2.2, OVMF2024.02, one virtual CPU,2GiB, Q35, explicit48-bit IntelIOMMU and TCG were used. Dependencies were extracted into a scoped runtime. Xterm used an existing PTY because this environment maps onlyUID/GID0; no product launcher checks were removed. The direct QEMU test harness was used; the product's regular-user launcher was not executed here. X11 needed authenticated loopbackTCP because native Unix sockets are unavailable. A scoped bind shim restricts listeners to loopback. A transient xkbcomp dependency link was removed after capture.

This proves the embedded `minimal-system-v0` kernel lifecycle. It does not establish current desktop, hosted inference, MeshStack, Azure-host, Docker/KVM, externalSSD or physicalKnightHub acceptance. Earlier desktop screenshots in the repository have their separate source and runtime provenance.

Failed setup takes are quarantined outside this delivery. No Xauthority cookie, framebuffer backing file, dependency package, EFI, local guest disk or unrelated material is included.
