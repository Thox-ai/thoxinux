# ThoxBeam interface

This directory documents the ThoxBeam runtime **interface** only. ThoxBeam is the runtime inside ThoxOS that ThoxKey uses on compatible host compute. Its driver logic is proprietary THOX technology and is not in this repository, under any license, in any form.

## The boundary

ThoxBeam, MeshStack and any other closed THOX component integrate with ThoxInux through the same surface as every other principal:

1. **Domain/control ABI.** The kernel's versioned control interface (upstream specs/abi in the Ginux tree) is the only kernel entry point for management operations. A closed component runs in its own domain, holds only the capabilities it is granted, and can have them revoked.
2. **Capability grants.** No component gets ambient authority by being THOX software. Grants are explicit, scoped and generation-bound, exactly like agent grants in userspace/agentos.
3. **Auditability at the boundary.** Calls across the interface are observable and loggable from the open side. The closed side's internals are its own; its requests and their outcomes are not secret from the user.

## What an integrator implements

- A domain manifest: identity (signed), requested capabilities, resource policy, failure policy.
- Control ABI client calls for lifecycle (start, stop, status) and any privileged operation, each checked by the kernel.
- Conformance to the allowlist posture: read-only by default, destructive operations denied without an explicit grant.

## What is deliberately not here

No driver code, no firmware, no keys, no MeshStack protocol internals, no ThoxKey attestation material. If a future open component needs a wider interface, the interface is extended here, in the open, first.
