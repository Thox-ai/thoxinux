#!/usr/bin/env python3
"""Build the Azure guide from structured content and exact official template assets."""
from pathlib import Path
import json, hashlib, html, shutil, re, datetime
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Preformatted, Flowable, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

ROOT=Path(__file__).resolve().parent.parent
KIT=Path('/root/.codex/plugins/cache/created-by-me-remote/thox-official-templates/1.0.0/skills/thox-official-templates/assets/template-kit')
HTML=ROOT/'html'; ASSETS=HTML/'assets'; ASSETS.mkdir(parents=True,exist_ok=True)
for name in ['thox-report.css','thox-report.js']: shutil.copyfile(KIT/'html'/name,HTML/name)
for name in ['thox-horizontal-dark.svg','thox-horizontal-dark.png']:shutil.copyfile(KIT/'assets'/name,ASSETS/name)
master=(KIT/'html/THOX_Documentation_Template_v1.0.0.html').read_text()
val=json.loads((ROOT/'validation.json').read_text())
BRAND='#05A451';INK='#101418';MUTED='#52525B'

def p(s):return ('p',s)
def h(s):return ('h',s)
def code(s):return ('code',s)
def table(headers,rows,widths=None):return ('table',headers,rows,widths)
def note(s):return ('note',s)
def bullets(items):return ('bullets',items)

sources=[
('S01','Microsoft: Prepare and customize a VHD image for Azure Virtual Desktop','https://learn.microsoft.com/en-us/azure/virtual-desktop/set-up-customize-master-image'),
('S02','Microsoft: Azure Virtual Desktop prerequisites','https://learn.microsoft.com/en-us/azure/virtual-desktop/prerequisites'),
('S03','Microsoft: Linux remote-desktop options','https://learn.microsoft.com/en-us/azure/virtual-machines/linux/linux-remote-desktop-options'),
('S04','Microsoft: Prepare a generic Linux image for Azure','https://learn.microsoft.com/en-us/azure/virtual-machines/linux/create-upload-generic'),
('S05','Microsoft: Hyper-V driver troubleshooting for Azure Linux VMs','https://learn.microsoft.com/en-us/troubleshoot/azure/virtual-machines/linux/troubleshoot-lis-driver-issues-on-linux-vms'),
('S06','Microsoft: Dsv5 VM series','https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/general-purpose/dsv5-series'),
('S07','Microsoft: Default outbound access and explicit outbound connectivity','https://learn.microsoft.com/en-us/azure/virtual-network/ip-services/default-outbound-access'),
('S08','Microsoft: Trusted Launch','https://learn.microsoft.com/en-us/azure/virtual-machines/trusted-launch'),
('S09','Microsoft: Cloud-init on Azure Linux VMs','https://learn.microsoft.com/en-us/azure/virtual-machines/linux/using-cloud-init'),
('S10','Microsoft: Azure Bastion SSH to Linux','https://learn.microsoft.com/en-us/azure/bastion/bastion-connect-vm-ssh-linux'),
('S11','Microsoft: Nested virtualization','https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/enable-nested-virtualization'),
('S12','THOX source baseline','https://github.com/ttracx/thoxos-ginux/tree/e88662bdc7e975753a5a049eb4b664bcee0db7e5'),
]

