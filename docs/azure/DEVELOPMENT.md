# Azure variant development handoff

Private engineering candidate based on repository main `e88662bdc7e975753a5a049eb4b664bcee0db7e5`; upstream pin remains `36503bda2d87465765e1b94e65f9d100f27ed5be`. See [current validation](../../evidence/azure/VALIDATION_SUMMARY.json), [build provenance](../../module-ginux/SOURCE_MANIFEST.json), [deployment guide](THOX_Ginux_Azure_Deployment_Guide.pdf) and [Azure commands](../../azure/README.md).

The complete corrected EFI and minimal-system lifecycle are tested locally. Deploy only the corresponding allowlisted runtime ZIP on a dedicated Ubuntu Azure host. The deployment helper requires explicit subscription, a regional Gen2 image version, existing private artifact storage and an owned or empty compute resource group. Cloud acceptance remains open until real server validation, what-if, cloud-init and guest logs are returned. Do not claim AVD/native Hyper-V boot or Gallery capture from ARM syntax checks.

For a source rebuild, install module prerequisites, run build-native.sh, run the five host layout tests and the real acceptance_lifecycle.py harness in fresh output state, then retain exact EFI/receipt/log hashes. Azure package provenance checks must agree with all reviewed patch bytes. Changes to hardware, packaging or cloud bootstrap require the corresponding meaningful guard or execution check. Preserve old evidence as history.

The current session independently reviewed the frozen kernel patch and Azure runtime paths; external lane acknowledgement and corporate whole-repository certification are not implied.
