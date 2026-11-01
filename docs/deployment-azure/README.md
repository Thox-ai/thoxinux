# ThoxOS Ginux Azure Compute variant

This package prepares an **Ubuntu 24.04 Gen2 Azure VM that runs the customized THOX Ginux kernel in QEMU TCG**. The Azure host retains Ubuntu's Hyper-V drivers and Azure VM agent. Ginux supplies the independent Rust kernel inside the research guest.

The linked [Azure Virtual Desktop master-image guide](https://learn.microsoft.com/en-us/azure/virtual-desktop/set-up-customize-master-image) configures Windows session hosts. It does not make Ginux an AVD-supported guest. This variant creates no Windows/AVD host pool, GUI, GPU or native Ginux Azure boot claim. TCG needs no nested virtualization. Do not enable KVM by assuming the Azure size exposes it.

Your AI. Your Data. Your Rules.™

## Current validation boundary

The ARM JSON, secret-free cloud-init generator, artifact packaging and local guard tests are checked here. A live subscription, Azure CLI identity and connected Azure API are required for server validation, what-if and deployment. Those commands are distinct acceptance stages. Local schema checks do not constitute an Azure deployment. The untouched Microsoft.Resources schema reports failures for its generated ARM-expression union and lowercase scope spelling; the local compatibility result records those native failures and two exact schema adaptations separately. Azure server validation and what-if are required before deployment. Refer to the owning build's evidence for actual EFI and QEMU results.

## What gets deployed

- Ubuntu `Canonical:ubuntu-24_04-lts:server:<explicit version>`, Gen2, `Standard_D4s_v5`, 128 GiB managed OS disk.
- Trusted Launch with host Secure Boot and vTPM. The guest's OVMF boot trust is separate; no production signing claim follows.
- Accelerated networking on a NIC with **no public IP**.
- A private host subnet with `defaultOutboundAccess=false`, an explicit NAT gateway and its static outbound public IP. NAT and its IP remain billable when the VM is deallocated.
- An NSG denying all inbound by default. Private SSH is a separate, narrow CIDR option.
- A dedicated user-assigned managed identity. It receives only Storage Blob Data Reader on the selected existing private artifact container. The deployment actor must be able to create that role assignment.
- Boot diagnostics and the normal Azure VM agent. No Docker daemon is required on the Azure host.

Standard Bastion is optional and separately billed. It adds a dedicated `AzureBastionSubnet` and a public endpoint for the managed Bastion service. The VM itself stays private. Without Bastion, Azure Run Command provides noninteractive management through the VM agent; an existing private VPN/peering route can provide interactive access only when that route actually exists.

## 1. Package the built kernel and corresponding patch provenance

Build the customized EFI through the root module instructions first. Then, from a real source checkout:

```bash
python3 azure/package_release.py \
  --source . \
  --output azure/releases/THOX_Ginux_Azure_Release.zip \
  --source-commit "$(git rev-parse HEAD)"
```

The packager reuses the existing host installer's artifact/receipt verification. It includes the EFI, checksum inventory, build receipt, license/notice, launcher, source manifest, patch series and patch files, plus the two existing installer modules. It excludes agent instructions, credentials and unrelated source material. The packager refuses missing, stale or extra patch mappings: both source manifest and build receipt must bind exactly the safe unique names in `patches/series` and the SHA-256 of each packaged patch. Their upstream commit and Cargo.lock digest must also agree, and any banner digest must match its patch. The ZIP is deterministic for identical input bytes. Its adjacent `.zip.json` records ZIP SHA-256, byte count and build-receipt digest. Source commit must identify the source actually used; never substitute an unrelated baseline SHA.

## 2. Select the Azure account, image and artifact storage

Use an already authenticated Azure CLI or Azure Cloud Shell with the intended THOX tenant. No identity is inferred from an arbitrary default account. Copy `azure/deployment.example.json` to a private local configuration file, replace the zero subscription ID, select existing resource groups/storage/container, and point to your **public** SSH key. Do not place a private key, token, storage key or SAS in the file.

```bash
cp azure/deployment.example.json azure/deployment.local.json
python3 azure/deploy.py resolve-image --config azure/deployment.local.json
```

Copy the returned exact `image_version` into the configuration. `latest` is refused. The resolver checks that the selected regional image is Gen2. The example storage/account names are examples, not provisioned resources.

The artifact storage account and container must already exist in the selected subscription. The container must be private and the operator needs Blob data upload/read permissions. The default deployment uses its authenticated HTTPS Blob endpoint over NAT. A storage account with public network access disabled or firewall `defaultAction=Deny` is refused because this new NAT address has not been admitted. Use a separately reviewed pre-provisioned network or private endpoint/private DNS design instead. Never disable a storage firewall or make the container public to pass a bootstrap check.

The compute resource group must also exist before ARM validate/what-if/deploy. All Azure CLI calls in the helper include the explicit selected subscription. The helper does not create accounts, register a different identity or switch your global Azure account.

## 3. Upload and verify the immutable artifact

```bash
python3 azure/deploy.py upload \
  --config azure/deployment.local.json \
  --artifact azure/releases/THOX_Ginux_Azure_Release.zip
```

The destination is content-addressed: `sha256/<ZIP SHA-256>/THOX_Ginux_Azure_Release.zip`. Existing blobs are never overwritten. The helper downloads either the new or existing blob and checks the actual bytes against the prepared ZIP. Blob metadata alone is not accepted as payload proof.

## 4. Prepare and inspect the complete plan

```bash
python3 azure/deploy.py prepare \
  --config azure/deployment.local.json \
  --artifact azure/releases/THOX_Ginux_Azure_Release.zip \
  --out azure/plans/azure-compute-01
```

Preparation is local and uses no Azure API. The output contains `azuredeploy.json`, `parameters.json`, `cloud-init.txt`, a configuration copy and `plan.json` with file hashes. Edits to a prepared plan are refused; change the source configuration and prepare a new version. Cloud-init contains a Blob URL and digests but no SAS, bearer token or storage key. ARM resolves the managed identity client ID before boot.

To enable a concrete interactive route, set both `enable_bastion` and `enable_private_ssh` to `true` before preparing the plan. Keep the default distinct `/26` Bastion subnet, and set `admin_source_cidr` to a `/24` or narrower RFC1918 network that covers that subnet. The helper checks containment and overlap. This opt-in creates the separately billed Standard Bastion service. With both options false, no inbound administration endpoint is exposed on the VM.

## 5. Validate, preview and deploy

```bash
python3 azure/deploy.py validate --plan azure/plans/azure-compute-01
python3 azure/deploy.py what-if --plan azure/plans/azure-compute-01
python3 azure/deploy.py deploy --plan azure/plans/azure-compute-01
```

`deploy` creates Azure resources and costs. `validate` and `what-if` are the reviewable steps before that action. Check region capacity, subscription quota, policies, existing storage firewall rules and role-assignment authority. No script bypasses a denial. Record the ARM deployment result separately from guest acceptance.

At boot, the host obtains an IMDS managed-identity token, downloads only the pinned private Blob, verifies the complete ZIP hash, then validates the allowlisted manifest and every file hash. Redirects are not followed with authorization headers. The existing verified host installer runs only after full archive verification. RBAC propagation is retried within a bounded window. Tokens and HTTP response bodies are not printed.

## 6. Inspect real acceptance evidence

Azure Run Command works through the VM agent without opening a VM public IP or inbound port. Supply the explicit subscription, resource group and VM name from your configuration:

```bash
az vm run-command invoke \
  --subscription "$THOX_SUBSCRIPTION_ID" \
  --resource-group "$THOX_RESOURCE_GROUP" \
  --name "$THOX_VM_NAME" \
  --command-id RunShellScript \
  --scripts 'cloud-init status --long; cat /opt/thox/ginux/azure-install-receipt.json; cat /var/log/thox-ginux/guest-smoke.json'
```

Set these three shell variables to the same non-secret values in your local config. A provisioning response can arrive before cloud-init finishes. Repeat the read-only status call as needed; never infer acceptance from missing output. Use `cloud-init status --wait` from a private SSH session for a blocking check, then `systemctl --failed`.

The bootstrap installs:

- `/opt/thox/ginux/` with the EFI, launch script, artifact receipt and `azure-install-receipt.json`.
- `/usr/local/bin/thox-ginux` and the dedicated locked `thoxginux` account, home `/var/lib/thox-ginux`.
- `/var/log/thox-ginux/guest-smoke.json` and `guest-smoke.log` from a bounded **real** QEMU boot, controller commands and clean shutdown.

The smoke test does not start an arbitrary Linux domain. It proves only the running controller's banner, commands and clean shutdown. Failed evidence is preserved and blocks acceptance.

For interactive access after opting into Bastion, use its portal connection or the CLI's native client:

```bash
az network bastion ssh \
  --subscription "$THOX_SUBSCRIPTION_ID" \
  --resource-group "$THOX_RESOURCE_GROUP" \
  --name "${THOX_VM_NAME}-bastion" \
  --target-resource-id "$THOX_VM_RESOURCE_ID" \
  --auth-type ssh-key --username thoxadmin \
  --ssh-key ~/.ssh/id_ed25519
```

Use the admin name/key actually selected in your config, and the `vmResourceId` ARM output. The private key stays on the client. Once connected:

```bash
sudo -iu thoxginux thox-ginux
```

Enter `shutdown` before closing the terminal. No background QEMU service is auto-started after the bounded smoke test. Do not run two guests on the same state directory.

## Custom master-image path

After the deployed host passes acceptance, follow [CAPTURE_MASTER_IMAGE.md](CAPTURE_MASTER_IMAGE.md) to produce a clean generalized Ubuntu host image in Azure Compute Gallery. Deprovisioning and generalizing are deliberate, separate operations on a disposable builder VM. No deployment helper automatically deletes user data, generalizes a machine or publishes a gallery image.

## Local verification

```bash
python3 -m unittest discover -s azure/tests -v
python3 azure/generate_template.py
python3 -m py_compile azure/*.py
```

`azuredeploy.json` is generated source. These tests exercise archive trust boundaries, unsafe configuration rejection, private network defaults, immutable plans and explicit subscription selection. They do not contact Azure. Live ARM validation, deployment, VM network reachability, blob authorization and host/guest acceptance require the actual target subscription.

Deployment mutation requires a dedicated empty compute resource group on first use. Before `deploy`, the CLI successfully inventories that group and refuses every resource that lacks both `thox-project=thoxos-ginux` and the matching `thox-deployment=<vm_name>` tag. Lookup failures stop deployment. Template resources carry these tags; Azure-generated resources such as an OS disk may need an operator's ownership review and explicit tagging before a retry. Resource names alone never authorize overwriting an existing resource. `validate` and `what-if` remain read-only previews.

## Reproduce the local schema check

```bash
python3 -m venv .venv-azure-validation
.venv-azure-validation/bin/pip install -r azure/requirements-validation.txt
.venv-azure-validation/bin/python azure/validate_arm_schema.py \
  --cache /tmp/thox-arm-schemas \
  --receipt /tmp/thox-arm-schema-result.json
```

The validator uses SHA-256 locked schemas from Microsoft's [Azure resource-manager schema repository](https://github.com/Azure/azure-resource-manager-schemas/tree/349477f132aad67ac74af3224ddea833bffc806d), with no implicit remote schema resolution. It checks both template wrappers and all 11 concrete resources against their exact API definitions, including the cross-resource-group nested role assignment. Expression contents and actual cloud availability are not evaluated. The checked-in `ARM_SCHEMA_VALIDATION.json` retains the **failed untouched strict result**, individual errors, schema hashes and a separately labeled compatibility result.

Two explicit compatibility changes affect only the generated [Microsoft.Resources 2022-09-01 schema](https://github.com/Azure/azure-resource-manager-schemas/blob/349477f132aad67ac74af3224ddea833bffc806d/schemas/2022-09-01/Microsoft.Resources.json): `DeploymentParameter.value` uses `oneOf` with both an empty schema and an expression schema, which incorrectly rejects expressions matching both; the adapter uses `anyOf` there. `ExpressionEvaluationOptions.scope` lists `Inner/Outer` while Microsoft's [nested-template scope documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/linked-templates#expression-evaluation-scope-in-nested-templates) uses lowercase `inner/outer`; the adapter accepts those spellings. These local changes do not modify the deployment template or waive server validation.

The nested role assignment follows Microsoft's [cross-resource-group extension-resource guidance](https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/scope-extension-resources). The private artifact container's resource group must exist and the operator must be authorized there as well as in the compute resource group.