pages=[
('scope','01 / outcome','A complete build path with a clear Azure boundary',[
 p('The Azure variant places the customized THOX Ginux kernel inside QEMU on an Ubuntu 24.04 Gen2 Azure VM. Azure boots and provisions the Linux host; QEMU supplies the Q35, OVMF and virtual devices that Ginux currently understands. The supplied package provides the kernel build, integrity-bound release artifact, private-VM infrastructure, managed-identity bootstrap and acceptance workflow.'),
 note('Product stage: engineering candidate. Documentation status: DRAFT. Actual kernel, packaging and local test outcomes appear in the evidence table. Azure deployment is not claimed without a connected subscription and a successful live acceptance run.'),
 table(['Requested idea','Implemented route','Boundary'],[
 ['Customized kernel','THOX Ginux EFI with source/patch provenance','A built EFI is not native Azure OS support.'],
 ['Azure deployment','Ubuntu Gen2 host plus nested QEMU TCG guest','No Hyper-V driver support is invented for Ginux.'],
 ['Customized master image','Customize and accept the Linux host, then capture through Azure image tooling','The linked Windows AVD procedure does not produce a Linux AVD session host.'],
 ['Interactive demo','Private SSH/Bastion to Linux; launch the Ginux serial console','No public web terminal, RDP listener or unauthenticated control plane.'],
 ]),
 h('Why the linked master-image article is a reference, not the build recipe'),
 p('The Microsoft article covers Windows Azure Virtual Desktop images, including Windows software and registry preparation. Azure Virtual Desktop session-host prerequisites list Windows operating systems. Linux remote desktops use a separate VM/VDI approach. This variant uses the same disciplined image lifecycle: build, customize, verify, generalize only when appropriate, and capture. It does not copy Windows registry, FSLogix or AVD agent steps into Ginux. [S01–S03]'),
 p('ThoxOS remains the operating and intelligence platform; MeshStack connects authorized resources, and ThoxWork organizes coordinated work. This research kernel package does not by itself establish running AI, mesh or workspace services inside Ginux.'),
 ]),
('architecture','02 / architecture','Two kernels, explicit trust boundaries',[
 ('figure',),
 table(['Layer','Profile','Responsibility'],[
 ['Azure host','Ubuntu 24.04 Gen2; Standard_D4s_v5; 128 GiB OS disk','Supported Azure boot, provisioning, SSH and synthetic network/storage drivers.'],
 ['Host protection','Trusted Launch; Secure Boot and vTPM','Protects the Azure Linux host. It is separate from Ginux guest boot/catalog signatures.'],
 ['Research VM','QEMU TCG; Q35/OVMF; one vCPU; 2 GiB RAM','Supplies the validated guest hardware model.'],
 ['Ginux guest','THOX EFI; 48-bit virtual IOMMU; modern virtio block/network','Independent Rust kernel and administration controller.'],
 ['State','Sparse 64 GiB guest volume in dedicated user state','Retains guest configuration/cache; it is not a 64 GiB Azure managed disk allocation.'],
 ]),
 h('Network and identity'),
 p('The template gives the VM no public IP. An existing private route, VPN, peering or Bastion provides administrative access. A user-assigned managed identity reads one private Blob container through an explicit data-plane role. The artifact ZIP digest is pinned independently of that identity. No SAS, PAT, private SSH key or IMDS access token belongs in ARM parameters, custom data, logs or this guide.'),
 p('Explicit NAT supplies package/artifact egress; NSG rules do not provide NAT. Dsv5 NICs enable Accelerated Networking. This size has no GPU. TCG avoids nested virtualization; optional KVM needs a separately supported profile and actual /dev/kvm evidence. Never silently disable Trusted Launch. [S06–S08, S11]'),
 ]),
('prerequisites','03 / prerequisites','Resolve the deployment inputs before provisioning',[
 table(['Input','What to supply','Checks before use'],[
 ['subscription_id','The authorized THOX Azure subscription','The CLI account must match the intended tenant and subscription.'],
 ['resource_group, location','A dedicated deployment resource group and allowed region','Record its purpose, expected cost and cleanup owner.'],
 ['vm_name, admin_username','Unique VM and Linux admin names','Use the repository validation rules; do not reuse a production target.'],
 ['ssh_public_key_path','An existing administrator public key file','Public key only. Keep private keys outside the package and parameters.'],
 ['storage_account, storage_resource_group','An authorized existing private Storage account','Confirm network access from the VNet, TLS and container policy.'],
 ['container','An existing private artifact container','The CLI derives a content-addressed blob name from the full ZIP SHA-256 and verifies upload readback.'],
 ['image_version','An exact resolved Ubuntu Marketplace image version','Do not leave latest or an authoring placeholder in the deployment plan.'],
 ['Private access','Default RunCommand acceptance; optional private SSH/Bastion','Set enable_private_ssh for interactive access. Optional enable_bastion creates an additional billable Standard Bastion service; no public VM IP.'],
 ]),
 h('Access needed by the operator'),
 p('The authenticated operator needs authority to create the resource-group resources and assign/use the managed identity and its container-scoped Blob Data Reader role. Data-plane upload permission is distinct from Azure resource creation. Role assignment often needs additional RBAC administration authority. A subscription Contributor assignment alone must not be assumed to grant every operation.'),
 code('az account show\naz account set --subscription "$THOX_AZURE_SUBSCRIPTION_ID"\npython3 azure/deploy.py resolve-image \\\n  --config azure/deployment.example.json'),
 p('Set THOX_AZURE_SUBSCRIPTION_ID to the approved subscription ID. Inspect the selected account and use the same exact ID in the configuration. The resolve-image subcommand prints available source image information through Azure CLI; copy an exact approved version into azure/deployment.example.json or a separate private operator configuration. The subsequent prepare step writes the resolved, non-secret plan.'),

 ]),
('build','04 / build','Build the kernel, then bind the release bytes',[
 p('Work from the reviewed THOX source revision. Preserve the original Ginux Apache-2.0 license and notice and all corresponding source modifications. The kernel build uses Rust 1.99.0 and the x86_64-unknown-uefi and x86_64-unknown-none targets, GNU Make, Clang and the pinned Ginux source.'),
 code('rustup toolchain install 1.99.0 --profile minimal \\\n  --component clippy --component rustfmt\nrustup target add --toolchain 1.99.0 \\\n  x86_64-unknown-uefi x86_64-unknown-none\nbash module-ginux/scripts/build-native.sh'),
 p('The native build writes module-ginux/artifacts/GINUX.EFI, build-receipt.json, SHA256SUMS and attribution. The receipt binds the upstream source, ordered THOX banner/Azure/startup patches, lockfile and compiled payload. Startup fixes cover Linux auxv stack layout, local TCP lifetime, detached output/restart and an invalid-pointer fixture. A rebuild needs its own receipt and acceptance; byte-for-byte reproducibility is not assumed.'),
 code('(cd module-ginux/artifacts && sha256sum --strict -c SHA256SUMS)\nexport THOX_RELEASE_ZIP=/absolute/path/THOX_Ginux_Azure_Release.zip\npython3 azure/package_release.py --source . \\\n  --output "$THOX_RELEASE_ZIP" \\\n  --source-commit "$(git rev-parse HEAD)"'),
 p('The packaging command creates THOX_Ginux_Azure_Release.zip from a reviewed source checkout; --source-commit must identify that source. Git excludes GINUX.EFI: the runtime ZIP contains the actual compiled payload. Only required kernel, launcher, installer and provenance files enter its allowlist. The release manifest binds every admitted file. Azure verifies the complete ZIP SHA-256 before extraction or execution.'),
 table(['Release root path','Purpose'],[
 ['module-ginux/artifacts/GINUX.EFI','Actual compiled kernel payload.'],
 ['module-ginux/artifacts/build-receipt.json and SHA256SUMS','Compile provenance and exact payload integrity inventory.'],
 ['module-ginux/artifacts/GINUX_LICENSE and GINUX_NOTICE','Preserved upstream attribution.'],
 ['module-ginux/scripts/run-vm.sh','Validated, constrained QEMU guest launcher.'],
 ['ssd-module/install_host.py and preflight.py','Verified installation as ordinary host files.'],
 ['release-manifest.json','Release allowlist and per-file hashes.'],
 ]),
 p('Publish the release only to the intended private storage container. Do not place credentials, source agent instructions, template masters, private user data or temporary debug images inside the executable artifact.'),
 ]),
('deployment','05 / deploy','Prepare locally, upload privately, review, then deploy',[
 p('Run these commands from the repository root on a machine with Azure CLI, Python and the authorized Azure login. Set THOX_RELEASE_ZIP to the actual generated ZIP path. Edit the configuration file with real operator inputs before preparation.'),
 code('export THOX_RELEASE_ZIP=/absolute/path/THOX_Ginux_Azure_Release.zip\nexport THOX_DEPLOY_PLAN=/absolute/path/thox-ginux-deployment-plan\npython3 azure/deploy.py prepare \\\n  --config azure/deployment.example.json \\\n  --artifact "$THOX_RELEASE_ZIP" --out "$THOX_DEPLOY_PLAN"\npython3 azure/deploy.py upload \\\n  --config azure/deployment.example.json \\\n  --artifact "$THOX_RELEASE_ZIP"'),
 p('The artifact object name is content-addressed under sha256/<ZIP digest>/; no blob_name field is accepted. Check the plan subscription, region, image version, private access, NAT and identity scope. Upload must match its digest. First deployment requires a dedicated empty compute resource group; retries refuse any resource without matching thox-project and thox-deployment ownership tags. Names alone never establish ownership.'),
 code('python3 azure/deploy.py validate --plan "$THOX_DEPLOY_PLAN"\npython3 azure/deploy.py what-if --plan "$THOX_DEPLOY_PLAN"\npython3 azure/deploy.py deploy --plan "$THOX_DEPLOY_PLAN"'),
 p('Server-side validate checks the ARM deployment against Azure. What-if previews planned infrastructure changes. Deploy creates billable resources. Review validation and what-if output before that step. Do not accept an unexpected public endpoint, broad role grant, production resource replacement or a different subscription.'),
 h('Bootstrap behavior'),
 p('Cloud-init installs the host dependencies and runs the integrity-bound bootstrap. The managed identity obtains a short-lived IMDS token at runtime, reads the private artifact, verifies the complete ZIP digest and strict manifest, and invokes the trusted host installer. Tokens are kept out of normal output. Role assignments can take time to propagate; bounded retries belong to the bootstrap, with clear failure logging.'),
 note('A successful ARM deployment establishes infrastructure provisioning only. Cloud-init completion, kernel console boot, domain behavior and persistence each require their own evidence. Do not mark the deployment accepted from an Azure resource status alone.'),
 ]),
('verification','06 / acceptance','Verify the host, the payload and the running kernel separately',[
 p('The default template keeps SSH ingress closed and creates no Bastion. Use Azure RunCommand to retrieve acceptance receipts without opening a VM public endpoint. Set the resource-group and VM-name variables from the reviewed configuration. For an interactive console, explicitly enable the narrow private SSH rule and an existing private route or the optional billable Standard Bastion service.'),
 code('az vm run-command invoke \\\n  --subscription "$THOX_AZURE_SUBSCRIPTION_ID" \\\n  --resource-group "$THOX_AZURE_RESOURCE_GROUP" \\\n  --name "$THOX_AZURE_VM_NAME" --command-id RunShellScript \\\n  --scripts \\\n  \'cloud-init status --wait\' \\\n  \'cat /opt/thox/ginux/azure-install-receipt.json\' \\\n  \'cat /var/log/thox-ginux/guest-smoke.json\''),
 p('After private SSH/Bastion access is established, run sudo -iu thoxginux thox-ginux for the actual guest terminal. Azure Serial Console reaches Ubuntu, not automatically Ginux. The Azure bootstrap records its smoke test in /var/log/thox-ginux/guest-smoke.json and guest-smoke.log. Its installer receipt is separate from the Linux host-install receipt. The guest account home is /var/lib/thox-ginux. At ginux>, begin with status, components, domain list and help. End with shutdown for a clean guest exit. Do not close the host or deallocate the VM while guest configuration is being written.'),
 table(['Gate','Evidence to retain','Acceptance boundary'],[
 ['Host provisioned','Azure deployment outputs, image version, cloud-init result','No public IP; intended identity and resource group.'],
 ['Artifact verified','ZIP SHA-256, manifest, EFI and receipt hashes','Match the reviewed release, not merely a successful HTTP download.'],
 ['Controller boot','Exact serial banner and successful status/help/shutdown transcript','A kernel console pass does not prove arbitrary Linux programs.'],
 ['Domain execution','Embedded init marker, detached state, stop/start/restart and full errors','Bind the actual test to the delivered EFI; arbitrary Linux compatibility remains separate.'],
 ['Persistence','Clean shutdown and separate reboot/recovery transcript','Do not infer writable Linux-domain filesystem durability from saved configuration.'],
 ['Azure host acceptance','Private SSH reachability, reboot, disk/state behavior, policy and costs','Local QEMU tests do not replace live Azure acceptance.'],
 ]),
 h('Current recorded outcome'),
 table(['Area','Actual status'],[[key.replace('_',' ').title(),value] for key,value in val.items()]),
 p('Validation strings are generated from validation.json alongside this guide. Change them only after reviewing the corresponding current source/hash-bound logs. Prior-session receipts remain historical and are not silently promoted to new Azure results.'),
 ]),
('master-image','07 / master image','Customize and capture the Linux host after acceptance',[
 p('The initial Azure route uses an endorsed Marketplace Ubuntu image and cloud-init. That is a reproducible deployment definition, not a prebuilt VHD containing a native Azure Ginux kernel. A reusable THOX master image is a separate output produced from an accepted disposable Linux image-build VM.'),
 bullets([
 'Record the exact Ubuntu image version, host package inventory, THOX artifact hash, source revision and successful acceptance results.',
 'Customize only the Linux host surfaces required by the product. Install approved themes/apps or model runtimes as separately versioned components; preserve licensing and update responsibilities.',
 'Remove build credentials, transient IMDS/session material, test users and private data. Decide deliberately whether the distributed image retains only immutable kernel payload or also seeded guest state.',
 'Stop all guest instances cleanly. Confirm no guest volume is in use. Do not bake test passwords, private SSH keys or machine identity into an image.',
 'Generalize only a disposable image-build VM using the applicable Microsoft Linux preparation procedure. Deprovisioning can remove accounts and invalidate access; never run it automatically against the operational demo VM.',
 'Capture into an explicitly named Azure Compute Gallery image definition/version with the correct generation/security capabilities. Retain the managed image/version IDs, source disk identity and artifact hashes.',
 'Deploy a fresh VM from that captured version and repeat private access, cloud-init/provisioning, kernel, reboot and persistence checks before distributing it.'
 ]),
 h('VHD export rules'),
 p('If an offline VHD is required, use the Azure Linux image-preparation workflow and its fixed VHD, boot/provisioning and alignment requirements. A GINUX.EFI executable or QEMU raw guest volume is not a valid Azure OS VHD. Native Azure Ginux support would require Hyper-V/VMBus storage and network drivers plus Azure provisioning behavior that this variant does not supply. [S04–S05]'),
 note('A captured Linux host image does not become a Windows AVD session host. A graphical Linux desktop is a separate managed-VM desktop integration, and GPU rendering requires a GPU size, drivers and an actual rendering test.'),
 p('Keep image capture and cleanup explicit. Retain a rollback version and deployment manifest. Do not overwrite a stable image version or delete a production gallery/resource group as part of an example command.'),
 ]),
('recovery','08 / recovery and sources','Recover without widening access or losing evidence',[
 table(['Symptom','Check','Bounded response'],[
 ['Blob download denied','Identity assignment, container scope, RBAC propagation and storage network policy','Correct the intended identity/scope; never make the container public or paste a SAS into cloud-init.'],
 ['Packages cannot download','NAT attachment, route/NSG/firewall and DNS','Restore the approved egress path; NSG allow rules alone do not provide NAT.'],
 ['Cloud-init incomplete','cloud-init status and restricted bootstrap logs','Retain failure output; retry the documented unit/step after cause is fixed.'],
 ['No SSH route','Existing private connectivity, Bastion target and approved source CIDR','Keep the VM private. Do not add 0.0.0.0/0 port22 as a shortcut.'],
 ['Ginux IOMMU/EFI panic','Actual QEMU command and matching OVMF pair','Use the tested 2 GiB/48-bit-IOMMU profile; preserve kernel validation.'],
 ['Domain start fails','Named domain, image identity and full serial output','Keep the runtime gate failed until a source-bound fix passes.'],
 ['Unexpected running costs','Dedicated resource-group inventory and owner','Deallocate or remove only the confirmed disposable deployment through an explicit operator action.'],
 ]),
 p('Cleanup must target the dedicated resource group recorded in the reviewed plan. List its resources first, confirm that shared storage/Bastion/gallery resources are outside that deletion scope, then perform an explicit Azure CLI or portal deletion. Preserve the final logs, artifact hashes and image/deployment IDs before cleanup.'),
 h('Sources and revision'),
 p('Primary references below were reviewed for this engineering guide on 2026-10-29. Microsoft documentation can change; deployment-time ARM validation and regional/SKU availability remain required.'),
 ('sources',),

 ])]

