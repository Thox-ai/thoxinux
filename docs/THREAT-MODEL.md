# ThoxInux threat model

Status: v0.9 engineering preview. This model describes the architecture as built and tested, with evidence limits stated. It is not a security certification. An independent security review is Phase 3 of the release plan and has not happened.

## Assets

- The user's data and files inside ThoxOS domains.
- Agent authority: what an agent is allowed to do, and the credentials it holds.
- Device identity and attestation material (ThoxKey; proprietary, outside this repo).
- The integrity of the boot image and of updates.
- The audit log: the user's record of what agents did.

## Principals and trust boundaries

1. **The Ginux kernel (ring 0).** Small, Rust-first, owns processes, address spaces, VFS, networking, scheduling, memory and IPC. Everything else is untrusted relative to it.
2. **Domains.** A domain is the native isolation unit: it owns processes, threads, address spaces, a generation-tagged capability table, CPU and memory policy, filesystem roots and mount views, network endpoints and device grants, and its lifecycle and failure policy. One agent (or agent team) runs in one domain. A domain cannot create kernel authority; it can only hold authority delegated to it, and delegation is revocable and generation-bound so cleanup after failure is enforceable.
3. **The ring-3 controller and the agent supervisor (thox-agentd).** The controller configures the kernel and manages domains from ring 3. It can delegate or revoke authority granted by the sealed boot envelope, but cannot create new kernel authority. thox-agentd follows the same rule for agents: it verifies signed agent identities offline, starts agents into their domains with exactly the capabilities in their manifests, brokers their tool calls, and writes the audit log. A compromised supervisor can misbehave within its delegated envelope; it cannot mint authority outside it.
4. **Agents.** Untrusted compute. An agent proposes plans; enforcement is not the agent's job. Agents hold no ambient authority: every tool call passes the broker, is checked against the manifest's capability grants, and is audit-logged. Read-only is the default posture; destructive operations are denied unless a grant says otherwise, and the syscall layer backs this with the policy-denied set in docs/COMPATIBILITY.md.
5. **The user.** The user grants capabilities, reads the audit log, and can revoke any agent's authority. Revocation must not require the agent's cooperation.

## Attack surfaces and mitigations

| Surface | Threat | Mitigation in the current build | Limit |
|---|---|---|---|
| Linux ABI (375 dispatched syscalls) | A Linux userspace program escapes its domain through a partially implemented syscall | Policy-denied set (48) refuses privileged operations by design; the compatibility matrix is published (docs/COMPATIBILITY.md) so the partial set is known, not hidden | 257 syscalls are Partial: bounded, not proven equivalent to Linux. The agent path is designed against the Complete set; general Linux compatibility is not a v1 claim |
| OCI image assembly | A tampered or swapped layer becomes a domain root | Layers are verified and assembled in manifest order with whiteout handling; the cache is content-addressed | Verification covers layer integrity; image signing policy for third-party images is not yet defined |
| Agent identity | A forged or swapped agent runs with another agent's grants | Manifests carry ed25519 signatures verified offline before first start; unsigned or unknown agents are refused and the refusal is logged | Key provisioning for user machines is a documented ceremony, not yet an installer flow |
| Tool broker | An agent exceeds its grants through the broker | Per-call capability check; grants are scoped (filesystem roots, process allowlist, network egress off by default); every decision is appended to the audit log | The broker is userspace; its own domain placement and hardening are Phase 2 work |
| Boot | A modified EFI or controller payload boots | Single EFI release unit with the controller payload authenticated by the boot envelope upstream | v0.9 ships with an explicit Secure Boot off posture (founder decision D14). Secure Boot signing lands in Phase 2. Until then, boot integrity rests on obtaining the image from the signed release checksums |
| Updates (RAUC-style bundles in the wider ThoxOS line) | A malicious or corrupt bundle replaces the system | Bundle tooling refuses keys inside the repository and verifies signatures against the keyring in the predecessor kits | The update path is not yet integrated into the ThoxInux EFI line; no OTA claim is made for v0.9 |
| Network | Domain traffic crosses to another domain or off-device without authority | Network endpoints are domain grants; IOMMU-confined virtio queues in the validated QEMU profile | IPv6, ancillary data and full socket option semantics are incomplete upstream (see compatibility matrix) |
| Proprietary boundary | MeshStack (closed) could become an unaccountable authority channel into the open kernel | MeshStack ships as a closed plugin that speaks to the kernel only over the stable domain/control ABI documented in thoxbeam/. It receives capabilities like any other principal, holds no special kernel privilege, and its calls are auditable at the ABI boundary | The plugin itself is proprietary; the boundary is auditable, its internals are not. That is a deliberate product decision, stated publicly |

## Out of scope for this model

- Physical attacks on an unlocked device, and firmware below UEFI.
- The proprietary components' internals (MeshStack, ThoxKey firmware, ThoxWork).
- Cloud services and hosted inference. Local operation requires no THOX cloud; hosted features, when used, are separate services with their own terms.
- Production readiness. Nothing in this document qualifies ThoxInux for production devices; Phase 3 (independent review, hardware validation) gates that word.

## Reporting

Security issues: see SECURITY.md when the repository is public. During the private staging period, report to tommy@thox.ai.
