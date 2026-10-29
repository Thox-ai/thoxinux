# Capture an accepted THOX Azure host image

This is an optional operator procedure, **not an executed deployment or image capture**. The supplied ARM deployment starts from a pinned Ubuntu Marketplace version and installs a verified THOX release. This procedure captures that installed Linux host into Azure Compute Gallery after it passes real cloud acceptance. The linked Windows AVD master-image procedure is not a Ginux/Linux session-host integration.

## Acceptance before capture

Use a disposable image-builder VM. Retain the immutable release ZIP, source commit, build receipt, full deployment results, `azure-install-receipt.json` and actual `guest-smoke.json`/log outside the VM before cleanup. Check that cloud-init completed, the Azure VM agent is healthy, host Secure Boot/vTPM are enabled, and a fresh bounded THOX guest smoke passed. Shut down the guest cleanly. Do not capture a running QEMU process or assume local build evidence proves cloud acceptance.

The following procedure is for a **generalized Ubuntu 24.04 Gen2 Trusted Launch host image**. It does not make the Ginux EFI a native Azure kernel. Host package versions and kernel/EFI release hashes belong in the image version's external release record.

## Prepare the disposable builder

Review the host for machine-specific data before generalization:

1. Export builder acceptance evidence and release provenance to the approved release location.
2. Remove any user credentials, SSH authorized keys, shell history, diagnostic payloads and unrelated test data that must not enter a reusable image. Azure deprovisioning does not guarantee this cleanup.
3. Review the dedicated guest's state at `/var/lib/thox-ginux/.local/state/thox/ginux`. It contains the persistent `volume.raw` and OVMF state. Remove the state directory only on this disposable builder, only after the guest is stopped and any required data has been exported, so clones begin with a fresh guest volume. Preserve the locked `thoxginux` system account and home permissions.
4. Preserve `/opt/thox/ginux` kernel/license/notice/build receipt, launcher and `host-install-receipt.json` as installed-payload provenance. Archive and remove `/opt/thox/ginux/azure-install-receipt.json` and `/var/log/thox-ginux` from the image; their builder outcomes are not clone acceptance evidence.
5. Remove `/etc/thox-ginux-azure.json` after retaining its nonsecret provenance externally. Its identity client ID belongs to the builder. Keep the installed smoke utility `/usr/local/lib/thox-ginux/smoke_guest.py` for independent clone tests. Do not run the installer bootstrap against an already installed captured payload.

These cleanup steps intentionally require operator review; no repository command wipes the builder or personal data automatically. A managed identity attachment is a VM resource property and must be selected independently for a new VM. An existing builder's container role assignment does not grant a clone access.

## Generalize only after that review

Microsoft's [Linux generalization procedure](https://learn.microsoft.com/en-us/azure/virtual-machines/generalize) removes the last provisioned administrator. Marking a VM generalized prevents restarting that source VM. These are deliberate one-way image-builder actions; do not run them on a retained working machine.

On the accepted builder, from the final administrative session:

```bash
sudo cloud-init clean --logs --seed
sudo waagent -deprovision+user
exit
```

Keep the interactive `waagent` confirmation. Follow any additional cleanup required by the current [Ubuntu Azure image guidance](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/create-upload-ubuntu). Do not reboot the builder after deprovisioning. From the authenticated operator's Azure CLI, set the existing explicit subscription/resource group/VM values from the reviewed deployment configuration, then:

```bash
az vm deallocate --subscription "$THOX_SUBSCRIPTION_ID" \
  --resource-group "$THOX_RESOURCE_GROUP" --name "$THOX_VM_NAME"
az vm generalize --subscription "$THOX_SUBSCRIPTION_ID" \
  --resource-group "$THOX_RESOURCE_GROUP" --name "$THOX_VM_NAME"
```

## Publish a version into Azure Compute Gallery

Use an approved gallery resource group, gallery name, image-definition name, region and unique numeric `major.minor.patch` image version. Set `THOX_GALLERY_RESOURCE_GROUP`, `THOX_GALLERY_NAME`, `THOX_IMAGE_DEFINITION`, `THOX_IMAGE_VERSION` and `THOX_LOCATION` to those reviewed values. This creates billable image resources and regional replicas. Every command below selects the subscription explicitly.

