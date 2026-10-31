# Integrated Ginux continuation pickup

Internal engineering continuity. Prepared October 30, 2026 (America/Chicago). This file records the current Codex session's work and prepared next assignments; it does not impersonate another runtime's acknowledgement.

## Objective and source

Promote the latest ThoxOS Ginux desktop/image implementation while preserving the independently tested root Azure kernel variant, repair reviewed source/runtime/credential defects, rerun available checks, and provide authentic user-experience evidence with precise limits.

- Owning private repository: `ttracx/thoxos-ginux`.
- Continuation parent: main `10787b1ae9dc024f069d229e83339876212afc5e`.
- Image/desktop input: `ginux-edition-0.1.0` at `7f8f2007d3ae8da19ddb0309e99ee25904971cd1`, tree-equivalent to `ginux-edition-0.2.0` at `98845311dd79f09fb96c25e7e6e9200ece7631ff`.
- Common Ginux upstream: `36503bda2d87465765e1b94e65f9d100f27ed5be`.
- Preserve root `azure/`, `module-ginux/`, `ssd-module/`, historical evidence and root handoffs. Do not replace them with the image branch's older root copies.
- Preserve the two EFI patch sets and hashes. Combining source trees does not establish image rebuild, Azure deployment, physical boot or MeshStack integration.
- Final authenticated source SHA, artifact hashes and remote readback are recorded after push, outside the reviewed shipping commit.

Read [the continuation note](../docs/continuation/README.md), [current validation](../docs/continuation/validation.json), both existing handoffs (`HANDOFF.md`, `AZURE_HANDOFF.md`), `../ginux-edition/.agents/HANDOFF.md`, the root experience selector and owning validation files before another change. Fresh screenshot/recording assets live in `docs/continuation/media/`; the final video is `live-guest.mp4`.

The current illustrated report is `docs/continuation/report.html` and `docs/continuation/report.pdf`. The final four-page PDF was rendered and every page inspected; embedded Inter/JetBrains Mono and the exact template logo are preserved. Structural offline HTML checks passed; interactive HTML browser QA remains unrun.

## Actual teams in this session

These are real subagent task names in the coordinating session, not dispatch to external named colleagues. Their result becomes accepted only when the parent reviews returned files, logs and claim limits.

| Task | Allowed scope | Exit evidence |
| --- | --- | --- |
| `latest_code_review` | Latest-source review; `ginux-edition/scripts/ginux-source.sh` and source-preparation regressions | Exact source-input mapping; foreign/dirty/stale checkout refusal and valid reuse checks; no destructive replacement |
| `runtime_config_fix` | Docker entrypoint setting propagation and scoped executable-shell tests | Supported settings survive privilege drop; unrelated/secret environment is not broadly forwarded; test-harness limit stated |
| `relay_azure_fix` | Hosted relay, image-lane Azure template and directly relevant tests/docs | Redirects cannot forward credentials; no API key in customData; safe root-owned postdeployment configuration contract; local upstream test scope retained |
| `runtime_evidence` | Scoped dependencies and actual QEMU capture/evidence only | Fresh screenshot/recording from actual guest execution, source/payload hashes, command/result logs; no transcript recreation or Docker/physical claim |
| `mesh_integration_review` | Read-only cross-repository Mesh review | Exact Mesh baselines and live/fixture boundaries; no Ginux integration inferred |
| `docs_integration` | Root README/START_HERE/AGENTS and continuation docs/handoff | Clear experience selector, per-lane evidence provenance, historical labels, exact limits and current pickup |
| Parent `/root` | Integration, independent test review, final preview, authenticated push/archive and authorized report | Exact source/bytes readback, tests, artifact inventory, Sent Items verification and remaining gates |

## Acceptance and stop conditions

Run the image implementation's `make test` and `make ci` against the integrated source, and root Azure/module/SSD tests. Review every skip and failure. ShellCheck, syntax and any full theme-generation result must state whether dependencies and execution were available. Do not label fake-QEMU or stub-upstream tests as guest boot or hosted inference.

Use the exact accepted EFI for any new root-kernel recording and bind the capture receipt to its SHA-256. Fresh recording of that EFI does not test the image implementation's separately compiled EFI or a newly edited Docker image. Any changed image needs `make demo-image`, `make selftest`, shell e2e, authenticated browser testing, desktop/headless VHD and USB-disk benches on a capable host before corrected-binary distribution.

Stop physical actions while KnightHub is offline or the SSD target is unresolved. Never choose the THOXOS/Vibe disk, change firmware, erase a drive or reboot by inference. Stop Azure deployment when identity, subscription, resource ownership, quota or image acceptance is missing. Do not bypass source, writer, TLS, capability or memory guards to obtain a pass.

## Prepared next assignments

| Receiving lane | Assignment, inputs and allowed work | Acceptance / stop condition |
| --- | --- | --- |
| Hermes | Reconcile final source/archive/report receipts and preserve existing predecessor records | Return actual runtime identity, source/hash/load receipt and delivery result; no substitute mailbox or invented acknowledgement |
| Codex / Nova | On a capable authorized build host, rebuild this shipping source; run local CI, Docker selftest/shell/browser and image benches | Return commands, environment, image/EFI hashes and logs; no historical result relabeled as fresh |
| Claude | Independently review only the reviewed patch range and evidence claims in a matching checkout | Exact baseline/head, changed paths and findings; do not disable guards or alter unrelated image ownership |
| Muse / Samuel / Julian / Clara / Sera | Maintain official narrative, internal HTML/PDF preview, captions, brand and claim review from actual captures | Preserve genuine/fixture/synthetic labels; keep agent pickup and template internals out of customer downloads and public routes |
| Kai | When KnightHub is online, inventory hardware and spare SSD read-only, then obtain exact target/action authorization before destructive acceptance | Qualified physical boot, persistence and relevant device evidence; no implicit erase, firmware change or reboot |
| Azure deployment owner | Use the selected root-marketplace or image-Gallery design with an authorized identity; validate/what-if, deploy and inspect actual guest provisioning | Exact deployment/host receipts; do not mix Standard and Trusted Launch settings or infer nested KVM |
| MeshStack owner | Preserve the owning Mesh UX/runtime lanes; implement and verify an actual cross-platform integration before a live Mesh claim | Name coordinator source, nodes, workload and result; fixture dashboard and virtual-profile evidence stay labeled |
| Sadie | After source/archive verification, send the authorized consolidated THOX report from verified Sadie@thox.ai to Tommy/Craig | Verify Sent Items and actual attachments; reconcile unknown sends before retry; no recipient-read claim |

These named external assignments are prepared, not acknowledged or executed by those runtimes in this session. The parent may record its own completed steps only with actual tool evidence. The canonical ship tracker and unrelated lane ownership remain intact.