# Give current evidence its own substantive page rather than splitting a status table.
for n,page in enumerate(pages):
 if page[0]=='verification':
  ident,eyebrow,title,blocks=page
  cut=next(i for i,b in enumerate(blocks) if b[0]=='h' and b[1]=='Current recorded outcome')
  status=blocks[cut+1:]
  pages[n]=(ident,eyebrow,title,blocks[:cut])
  history=(ROOT.parent.parent/'evidence/azure/lifecycle-cold.log').read_text(errors='replace').replace('\r','')
  lines=history.splitlines()
  wanted=['Build profile:', 'ginux> domain start thoxprobe', 'thoxprobe: running (detached)', '100    0', 'GINUX_KERNEL_OK']
  chosen=[next(line for line in lines if line.startswith(prefix)) for prefix in wanted]
  evidence=[p('Current local results are separate from live Azure deployment. Retain source, EFI hash, commands and environment for each pass. Azure architecture, implementation and kernel diagnosis agents contributed; no external acknowledgement is implied.')]+status+[h('Authentic current lifecycle evidence'),code('\n'.join(chosen)),p('Exact lines from evidence/azure/lifecycle-cold.log for the EFI identified above. lifecycle-results.json records 17 cold-boot and 5 recovery commands and both log hashes. This is local QEMU proof; Azure, Docker, KVM and physical acceptance remain unrun. The October 28 predecessor evidence is preserved separately.')]
  pages.insert(n+1,('evidence','07 / evidence','Current tests and acceptance receipts',evidence))
  break
