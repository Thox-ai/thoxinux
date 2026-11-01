# ThoxInux user guide

For people running ThoxInux, not building it. Build and development: docs/QUICKSTART.md and docs/DEVELOPMENT.md.

## What ThoxInux is

ThoxInux is the open-source core of ThoxOS: a Rust-first kernel (a fork of Ginux) that runs a Linux userspace, plus the ThoxOS shell, local chat, files, devices, search and the agent supervisor. It runs completely on your own machine. Local, offline and LAN use needs no THOX account and no THOX cloud. Services THOX operates (remote access, off-site backup, fleet features) are optional add-ons, now and by design.

Your AI. Your Data. Your Rules.™

## What you can do today (v0.9, engineering preview)

- Boot ThoxInux from the EFI image in QEMU, or from the external SSD image on a supported x86-64 machine with Secure Boot off (v0.9 posture; see Limitations).
- Use the controller console: `help` lists commands; `status` shows the running system, domains and configuration; configuration persists across reboots in the saved profile.
- Run the interactive ThoxOS shell (Docker demo or SSD image) and the working commands `thox version` and `thox status`.
- Run agents under the supervisor (developer preview): agents start only with a verified signed identity, work through a tool broker limited by their grants, and everything they do lands in an audit log you can read.

## The agent rules, in plain language

1. An agent cannot start unless its identity checks out.
2. An agent can only use the tools and folders its grant lists. The default is read-only, and network access is off unless granted.
3. If an agent asks for something outside its grant, the answer is no, and the refusal is written to the audit log too.
4. You can read the audit log at any time and revoke an agent's grant without its permission.

## Supported in v0.9

- Architecture: x86-64 only. ARM64 is planned for v1.1 and is not in this release.
- Validated environment: QEMU Q35 with OVMF (KVM or TCG), 2 GiB RAM, 1 vCPU profile for the kernel console; the desktop and shell images carry their own bench records in userspace/ginux-edition/docs/.
- Userspaces proven upstream: Rocky Linux 10 (systemd to multi-user.target) and Alpine Linux programs. See docs/COMPATIBILITY.md for the honest syscall matrix.

## Limitations, stated plainly

- Engineering preview. Not production ready, not a Linux replacement, and not yet independently security reviewed.
- Physical hardware is unvalidated except as recorded in the evidence files. Bare-metal driver coverage (storage, network, GPU) is the largest unknown.
- Secure Boot: v0.9 requires Secure Boot off. A signed boot path lands in a later phase.
- No MeshStack in this release. MeshStack is a proprietary THOX technology and ships separately; ThoxInux works fully without it for local use.

## Getting help

During the private staging period: tommy@thox.ai. When the repository is public, use GitHub Issues and Discussions on this repository.
