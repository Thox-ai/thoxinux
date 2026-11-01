# Ecosystem map: ThoxOS Ginux Edition

## Where it sits

| Field | Value |
|---|---|
| Parent product | ThoxOS (THOX operating system family) |
| Sibling editions | ThoxOS Vibe Desktop (Pop!_OS + COSMIC, KnightHub external SSD), ThoxOS webby edition, ThoxOS iOS and Watch, ThoxOS Android |
| Role | Research and demo edition: ThoxOS identity and tooling on a non-Linux kernel (Ginux), shown in Docker anywhere, on KnightHub hardware and on Azure VMs, with ThoxOS Desktop (TXF 5.2) as the host desktop |
| Status | Host images 0.2.0, guest 0.1.0. Research preview. Not a product kernel |

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
    DSK["ThoxOS Desktop (TXF 5.2)<br/>generated looks, dock, greeter"]
    AZI["Azure VHD<br/>desktop or headless"]
    RLY["thox-ai-relay<br/>loopback, hosted model"]
  end
  subgraph Azure
    GAL["Compute Gallery image"]
    AVM["Azure VM, Dsv5<br/>nested KVM, RDP from one CIDR"]
    AOAI["Hosted model<br/>Azure OpenAI or other"]
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
  TXF -- "txf-tokens.json (copied unchanged)" --> DSK
  DM --> AZI
  DSK --> AZI
  DSK --> SSD
  AZI --> GAL --> AVM
  RLY --> AVM
  AVM -- "relay, key on host" --> AOAI
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
| Debian cloud kernel (`linux-image-cloud-amd64`) | Debian 13 package | No DRM drivers: framebuffer-only console (seat rule in the Azure overlay) |
| cloud-init 25, waagent 2.12, xrdp, XFCE 4.20, plank, Papirus | Debian 13 packages | Unit names changed in cloud-init 25 (configure-host.sh detects them) |
| TXF 5.2 desktop tokens | `ttracx/thox-experience-fabric` at `adec4ae` | Implementation location awaiting ruling (DESKTOP.md) |
| Azure Compute Gallery, ARM API 2024-03-01 (compute) | `azure/azuredeploy.json` | Not yet deployed |

## Downstream consumers

| Consumer | Uses |
|---|---|
| Tommy (demos, Kickstarter and social content) | Docker demo, KnightHub boot |
| THOX content library | Review findings and boot captures as post material |
| Fleet lanes | Handoffs in `handoffs/` |
| Azure demos and partner trials | Gallery image and template; RDP desktop with ThoxOS on Ginux |

## Data boundaries

| Boundary | Rule |
|---|---|
| Guest to outside | No inbound ports; outbound NAT through QEMU user networking only |
| Guest to host | 10.0.2.2 reaches host loopback: DNS (53), registry (443, read-only), optional model endpoint (11434) |
| Secrets | Registry leaf key only inside the image or host (0600); root key destroyed at build; admin password via BuildKit secret; web credential generated per container |
| User data | Lives in the Ginux volume (`volume.raw`) on the host state directory; on desktop images each user's volume is in `~/.local/state/thoxos-g`; no cloud sync |
| Azure network | NSG admits SSH and RDP only from `allowedSourceCidr` (no default); no other inbound port |
| Hosted AI key | Only in `/etc/thoxos/ai-relay.env` (root:thoxos-ai, 0640); never in user shells, the Ginux guest or the image; template takes it as a secure parameter |
| Image secrets | None: no account, password, SSH host key, xrdp key or machine-id in the VHD; first boot creates them |