pages=[(i,'08 / master image' if i=='master-image' else '09 / recovery and sources' if i=='recovery' else e,t,b) for i,e,t,b in pages]

SVG='''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 530" role="img" aria-labelledby="t d"><title id="t">Azure host and Ginux guest boundaries</title><desc id="d">Private administrator access enters an Ubuntu Azure virtual machine. A managed identity fetches a SHA-256-pinned artifact from private Blob Storage. QEMU runs the independent Ginux kernel inside the Ubuntu host.</desc><rect width="1000" height="530" fill="#FAFAFA"/><g font-family="Inter,Arial,sans-serif" fill="#101418"><rect x="180" y="35" width="790" height="450" rx="14" fill="#E7F6EE" stroke="#05A451" stroke-width="2"/><text x="205" y="65" font-size="19" font-weight="700">Azure VNet: private VM, explicit outbound connectivity</text><rect x="205" y="90" width="490" height="350" rx="12" fill="white" stroke="#52525B"/><text x="225" y="122" font-size="19" font-weight="700">Ubuntu 24.04 Gen2 Azure VM</text><text x="225" y="148" font-size="15">Trusted Launch · Secure Boot · vTPM · SSH</text><rect x="225" y="175" width="450" height="235" rx="10" fill="#F4F4F5" stroke="#A1A1AA"/><text x="245" y="204" font-size="18" font-weight="700">QEMU TCG / Q35 / OVMF</text><text x="245" y="230" font-size="15">1 vCPU · 2 GiB · virtual IOMMU 48</text><rect x="245" y="255" width="410" height="125" rx="9" fill="#09090B"/><text x="265" y="288" font-size="18" font-weight="700" fill="#FAFAFA">THOX Ginux kernel</text><text x="265" y="316" font-size="15" fill="#FAFAFA">EFI boot, ring-3 controller, Linux ABI</text><text x="265" y="345" font-size="14" fill="#A1A1AA">Domain execution has its own acceptance gate</text><rect x="725" y="100" width="220" height="145" rx="10" fill="white" stroke="#52525B"/><text x="745" y="132" font-size="18" font-weight="700">Private Blob</text><text x="745" y="162" font-size="15">Versioned release ZIP</text><text x="745" y="188" font-size="15">Whole-artifact SHA-256</text><text x="745" y="217" font-size="14">Managed identity read</text><rect x="725" y="290" width="220" height="115" rx="10" fill="white" stroke="#52525B"/><text x="745" y="322" font-size="18" font-weight="700">NAT Gateway</text><text x="745" y="351" font-size="15">Explicit outbound only</text><text x="745" y="377" font-size="14">Package/artifact access</text><rect x="15" y="170" width="140" height="125" rx="10" fill="white" stroke="#52525B"/><text x="32" y="202" font-size="17" font-weight="700">Administrator</text><text x="32" y="230" font-size="14">Bastion / VPN /</text><text x="32" y="253" font-size="14">private SSH</text><path d="M155 232H205M195 224L205 232L195 240" stroke="#047C3D" stroke-width="3" fill="none"/><path d="M725 172H695M705 164L695 172L705 180" stroke="#047C3D" stroke-width="3" fill="none"/><text x="218" y="470" font-size="14">Azure boots Linux. QEMU boots Ginux. No native Azure Ginux or Windows AVD claim.</text></g></svg>'''
(ASSETS/'azure-boundaries.svg').write_text(SVG)

