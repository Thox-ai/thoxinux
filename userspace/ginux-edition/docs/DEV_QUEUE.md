# Development queue

Ordered by priority score (Market Value x 0.4 + Technical Feasibility x 0.3 + Time-to-Market x 0.2 + Strategic Importance x 0.1, each 1 to 10). Re-scored 2026-10-29 for 0.2.0.

| # | Item | MV | TF | TTM | SI | Score | Owner lane |
|---|---|---|---|---|---|---|---|
| 1 | Boot the SSD image on KnightHub hardware under KVM; record tty1 photo, `thoxos-g doctor`, timings | 8 | 9 | 9 | 9 | 8.6 | Tommy (hardware), Kai (device steps) |
| 2 | First Azure run: publish the desktop VHD to a gallery, deploy `azuredeploy.json` on Standard_D4s_v5, confirm provisioning, RDP, the three looks and Ginux under nested KVM; save the boot diagnostics screenshot | 8 | 8 | 9 | 9 | 8.3 | Tommy (subscription), Hermes |
| 3 | Rule where the ThoxOS Desktop implementation lives (`ginux-edition/desktop/` or `ttracx/thoxos-desktop`) | 5 | 10 | 10 | 8 | 7.8 | Tommy |
| 4 | Open the upstream pull request for patch 0001 and issues for F3, F4 and F12 | 6 | 9 | 9 | 8 | 7.7 | Codex |
| 5 | Hosted AI end to end on Azure: an Azure OpenAI deployment behind `thox-ai-relay`, key from Key Vault, `thox ask` from the host and from ThoxOS on Ginux | 7 | 8 | 8 | 7 | 7.5 | Hermes, Claude |
| 6 | Measure KVM boot and OCI pull timings on KnightHub; add to VALIDATION.md | 6 | 9 | 8 | 7 | 7.4 | Hermes |
| 7 | Wire `thox ask` to the KnightHub model endpoint once its served model name is confirmed | 7 | 8 | 7 | 7 | 7.3 | Claude |
| 8 | Private access option in `azuredeploy.json`: no public IP, RDP through Bastion or a VPN (Record A's posture, RECONCILIATION_2026-10-29 R6) | 6 | 8 | 7 | 7 | 6.9 | Hermes, Codex |
| 9 | Run `Install-ThoxOSGinux.ps1` on KnightHub against a spare USB SSD and record the transcript | 5 | 8 | 8 | 5 | 6.5 | Tommy, Hermes |
| 10 | Screen lock for RDP sessions (TXF surface 14) | 5 | 7 | 7 | 5 | 6.0 | Claude |
| 11 | Opt-in bench step in local CI (no GitHub Actions): build the Azure VHD and run the QEMU and RDP bench, report it as its own commit status | 5 | 7 | 6 | 7 | 6.0 | Nova |
| 12 | Signed boot path (shim + signed loader) so the SSD boots with Secure Boot on and Azure can use Trusted Launch | 6 | 6 | 5 | 6 | 5.8 | Codex |
| 13 | Azure Virtual Desktop bridge, only if AVD is required: a Windows host pool that publishes Remote Desktop Connection to the ThoxOS VM as a RemoteApp | 5 | 7 | 5 | 5 | 5.6 | Hermes |
| 14 | Accelerated networking: test with the VF marked unmanaged, then turn it on in the template | 4 | 7 | 6 | 4 | 5.3 | Hermes |
| 15 | Getty login inside the domain (needs a console line discipline in Ginux; `thox-shell` covers interactive use today) | 5 | 5 | 6 | 5 | 5.2 | Claude |
| 16 | Redrawn TXF icon set and cursors (surfaces 4 and 5) | 4 | 6 | 5 | 6 | 5.0 | Muse (drafts), Clara (brand check) |
| 17 | GTK 4 and Qt themes from the same tokens (surface 8) | 4 | 6 | 5 | 5 | 4.9 | Claude |
| 18 | Finish the F4 fix (embedded minimal-system probe exec) and upstream it; Record A's startup patch claims an auxv fix, evaluate it first (RECONCILIATION_2026-10-29 R8) | 4 | 5 | 5 | 6 | 4.7 | Codex |

Re-score after items 1 and 2: real KVM and Azure numbers change TTM for the timing, endpoint and relay items.