```bash
THOX_SOURCE_VM_ID="$(az vm show --subscription "$THOX_SUBSCRIPTION_ID" \
  --resource-group "$THOX_RESOURCE_GROUP" --name "$THOX_VM_NAME" \
  --query id --output tsv)"

az sig create --subscription "$THOX_SUBSCRIPTION_ID" \
  --resource-group "$THOX_GALLERY_RESOURCE_GROUP" \
  --gallery-name "$THOX_GALLERY_NAME" --location "$THOX_LOCATION"

az sig image-definition create --subscription "$THOX_SUBSCRIPTION_ID" \
  --resource-group "$THOX_GALLERY_RESOURCE_GROUP" \
  --gallery-name "$THOX_GALLERY_NAME" \
  --gallery-image-definition "$THOX_IMAGE_DEFINITION" \
  --location "$THOX_LOCATION" --publisher THOX --offer ThoxOSGinux \
  --sku AzureCompute --os-type Linux --os-state Generalized \
  --hyper-v-generation V2 --features SecurityType=TrustedLaunch

az sig image-version create --subscription "$THOX_SUBSCRIPTION_ID" \
  --resource-group "$THOX_GALLERY_RESOURCE_GROUP" \
  --gallery-name "$THOX_GALLERY_NAME" \
  --gallery-image-definition "$THOX_IMAGE_DEFINITION" \
  --gallery-image-version "$THOX_IMAGE_VERSION" \
  --location "$THOX_LOCATION" --target-regions "$THOX_LOCATION" \
  --replica-count 1 --virtual-machine "$THOX_SOURCE_VM_ID"

az sig image-version show --subscription "$THOX_SUBSCRIPTION_ID" \
  --resource-group "$THOX_GALLERY_RESOURCE_GROUP" \
  --gallery-name "$THOX_GALLERY_NAME" \
  --gallery-image-definition "$THOX_IMAGE_DEFINITION" \
  --gallery-image-version "$THOX_IMAGE_VERSION" --output json
```

If the gallery or image definition already exists, inspect it and reuse it only when its ownership, OS state, architecture and security properties match. Do not recreate or alter an unrelated definition. Wait for successful image provisioning and regional replication; record the **version-specific resource ID** and hash of the accepted release record. Keep published image versions immutable by release policy; never use `latest` as an acceptance identity.

The `TrustedLaunch` feature is specifically required for [capturing a Trusted Launch VM](https://learn.microsoft.com/en-us/azure/virtual-machines/trusted-launch-portal). That source differs from the `TrustedLaunchSupported` path for a Gen2 OS-disk VHD without VM guest state. A legacy managed-image resource is not supported for a Trusted Launch VM. The current [image-version CLI](https://learn.microsoft.com/en-us/cli/azure/sig/image-version?view=azure-cli-latest) accepts `--virtual-machine` directly.

## Qualify a fresh clone

This repository's ARM template accepts a Marketplace version; it does **not** accept a Gallery image ID. To test the captured version, use Azure's Gallery **Create VM** flow or a separately reviewed template that references the exact image-version ID. Match the supported host design: Gen2/Trusted Launch with Secure Boot and vTPM, x86-64 D4s_v5, accelerated NIC, private VM IP, explicit outbound route and reviewed management access. Select a new administrator and identity. Do not reuse the builder's bootstrap cloud-init against the preinstalled payload.

On each fresh clone, verify provisioning and run a new smoke test:

```bash
cloud-init status --wait
sudo python3 /usr/local/lib/thox-ginux/smoke_guest.py \
  --output /var/log/thox-ginux-clone
sudo cat /var/log/thox-ginux-clone/guest-smoke.json
```

Bind the new log/receipt to that clone's VM resource ID and the exact Gallery image-version ID. Check the installed EFI/build receipt against the external accepted release. A builder log, inherited receipt or successful image replication cannot substitute for this fresh-instance test. No Gallery image, clone, AVD deployment, GUI/GPU workload or native Ginux Azure boot has been executed or claimed by this procedure.