# Build HTML by retaining official documentation shell, controls, CSS and semantic structure.
def html_block(block):
 kind=block[0]
 if kind=='p':return '<p>'+html.escape(block[1])+'</p>'
 if kind=='h':return '<h3>'+html.escape(block[1])+'</h3>'
 if kind=='note':return '<div class="callout"><strong>Evidence boundary</strong><p>'+html.escape(block[1])+'</p></div>'
 if kind=='code':return '<pre><code>'+html.escape(block[1])+'</code></pre>'
 if kind=='bullets':return '<ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in block[1])+'</ul>'
 if kind=='table':return '<div class="scroll-table"><table><caption>Table: '+html.escape(block[1][0])+' and related values</caption><thead><tr>'+''.join('<th scope="col">'+html.escape(x)+'</th>' for x in block[1])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in block[2])+'</tbody></table></div>'
 if kind=='figure':return '<figure><img src="assets/azure-boundaries.svg" alt="Private Azure Ubuntu host contains the QEMU Ginux research guest; private Blob and NAT are separate services"><figcaption>Figure 1. Architecture illustration, not a deployed-resource screenshot. Source: THOX Azure variant design, 2026-10-29.</figcaption></figure>'
 if kind=='sources':return '<ol class="sources">'+''.join('<li><strong>'+i+'</strong> <a href="'+u+'">'+html.escape(t)+'</a></li>' for i,t,u in sources)+'</ol>'
 raise ValueError(kind)
