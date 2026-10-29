# Ecosystem map: ThoxOS Ginux Edition

## Where it sits

| Field | Value |
|---|---|
| Parent product | ThoxOS (THOX operating system family) |
| Sibling editions | ThoxOS Vibe Desktop (Pop!_OS + COSMIC, KnightHub external SSD), ThoxOS webby edition, ThoxOS iOS and Watch, ThoxOS Android |
| Role | Research and demo edition: ThoxOS identity and tooling on a non-Linux kernel (Ginux), shown in Docker anywhere and on KnightHub hardware |
| Status | 0.1.0 research preview. Not a product kernel |

```mermaid
flowchart LR
  subgraph Upstream
    G["gmkurtzer/ginux<br/>Apache-2.0"]
    R["Rocky Linux 10<br/>UBI init image"]
    D["Debian 13 + backports<br/>QEMU 11.1, OVMF, kernel"]
  end
  subgraph ThisRepo["ttracx/thoxos-ginux"]
    P["patches 0001-0003"]
    U["ThoxOS userspace<br/>os-release, issue, motd, thox CLI"]
    T["thoxos-g launcher + driver"]
    DM["Docker demo image"]
    SSD["KnightHub SSD image + installers"]
  end
  subgraph THOX
    TXF["TXF design system<br/>#05A451, Inter, JetBrains Mono"]
    KH["KnightHub<br/>i7-14700F, 126 GB, RTX 4060 Ti"]
    AI["KnightHub model endpoint<br/>OpenAI-compatible, planned"]
    VIBE["ThoxOS Vibe Desktop<br/>same 500 GB THOXOS SSD"]
    FLEET["Agent fleet<br/>Hermes, Codex, Muse, Claude, DigitalHumans"]
  end
  G --> P --> DM
  R --> U --> DM
  D --> DM
  DM --> SSD --> KH
  U -- "thox ask" --> AI
  TXF --> DM
  SSD -. "guarded: refuses THOXOS-labeled disk without explicit flag" .- VIBE
  FLEET --> ThisRepo
```

## Upstream dependencies

| Dependency | Pin | Risk |
|---|---|---|
| Ginux | commit `36503bd` in `upstream.lock` | Research code, no audit, fast-moving; patches must be rebased per bump |
| Rocky 10 UBI init | digest in `upstream.lock` | Stable; userspace changes are file-only |
| QEMU 11.1 (trixie-backports) | Debian package | QEMU 10.0.x breaks Ginux virtio-net (F3) |
| Distribution registry v2, ttyd 1.7.7 | image digest, binary SHA-256 | Low |

## Downstream consumers

| Consumer | Uses |
|---|---|
| Tommy (demos, Kickstarter and social content) | Docker demo, KnightHub boot |
| THOX content library | Review findings and boot captures as post material |
| Fleet lanes | Handoffs in `handoffs/` |

## Data boundaries

| Boundary | Rule |
|---|---|
| Guest to outside | No inbound ports; outbound NAT through QEMU user networking only |
| Guest to host | 10.0.2.2 reaches host loopback: DNS (53), registry (443, read-only), optional model endpoint (11434) |
| Secrets | Registry leaf key only inside the image or host (0600); root key destroyed at build; admin password via BuildKit secret; web credential generated per container |
| User data | Lives in the Ginux volume (`volume.raw`) on the host state directory; no cloud sync |
