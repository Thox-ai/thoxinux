# ThoxOS Ginux Azure Compute Edition — Start Here

`0.2.0-azure-candidate` · Engineering candidate · October 29, 2026

[PDF deployment guide](THOX_Ginux_Azure_Deployment_Guide.pdf) · [HTML deployment guide](html/THOX_Ginux_Azure_Deployment_Guide.html) · [Current validation](validation.json) · [Complete Azure commands](../../azure/README.md)

**Your AI. Your Data. Your Rules.™**

## What you are running

Azure boots Ubuntu 24.04 Gen2. QEMU TCG on Ubuntu boots the customized independent Ginux Rust kernel. The Azure host retains its supported Hyper-V drivers and Azure VM agent. Ginux is a serial-console research guest with a tested minimal embedded userspace; it is not a Windows Azure Virtual Desktop session host or a graphical desktop.

The compute profile is `Standard_D4s_v5`, 128 GiB OS disk, Trusted Launch with Secure Boot/vTPM and accelerated networking. The VM has no public IP. Explicit NAT provides outbound access. A dedicated managed identity downloads an immutable runtime ZIP from an existing private Blob container. Default management uses Azure Run Command. Private SSH and separately billed Standard Bastion are optional.

The final combined THOX Azure EFI passed 22 real local QEMU commands across cold and recovered boots: embedded `/sbin/init`, detached PID 100, stop/start/restart, failure recovery, clean shutdown and saved configuration. 120 unit checks pass across the five local lanes. Read [validation.json](validation.json) and the [lifecycle receipt](../../evidence/azure/lifecycle-results.json) for the exact boundary. Accepted EFI SHA-256: `3ebcc9043ef9dc8b7e75abc15b113a5810c8d39c0ad47143476a41caed24d5ba` (12,507,648 bytes). Local tests do not establish Azure deployment: no Azure authentication, server validation, what-if, cloud boot or image capture has run here.

## Choose the correct package

| Item | What it contains | How to use it |
| --- | --- | --- |
| Git/source archive | Kernel patch series, build scripts, deployment code, receipts and documentation | Build the kernel and package the resulting payload. `GINUX.EFI` is excluded from Git. |
| `THOX_Ginux_Azure_Release.zip` | Actual compiled `module-ginux/artifacts/GINUX.EFI`, corresponding receipt/checksums/licenses, launcher, installer modules and provenance manifest | Supply this ZIP to `azure/deploy.py`. Keep it intact. |
| Documentation package | This QuickStart, PDF and complete HTML asset tree | Read and review; it does not substitute for the runtime ZIP. |

For a local serial demo from the runtime ZIP, first compare its complete SHA-256 with the separately delivered release receipt. Extract it to a new ordinary directory. From that directory, with QEMU x86-64, OVMF, Bash, Python 3 and util-linux installed on Linux:

```bash
bash module-ginux/scripts/run-vm.sh \
  --artifact-dir module-ginux/artifacts \
  --state-dir "$HOME/.local/state/thox/ginux-azure"
```

The launcher verifies its artifact inventory before boot. At `ginux>` enter `status`, `components`, `domain list` and `help`; finish with `shutdown`. One vCPU, 2 GiB, a 48-bit virtual IOMMU and a sparse 64 GiB guest volume are the constrained research profile. Never launch two guests against the same state. Docker and KVM runtime qualification remain separate, unrun gates.

## Build and package from source

Follow the full [module prerequisite instructions](../../module-ginux/README.md), including Rust 1.99.0, both Rust targets, Clang and GNU Make. From a reviewed source checkout:

```bash
bash module-ginux/scripts/build-native.sh
(cd module-ginux/artifacts && sha256sum --strict -c SHA256SUMS)
export THOX_RELEASE_ZIP=/absolute/path/THOX_Ginux_Azure_Release.zip
python3 azure/package_release.py --source . \
  --output "$THOX_RELEASE_ZIP" \
  --source-commit "$(git rev-parse HEAD)"
```

Use the actual reviewed source commit. A new build has its own payload hash, receipt and acceptance results. The packager refuses an existing output path. Its adjacent `.zip.json` binds the complete ZIP digest, size, source commit and build-receipt digest. Preserve these records with the release.