main='''<p class="eyebrow">Azure deployment / engineering guide</p><h1>ThoxOS Ginux Azure variant</h1><p class="lede">Build the customized research kernel, provision a private Azure Linux host, and preserve the evidence boundary from local build to cloud acceptance.</p><dl class="meta"><div><dt>Owner / audience</dt><dd>Sadie Weaving / Tommy, Craig and authorized engineers</dd></div><div><dt>Document / version</dt><dd>THOX-GINUX-AZURE-001 / 0.2.0-azure-candidate</dd></div><div><dt>Product stage / document status</dt><dd>ENGINEERING CANDIDATE / DRAFT</dd></div><div><dt>As-of / classification</dt><dd>2026-10-29 / CONFIDENTIAL</dd></div></dl>'''
for ident,eyebrow,title,blocks in pages:main+='<section id="'+ident+'" class="section print-page"><p class="eyebrow">'+eyebrow+'</p><h2>'+html.escape(title)+'</h2>'+''.join(html_block(b) for b in blocks)+'</section>'
out=master.replace('THOX.ai | Documentation template','THOX.ai | Ginux Azure deployment guide').replace('THOX.ai official reusable editorial template v1.0.0','THOX Ginux Azure engineering deployment guide; source and evidence bound.').replace('../assets/thox-horizontal-dark.svg','assets/thox-horizontal-dark.svg')
out=re.sub(r'<nav class="toc".*?</nav>','<nav class="toc" aria-label="Documentation sections"><p class="label">Guide map</p>'+''.join('<a href="#'+x[0]+'">'+x[1]+'</a>' for x in pages)+'</nav>',out,flags=re.S)
out=re.sub(r'<main id="main">.*?</main>','<main id="main">'+main+'</main>',out,flags=re.S)
out=out.replace('TEMPLATE v1.0.0 · [Document ID / version] · [Date]','THOX-GINUX-AZURE-001 / 0.2.0 ·2026-10-29').replace('</head>','<link rel="stylesheet" href="azure-guide.css"></head>')
(HTML/'THOX_Ginux_Azure_Deployment_Guide.html').write_text(out)
(HTML/'azure-guide.css').write_text('''pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--surface,#F4F4F5);border:1px solid var(--line,#D4D4D8);padding:1rem;border-radius:.4rem;font:12px/1.55 "JetBrains Mono",monospace}figure{margin:1.4rem 0}figure img{width:100%;height:auto}figcaption{font-size:.8rem;color:var(--muted,#52525B)}.sources{font-size:.82rem}.sources li{margin:.4rem 0}table{font-size:.86rem}@media print{.print-page{break-before:page}pre{font-size:9px}table{font-size:9px}.sources{font-size:8px}}''')

