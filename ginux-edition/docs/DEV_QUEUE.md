# Development queue

Ordered by priority score (Market Value x 0.4 + Technical Feasibility x 0.3 + Time-to-Market x 0.2 + Strategic Importance x 0.1, each 1 to 10).

| # | Item | MV | TF | TTM | SI | Score | Owner lane |
|---|---|---|---|---|---|---|---|
| 1 | Boot the SSD image on KnightHub hardware under KVM; record tty1 photo, `thoxos-g doctor`, timings | 8 | 9 | 9 | 9 | 8.6 | Tommy (hardware), Kai (device steps) |
| 2 | Open the upstream pull request for patch 0001 and issues for F3, F4 and F12 | 6 | 9 | 9 | 8 | 7.7 | Codex |
| 3 | Measure KVM boot and OCI pull timings on KnightHub; add to VALIDATION.md | 6 | 9 | 8 | 7 | 7.4 | Hermes |
| 4 | Wire `thox ask` to the KnightHub model endpoint once its served model name is confirmed | 7 | 8 | 7 | 7 | 7.3 | Claude |
| 5 | Run `Install-ThoxOSGinux.ps1` on KnightHub against a spare USB SSD and record the transcript | 5 | 8 | 8 | 5 | 6.5 | Tommy, Hermes |
| 6 | Signed boot path (shim + signed GRUB) so the SSD boots with Secure Boot on | 6 | 6 | 5 | 6 | 5.8 | Codex |
| 7 | Getty login inside the domain (needs a console line discipline in Ginux; `thox-shell` covers interactive use today) | 5 | 5 | 6 | 5 | 5.2 | Claude |
| 8 | Finish the F4 fix (embedded minimal-system probe exec) and upstream it | 4 | 5 | 5 | 6 | 4.7 | Codex |

Re-score after item 1: real KVM numbers change TTM for the timing and endpoint items.