## Prepare the Azure deployment

Use an already authenticated Azure CLI or Azure Cloud Shell for the intended tenant. Copy `azure/deployment.example.json` to a private `azure/deployment.local.json`. Supply the real subscription ID, dedicated empty compute resource group, region, VM/admin names, administrator **public** key, existing storage account/resource group and private container. The example zero subscription and blank image version are deliberately unusable.

```bash
python3 azure/deploy.py resolve-image --config azure/deployment.local.json
```

Copy the exact returned Gen2 Ubuntu `image_version` into the local configuration; `latest` is refused. The operator needs compute and identity/RBAC authority plus separate artifact Blob upload/read permission. Storage network policy must allow the intended authenticated HTTPS path. Do not make the container public or add a SAS to custom data.

```bash
export THOX_DEPLOY_PLAN=/absolute/path/thox-ginux-azure-plan
python3 azure/deploy.py prepare \
  --config azure/deployment.local.json \
  --artifact "$THOX_RELEASE_ZIP" --out "$THOX_DEPLOY_PLAN"
python3 azure/deploy.py upload \
  --config azure/deployment.local.json --artifact "$THOX_RELEASE_ZIP"
python3 azure/deploy.py validate --plan "$THOX_DEPLOY_PLAN"
python3 azure/deploy.py what-if --plan "$THOX_DEPLOY_PLAN"
```

`prepare` is local. Upload uses a content-addressed object and readback-hashes the actual bytes. Inspect the plan and live previews for the exact subscription, ownership, private network, identity scope and expected costs. Mutating deployment requires the reviewed dedicated compute resource group. Existing resources without both matching THOX ownership tags stop deployment; a resource name alone never establishes ownership.

After successful server validation and reviewed what-if:

```bash
python3 azure/deploy.py deploy --plan "$THOX_DEPLOY_PLAN"
```

This creates billable Azure resources. NAT and optional Bastion can continue to cost money while the VM is deallocated. The helper does not silently clean up resources.

## Check the deployed host and kernel

Set these shell variables to the exact non-secret configuration values. Azure Run Command uses the VM agent without opening a VM public IP:

```bash
az vm run-command invoke \
  --subscription "$THOX_SUBSCRIPTION_ID" \
  --resource-group "$THOX_RESOURCE_GROUP" \
  --name "$THOX_VM_NAME" --command-id RunShellScript \
  --scripts 'cloud-init status --long; cat /opt/thox/ginux/azure-install-receipt.json; cat /var/log/thox-ginux/guest-smoke.json'
```

Repeat the read-only status check until cloud-init finishes; retain failures. The bounded bootstrap smoke proves controller boot, commands and clean shutdown only. Retain its JSON and log, artifact hashes and ARM outputs. A live domain lifecycle, separate-boot persistence and private route require their own acceptance. Provisioning success alone does not qualify them.

To enable interactive access, configure the narrow private SSH option and a real private route, or opt into Standard Bastion before preparing a fresh plan. Follow the [Bastion commands](../../azure/README.md). After SSH, `sudo -iu thoxginux thox-ginux` opens the guest serial terminal. Azure Serial Console reaches Ubuntu. No permanent guest daemon is installed.

## Capture or clean up deliberately

Customize and capture a disposable **Linux host** only after live acceptance, using [CAPTURE_MASTER_IMAGE.md](../../azure/CAPTURE_MASTER_IMAGE.md). Generalization is irreversible; no helper runs it automatically. A gallery version needs a fresh-clone acceptance test. The user's linked Windows AVD image procedure supplies lifecycle context and does not establish Linux AVD support.

Before deleting resources, inventory the exact dedicated resource group, preserve the receipts, and confirm it contains only this disposable deployment. Shared artifact storage and gallery versions need their own reviewed retention decisions. Physical external SSD/KnightHub boot remains unqualified; no disk-writing command is part of this QuickStart.

The [original root installation QuickStart](../../START_HERE.md), research guide and October 28 evidence are historical. Their predecessor panic and old EFI hash must not be relabeled as current Azure results.