# Standalone PDF uses the same content and exact corporate artwork.
pdfmetrics.registerFont(TTFont('Inter','/usr/local/share/fonts/Inter.ttf'))
pdfmetrics.registerFont(TTFont('THOXMono','/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'))
styles=getSampleStyleSheet()
for key in ['Normal','BodyText']:styles[key].fontName='Inter';styles[key].fontSize=9.2;styles[key].leading=13.8;styles[key].textColor=colors.HexColor(INK)
styles.add(ParagraphStyle(name='THOXTitle',fontName='Inter',fontSize=25,leading=29,textColor=colors.HexColor(INK),spaceAfter=14))
styles.add(ParagraphStyle(name='THOXH2',fontName='Inter',fontSize=20,leading=25,textColor=colors.HexColor(INK),spaceAfter=14))
styles.add(ParagraphStyle(name='THOXH3',fontName='Inter',fontSize=11,leading=16,textColor=colors.HexColor('#047C3D'),spaceBefore=8,spaceAfter=5))
styles.add(ParagraphStyle(name='THOXEyebrow',fontName='Inter',fontSize=9,leading=12,textColor=colors.HexColor('#047C3D'),spaceAfter=7))
styles.add(ParagraphStyle(name='THOXSmall',fontName='Inter',fontSize=7.5,leading=10.2,textColor=colors.HexColor(MUTED)))
styles.add(ParagraphStyle(name='THOXCell',fontName='Inter',fontSize=8.0,leading=11.3,textColor=colors.HexColor(INK)))
styles.add(ParagraphStyle(name='THOXHeadCell',parent=styles['THOXCell'],textColor=colors.white))
styles.add(ParagraphStyle(name='THOXMono',fontName='THOXMono',fontSize=7.7,leading=11,textColor=colors.HexColor(INK),backColor=colors.HexColor('#F4F4F5'),borderPadding=8,spaceAfter=10))

def para(s,style='BodyText'):return Paragraph(html.escape(s),styles[style])
class BoundaryFigure(Flowable):
 def __init__(self):Flowable.__init__(self);self.width=470;self.height=205
 def draw(self):
  c=self.canv;c.saveState();c.translate(30,0);c.scale(0.87,0.87);c.setStrokeColor(colors.HexColor(BRAND));c.setFillColor(colors.HexColor('#E7F6EE'));c.roundRect(77,15,390,210,7,fill=1)
  c.setFont('Inter',9);c.setFillColor(colors.HexColor(INK));c.drawString(88,208,'Azure private VNet + explicit outbound')
  c.setFillColor(colors.white);c.setStrokeColor(colors.HexColor('#71717A'));c.roundRect(89,40,245,151,6,fill=1)
  c.setFillColor(colors.HexColor(INK));c.setFont('Inter',10);c.drawString(101,173,'Ubuntu 24.04 Gen2 host')
  c.setFont('Inter',7.6);c.drawString(101,157,'Trusted Launch / Secure Boot / vTPM / SSH')
  c.setFillColor(colors.HexColor('#F4F4F5'));c.roundRect(101,51,221,93,5,fill=1)
  c.setFillColor(colors.HexColor(INK));c.setFont('Inter',9);c.drawString(111,128,'QEMU TCG / Q35 / OVMF')
  c.setFont('Inter',7.6);c.drawString(111,113,'1 vCPU / 2 GiB / virtual IOMMU 48')
  c.setFillColor(colors.HexColor('#09090B'));c.roundRect(111,61,200,40,4,fill=1)
  c.setFillColor(colors.white);c.setFont('Inter',9);c.drawString(121,85,'THOX Ginux kernel + controller')
  c.setFont('Inter',7);c.drawString(121,71,'Domain execution has its own acceptance gate')
  for x,y,w,h,label,detail in [(349,130,107,61,'Private Blob','Identity read + ZIP hash'),(349,51,107,61,'NAT Gateway','Explicit outbound'),(0,97,66,67,'Admin','Bastion/VPN/SSH')]:
   c.setStrokeColor(colors.HexColor('#71717A'));c.setFillColor(colors.white);c.roundRect(x,y,w,h,5,fill=1);c.setFillColor(colors.HexColor(INK));c.setFont('Inter',8);c.drawString(x+7,y+h-18,label);c.setFont('Inter',6.6);c.drawString(x+7,y+h-34,detail)
  c.setStrokeColor(colors.HexColor('#047C3D'));c.line(66,131,89,131);c.line(349,160,334,160)
  c.setFont('Inter',7);c.setFillColor(colors.HexColor(MUTED));c.drawString(88,26,'Architecture illustration. No deployed-resource screenshot is implied.');c.restoreState()

