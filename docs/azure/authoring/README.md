# Guide authoring and finalization

This directory is internal source material, not an install-artifact input. The guide starts from THOX Official Templates1.0.0 and its exact outlined corporate identity. Keep the upstream template source external; do not publish master placeholders.

1. Replace only the factual status strings in `../validation.json` after reading the corresponding current logs and payload/source hashes. Preserve not-run cloud/image gates until executed.
2. Run `python3 docs/azure/authoring/build_guide.py` from the source root. It recreates the HTML/PDF and provenance record.
3. Run `python3 docs/azure/qa/check_documents.py` and `node docs/azure/qa/test_controls.cjs`.
4. Inspect every generated PDF page from `qa/contact.png`, then inspect any changed dense page at full resolution. Static link and control checks do not establish browser layout or live Azure acceptance.
5. Copy only the PDF and complete `html/` tree to the user documentation package. Keep `authoring/`, `qa/`, validation inputs and internal source receipts out of the executable Azure release.

Inter is available locally. JetBrains Mono is not installed; the PDF uses a recorded DejaVu Sans Mono compatibility fallback. No font binaries are included.
