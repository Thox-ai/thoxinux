#!/usr/bin/env bash
# Copyright (c) 2026 THOX.ai LLC. Licensed under the Apache License, Version 2.0.
# ThoxOS Ginux Edition: publish a VHD as an Azure Compute Gallery image version.
#
# The Linux counterpart of the master-image flow in Microsoft's "Prepare and
# customize a VHD image" guide: the image is already generalized (never booted,
# empty machine-id, no host keys, no login account), fixed and MiB-aligned, so
# it goes straight to a page blob and into a gallery image definition (Gen2,
# Linux, generalized, standard security). The script prints the image version
# resource ID that azure/azuredeploy.json takes as imageVersionId.
#
# Usage:
#   azure/publish-image.sh --vhd build/azure/thoxos-ginux-azure-desktop-0.2.0.vhd \
#       --resource-group thoxos-images --location eastus \
#       [--storage-account NAME] [--gallery thoxos_gallery] [--definition thoxos-ginux-desktop] \
#       [--version 0.2.0] [--publisher THOX] [--offer thoxos-ginux] [--sku desktop]
#
# Needs: Azure CLI 2.60+ signed in (az login) with rights to create storage and
# gallery resources, and the Storage Blob Data Contributor role on the account
# (uploads use Entra ID, never account keys). azcopy is used when installed.
set -euo pipefail

vhd=""
group=""
location=""
account=""
gallery="thoxos_gallery"
definition=""
version=""
publisher="THOX"
offer="thoxos-ginux"
sku=""

fail() {
    echo "publish-image: $*" >&2
    exit 1
}

while (($#)); do
    case "$1" in
    --vhd) vhd="${2:?}"; shift 2 ;;
    --resource-group) group="${2:?}"; shift 2 ;;
    --location) location="${2:?}"; shift 2 ;;
    --storage-account) account="${2:?}"; shift 2 ;;
    --gallery) gallery="${2:?}"; shift 2 ;;
    --definition) definition="${2:?}"; shift 2 ;;
    --version) version="${2:?}"; shift 2 ;;
    --publisher) publisher="${2:?}"; shift 2 ;;
    --offer) offer="${2:?}"; shift 2 ;;
    --sku) sku="${2:?}"; shift 2 ;;
    -h | --help) sed -n '3,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) fail "unknown argument: $1" ;;
    esac
done
[[ -n "$vhd" && -n "$group" && -n "$location" ]] || fail "--vhd, --resource-group and --location are required"
[[ -s "$vhd" ]] || fail "missing $vhd"
command -v az >/dev/null 2>&1 || fail "Azure CLI (az) is required"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$here/vhd_check.py" "$vhd" || fail "$vhd does not meet Azure's VHD rules"

name="$(basename "$vhd")"
# thoxos-ginux-azure-<desktop|headless>-<version>.vhd
if [[ "$name" =~ ^thoxos-ginux-azure-(desktop|headless)-([0-9]+\.[0-9]+\.[0-9]+)\.vhd$ ]]; then
    : "${sku:=${BASH_REMATCH[1]}}"
    : "${version:=${BASH_REMATCH[2]}}"
fi
[[ -n "$sku" && -n "$version" ]] || fail "pass --sku and --version (the file name did not carry them)"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "--version must be MAJOR.MINOR.PATCH"
: "${definition:=thoxos-ginux-$sku}"
if [[ -z "$account" ]]; then
    suffix="$(printf '%s' "$group/$location" | sha256sum | cut -c1-10)"
    account="thoxosimg$suffix"
fi
[[ "$account" =~ ^[a-z0-9]{3,24}$ ]] || fail "storage account name must be 3-24 lowercase letters or digits"

az account show --query id -o tsv >/dev/null 2>&1 || fail "not signed in; run az login"
subscription="$(az account show --query id -o tsv)"
echo "publish-image: subscription $subscription, group $group, $location"

az group create --name "$group" --location "$location" --output none
if ! az storage account show --name "$account" --resource-group "$group" --output none 2>/dev/null; then
    az storage account create --name "$account" --resource-group "$group" --location "$location" \
        --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 \
        --allow-blob-public-access false --output none
fi
account_id="$(az storage account show --name "$account" --resource-group "$group" --query id -o tsv)"
az storage container create --account-name "$account" --name vhds --auth-mode login --output none

blob_url="https://$account.blob.core.windows.net/vhds/$name"
echo "publish-image: uploading $name as a page blob"
if command -v azcopy >/dev/null 2>&1; then
    AZCOPY_AUTO_LOGIN_TYPE=AZCLI azcopy copy "$vhd" "$blob_url" --blob-type PageBlob
else
    az storage blob upload --account-name "$account" --container-name vhds --name "$name" \
        --file "$vhd" --type page --auth-mode login --overwrite --output none
fi

if ! az sig show --resource-group "$group" --gallery-name "$gallery" --output none 2>/dev/null; then
    az sig create --resource-group "$group" --gallery-name "$gallery" --location "$location" --output none
fi
if ! az sig image-definition show --resource-group "$group" --gallery-name "$gallery" \
    --gallery-image-definition "$definition" --output none 2>/dev/null; then
    az sig image-definition create --resource-group "$group" --gallery-name "$gallery" \
        --gallery-image-definition "$definition" --location "$location" \
        --publisher "$publisher" --offer "$offer" --sku "$sku" \
        --os-type Linux --os-state Generalized --hyper-v-generation V2 \
        --features "SecurityType=Standard IsAcceleratedNetworkSupported=False" \
        --description "ThoxOS Ginux Edition ($sku): ThoxOS on the Ginux Rust kernel under nested KVM. Research preview." \
        --output none
fi
echo "publish-image: creating image version $version (this replicates the VHD; it takes several minutes)"
az sig image-version create --resource-group "$group" --gallery-name "$gallery" \
    --gallery-image-definition "$definition" --gallery-image-version "$version" \
    --location "$location" --target-regions "$location" --replica-count 1 \
    --os-vhd-uri "$blob_url" --os-vhd-storage-account "$account_id" --output none
image_id="$(az sig image-version show --resource-group "$group" --gallery-name "$gallery" \
    --gallery-image-definition "$definition" --gallery-image-version "$version" --query id -o tsv)"
echo "publish-image: done"
echo "imageVersionId=$image_id"