def pdf_table(headers,rows,widths=None):
 data=[[para(x,'THOXHeadCell') for x in headers]]+[[para(str(x),'THOXCell') for x in row] for row in rows]
 widths=widths or ([470/len(headers)]*len(headers))
 t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#047C3D')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F4F4F5')]),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#047C3D')),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#D4D4D8'))]));return t
story=[]
for i,(ident,eyebrow,title,blocks) in enumerate(pages):
 if i:
  while story and isinstance(story[-1],Spacer):story.pop()
  story.append(PageBreak())
 story+=[para(eyebrow.upper(),'THOXEyebrow'),para(title,'THOXTitle' if i==0 else 'THOXH2')]
 if i==0:story+=[para('ThoxOS Ginux Azure variant · THOX-GINUX-AZURE-001 / 0.2.0-azure-candidate','THOXSmall'),para('2026-10-29 · CONFIDENTIAL · Product: engineering candidate · Document: DRAFT','THOXSmall'),Spacer(1,12)]
 for b in blocks:
  kind=b[0]
  if kind=='p':story += [para(b[1]),Spacer(1,7)]
  elif kind=='h':story += [para(b[1],'THOXH3')]
  elif kind=='note':story += [pdf_table(['Evidence boundary'],[[b[1]]]),Spacer(1,9)]
  elif kind=='code':story += [Preformatted(b[1],styles['THOXMono'],maxLineLength=87),Spacer(1,4)]
  elif kind=='table':story += [pdf_table(b[1],b[2],b[3]),Spacer(1,10)]
  elif kind=='figure':story += [BoundaryFigure(),para('Figure 1. Architecture illustration. Source: THOX Azure variant design, 2026-10-29.','THOXSmall'),Spacer(1,10)]
  elif kind=='bullets':
   for item in b[1]:story += [para('• '+item),Spacer(1,6)]
  elif kind=='sources':
   for sid,title,url in sources:story.append(Paragraph(html.escape(sid+' '+title)+' · <link href="'+url+'" color="#047C3D">Microsoft / source link</link>',styles['THOXSmall']))
   story.append(Spacer(1,8))

def header(c,doc):
 c.saveState();c.drawImage(str(ASSETS/'thox-horizontal-dark.png'),48,754,width=108,height=37.42,mask='auto',preserveAspectRatio=True)
 c.setFont('Inter',7.5);c.setFillColor(colors.HexColor(MUTED));c.drawRightString(547,772,'AZURE ENGINEERING GUIDE / CONFIDENTIAL')
 c.setStrokeColor(colors.HexColor(BRAND));c.setLineWidth(1);c.line(48,747,547,747)
 c.setFont('Inter',7);c.drawString(48,28,'THOX.ai LLC · Your AI. Your Data. Your Rules.™');c.drawRightString(547,28,f'THOX-GINUX-AZURE-001 / 0.2 · {doc.page}');c.restoreState()
pdf=ROOT/'THOX_Ginux_Azure_Deployment_Guide.pdf'
SimpleDocTemplate(str(pdf),pagesize=(595.28,841.89),leftMargin=62,rightMargin=63.28,topMargin=107,bottomMargin=53,title='ThoxOS Ginux Azure Deployment Guide',author='Sadie Weaving, AI-powered THOX coordinator').build(story,onFirstPage=header,onLaterPages=header)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
provenance={'template_system':'THOX Official Templates 1.0.0','master':'html/THOX_Documentation_Template_v1.0.0.html','master_sha256':sha(KIT/'html/THOX_Documentation_Template_v1.0.0.html'),'predecessor_source_baseline':'e88662bdc7e975753a5a049eb4b664bcee0db7e5','build_receipt_sha256':sha(ROOT.parent.parent/'module-ginux/artifacts/build-receipt.json'),'lifecycle_receipt_sha256':sha(ROOT.parent.parent/'evidence/azure/lifecycle-results.json'),'artifact_stage':'engineering-candidate','date':'2026-10-29','fonts':{'body':'Inter, locally available','technical_pdf':'DejaVu Sans Mono compatibility fallback; JetBrains Mono unavailable','technical_html':'JetBrains Mono declared with monospace fallback','font_binaries_distributed':False},'actual_status':val,'files':{str(p.relative_to(ROOT)):sha(p) for p in [pdf,HTML/'THOX_Ginux_Azure_Deployment_Guide.html',HTML/'thox-report.css',HTML/'thox-report.js',ASSETS/'azure-boundaries.svg',ASSETS/'thox-horizontal-dark.svg']}}
(ROOT/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
print(json.dumps({'pdf':str(pdf),'html':str(HTML/'THOX_Ginux_Azure_Deployment_Guide.html'),'pdf_sha256':sha(pdf),'html_sha256':sha(HTML/'THOX_Ginux_Azure_Deployment_Guide.html')}))
