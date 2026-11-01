# Start here: ThoxInux

This repository was ThoxOS Ginux Edition (ttracx/thoxos-ginux) until 2026-10-31, when it was consolidated into the ThoxInux monorepo. The predecessor repository remains the private archive of record; this tree carries its full history.

## New here

Read README.md, then docs/QUICKSTART.md. Every command in the quick start was run against this tree.

## Coming from the predecessor lanes

- Kernel work (was module-ginux): kernel/ginux/. Its patch set was converged with the edition set; read docs/RECONCILIATION-2026-10-31.md before quoting any test number.
- Userspace and desktop (was ginux-edition): userspace/ginux-edition/.
- SSD installer (was ssd-module): boot/ssd/.
- Azure deployment variants (was azure/): docs/deployment-azure/ and userspace/ginux-edition/azure/. They remain separate products with separate security models.
- Historical kit guide (October 28, 2026) for the original research payload: docs/azure/START_HERE.md and the evidence records under evidence/. Its limits (including the embedded-domain failure in that environment) are payload-specific; the current diagnosis state is in the run's evidence report.
