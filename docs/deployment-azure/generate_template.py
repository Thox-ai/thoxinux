#!/usr/bin/env python3
"""Generate the checked-in ARM JSON; no deployment or Azure credentials used."""
import json
from pathlib import Path


def template():
    params = {
        "location": {"type": "string", "defaultValue": "[resourceGroup().location]"},
        "vmName": {"type": "string", "minLength": 3, "maxLength": 32},
        "vmSize": {"type": "string", "defaultValue": "Standard_D4s_v5", "allowedValues": ["Standard_D4s_v5"]},
        "adminUsername": {"type": "string", "minLength": 3, "maxLength": 32},
        "sshPublicKey": {"type": "string", "minLength": 80},
        "ubuntuImageVersion": {"type": "string", "metadata": {"description": "An explicitly resolved Canonical ubuntu-24_04-lts server image version, never latest"}},
        "artifactStorageAccount": {"type": "string", "minLength": 3, "maxLength": 24},
        "artifactStorageResourceGroup": {"type": "string"},
        "artifactContainer": {"type": "string"},
        "cloudInit": {"type": "string", "metadata": {"description": "Non-secret cloud-init JSON/YAML; managed identity marker is resolved by ARM"}},
        "enablePrivateSsh": {"type": "bool", "defaultValue": False},
        "enableBastion": {"type": "bool", "defaultValue": False, "metadata": {"description": "Opt-in Standard Bastion creates separately billed service and public endpoint; VM remains private"}},
        "bastionSubnetPrefix": {"type": "string", "defaultValue": "10.42.0.0/26"},
        "adminSourceCidr": {"type": "string", "defaultValue": "10.42.0.0/24"},
        "vnetAddressPrefix": {"type": "string", "defaultValue": "10.42.0.0/16"},
        "subnetAddressPrefix": {"type": "string", "defaultValue": "10.42.1.0/24"},
    }
    variables = {
        "identityName": "[concat(parameters('vmName'), '-identity')]",
        "vnetName": "[concat(parameters('vmName'), '-vnet')]",
        "nsgName": "[concat(parameters('vmName'), '-nsg')]",
        "nicName": "[concat(parameters('vmName'), '-nic')]",
        "natName": "[concat(parameters('vmName'), '-nat')]",
        "natIpName": "[concat(parameters('vmName'), '-nat-ip')]",
        "blobReaderRoleId": "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1",
        "artifactContainerId": "[resourceId(subscription().subscriptionId, parameters('artifactStorageResourceGroup'), 'Microsoft.Storage/storageAccounts/blobServices/containers', parameters('artifactStorageAccount'), 'default', parameters('artifactContainer'))]",
        "roleName": "[guid(variables('artifactContainerId'), resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', variables('identityName')), variables('blobReaderRoleId'))]",
        "roleDeploymentName": "[concat(parameters('vmName'), '-artifact-access')]",
        "sshRule": [{"name": "PrivateSshFromAdminNetwork", "properties": {"priority": 100, "protocol": "Tcp", "access": "Allow", "direction": "Inbound", "sourceAddressPrefix": "[parameters('adminSourceCidr')]", "sourcePortRange": "*", "destinationAddressPrefix": "*", "destinationPortRange": "22"}}],
        "denyRule": [{"name": "DenyOtherInbound", "properties": {"priority": 4096, "protocol": "*", "access": "Deny", "direction": "Inbound", "sourceAddressPrefix": "*", "sourcePortRange": "*", "destinationAddressPrefix": "*", "destinationPortRange": "*"}}],
    }
    resources = [
        {"type": "Microsoft.ManagedIdentity/userAssignedIdentities", "apiVersion": "2023-01-31", "name": "[variables('identityName')]", "location": "[parameters('location')]"},
        {"type": "Microsoft.Authorization/roleAssignments", "apiVersion": "2022-04-01", "name": "[variables('roleName')]", "scope": "[variables('artifactContainerId')]", "dependsOn": ["[resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', variables('identityName'))]"], "properties": {"roleDefinitionId": "[subscriptionResourceId('Microsoft.Authorization/roleDefinitions', variables('blobReaderRoleId'))]", "principalId": "[reference(resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', variables('identityName')), '2023-01-31').principalId]", "principalType": "ServicePrincipal"}},
        {"type": "Microsoft.Network/publicIPAddresses", "apiVersion": "2024-05-01", "name": "[variables('natIpName')]", "location": "[parameters('location')]", "sku": {"name": "Standard"}, "properties": {"publicIPAllocationMethod": "Static"}},
        {"type": "Microsoft.Network/natGateways", "apiVersion": "2024-05-01", "name": "[variables('natName')]", "location": "[parameters('location')]", "sku": {"name": "Standard"}, "dependsOn": ["[resourceId('Microsoft.Network/publicIPAddresses', variables('natIpName'))]"], "properties": {"idleTimeoutInMinutes": 10, "publicIpAddresses": [{"id": "[resourceId('Microsoft.Network/publicIPAddresses', variables('natIpName'))]"}]}},
        {"type": "Microsoft.Network/networkSecurityGroups", "apiVersion": "2024-05-01", "name": "[variables('nsgName')]", "location": "[parameters('location')]", "properties": {"securityRules": "[concat(if(parameters('enablePrivateSsh'), variables('sshRule'), json('[]')), variables('denyRule'))]"}},
        {"type": "Microsoft.Network/virtualNetworks", "apiVersion": "2024-05-01", "name": "[variables('vnetName')]", "location": "[parameters('location')]", "dependsOn": ["[resourceId('Microsoft.Network/networkSecurityGroups', variables('nsgName'))]", "[resourceId('Microsoft.Network/natGateways', variables('natName'))]"], "properties": {"addressSpace": {"addressPrefixes": ["[parameters('vnetAddressPrefix')]" ]}, "subnets": [{"name": "host", "properties": {"addressPrefix": "[parameters('subnetAddressPrefix')]", "defaultOutboundAccess": False, "networkSecurityGroup": {"id": "[resourceId('Microsoft.Network/networkSecurityGroups', variables('nsgName'))]"}, "natGateway": {"id": "[resourceId('Microsoft.Network/natGateways', variables('natName'))]"}}}]}},
        {"type": "Microsoft.Network/networkInterfaces", "apiVersion": "2024-05-01", "name": "[variables('nicName')]", "location": "[parameters('location')]", "dependsOn": ["[resourceId('Microsoft.Network/virtualNetworks', variables('vnetName'))]"], "properties": {"enableAcceleratedNetworking": True, "ipConfigurations": [{"name": "primary", "properties": {"privateIPAllocationMethod": "Dynamic", "subnet": {"id": "[resourceId('Microsoft.Network/virtualNetworks/subnets', variables('vnetName'), 'host')]"}}}]}},
        {"type": "Microsoft.Compute/virtualMachines", "apiVersion": "2024-07-01", "name": "[parameters('vmName')]", "location": "[parameters('location')]", "dependsOn": ["[resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', variables('identityName'))]", "[extensionResourceId(variables('artifactContainerId'), 'Microsoft.Authorization/roleAssignments', variables('roleName'))]", "[resourceId('Microsoft.Network/networkInterfaces', variables('nicName'))]"], "identity": {"type": "UserAssigned", "userAssignedIdentities": {"[resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', variables('identityName'))]": {}}}, "properties": {"hardwareProfile": {"vmSize": "[parameters('vmSize')]"}, "securityProfile": {"securityType": "TrustedLaunch", "uefiSettings": {"secureBootEnabled": True, "vTpmEnabled": True}}, "storageProfile": {"imageReference": {"publisher": "Canonical", "offer": "ubuntu-24_04-lts", "sku": "server", "version": "[parameters('ubuntuImageVersion')]"}, "osDisk": {"createOption": "FromImage", "diskSizeGB": 128, "managedDisk": {"storageAccountType": "Premium_LRS"}}}, "osProfile": {"computerName": "[parameters('vmName')]", "adminUsername": "[parameters('adminUsername')]", "customData": "[base64(replace(parameters('cloudInit'), '__IDENTITY_CLIENT_ID__', reference(resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', variables('identityName')), '2023-01-31').clientId))]", "linuxConfiguration": {"disablePasswordAuthentication": True, "provisionVMAgent": True, "ssh": {"publicKeys": [{"path": "[format('/home/{0}/.ssh/authorized_keys', parameters('adminUsername'))]", "keyData": "[parameters('sshPublicKey')]"}]}}}, "networkProfile": {"networkInterfaces": [{"id": "[resourceId('Microsoft.Network/networkInterfaces', variables('nicName'))]", "properties": {"primary": True}}]}, "diagnosticsProfile": {"bootDiagnostics": {"enabled": True}}}},
    ]
    outputs = {
        "vmResourceId": {"type": "string", "value": "[resourceId('Microsoft.Compute/virtualMachines', parameters('vmName'))]"},
        "privateIp": {"type": "string", "value": "[reference(resourceId('Microsoft.Network/networkInterfaces', variables('nicName')), '2024-05-01').ipConfigurations[0].properties.privateIPAddress]"},
        "artifactIdentityClientId": {"type": "string", "value": "[reference(resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', variables('identityName')), '2023-01-31').clientId]"},
        "route": {"type": "string", "value": "Ubuntu Gen2 Azure host + THOX Ginux QEMU TCG research guest; no AVD/native Ginux claim"},
    }
    # ARM RG deployments may not directly target a resource in another RG.
    # Run the extension role assignment in a nested deployment whose target is
    # the artifact's actual resource group; resolve the identity in the parent.
    assignment = next(resource for resource in resources if resource["type"] == "Microsoft.Authorization/roleAssignments")
    resources.remove(assignment)
    access_template = {
        "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#", "contentVersion": "1.0.0.0",
        "parameters": {name: {"type": "string"} for name in ("identityPrincipalId", "artifactStorageAccount", "artifactContainer", "roleAssignmentName")},
        "resources": [{"type": "Microsoft.Authorization/roleAssignments", "apiVersion": "2022-04-01", "name": "[parameters('roleAssignmentName')]", "scope": "[resourceId('Microsoft.Storage/storageAccounts/blobServices/containers', parameters('artifactStorageAccount'), 'default', parameters('artifactContainer'))]", "properties": {"roleDefinitionId": "[subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')]", "principalId": "[parameters('identityPrincipalId')]", "principalType": "ServicePrincipal"}}],
    }
    resources.insert(1, {"type": "Microsoft.Resources/deployments", "apiVersion": "2022-09-01", "name": "[variables('roleDeploymentName')]", "resourceGroup": "[parameters('artifactStorageResourceGroup')]", "dependsOn": ["[resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', variables('identityName'))]"], "properties": {"mode": "Incremental", "expressionEvaluationOptions": {"scope": "inner"}, "parameters": {"identityPrincipalId": {"value": "[reference(resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', variables('identityName')), '2023-01-31').principalId]"}, "artifactStorageAccount": {"value": "[parameters('artifactStorageAccount')]"}, "artifactContainer": {"value": "[parameters('artifactContainer')]"}, "roleAssignmentName": {"value": "[variables('roleName')]"}}, "template": access_template}})
    vm = next(resource for resource in resources if resource["type"] == "Microsoft.Compute/virtualMachines")
    vm["dependsOn"] = [dependency for dependency in vm["dependsOn"] if "extensionResourceId" not in dependency]
    vm["dependsOn"].append("[resourceId(parameters('artifactStorageResourceGroup'), 'Microsoft.Resources/deployments', variables('roleDeploymentName'))]")
    # Bastion is opt-in. Default management uses Azure VM Run Command through
    # the VM agent and exposes no inbound endpoint on the virtual machine.
    vnet = next(resource for resource in resources if resource["type"] == "Microsoft.Network/virtualNetworks")
    variables["hostSubnets"] = vnet["properties"]["subnets"]
    variables["bastionSubnets"] = [{"name": "AzureBastionSubnet", "properties": {"addressPrefix": "[parameters('bastionSubnetPrefix')]"}}]
    vnet["properties"]["subnets"] = "[concat(variables('hostSubnets'), if(parameters('enableBastion'), variables('bastionSubnets'), json('[]')))]"
    resources.extend([
        {"condition": "[parameters('enableBastion')]", "type": "Microsoft.Network/publicIPAddresses", "apiVersion": "2024-05-01", "name": "[concat(parameters('vmName'), '-bastion-ip')]", "location": "[parameters('location')]", "sku": {"name": "Standard"}, "properties": {"publicIPAllocationMethod": "Static"}},
        {"condition": "[parameters('enableBastion')]", "type": "Microsoft.Network/bastionHosts", "apiVersion": "2024-05-01", "name": "[concat(parameters('vmName'), '-bastion')]", "location": "[parameters('location')]", "sku": {"name": "Standard"}, "dependsOn": ["[resourceId('Microsoft.Network/virtualNetworks', variables('vnetName'))]", "[resourceId('Microsoft.Network/publicIPAddresses', concat(parameters('vmName'), '-bastion-ip'))]"], "properties": {"enableTunneling": True, "ipConfigurations": [{"name": "primary", "properties": {"subnet": {"id": "[resourceId('Microsoft.Network/virtualNetworks/subnets', variables('vnetName'), 'AzureBastionSubnet')]"}, "publicIPAddress": {"id": "[resourceId('Microsoft.Network/publicIPAddresses', concat(parameters('vmName'), '-bastion-ip'))]"}}}]}},
    ])
    # A dedicated target RG may be reused only after ownership has been checked.
    for resource in resources:
        resource["tags"] = {"thox-project": "thoxos-ginux", "thox-deployment": "[parameters('vmName')]"}
    return {"$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#", "contentVersion": "1.0.0.0", "parameters": params, "variables": variables, "resources": resources, "outputs": outputs}


if __name__ == "__main__":
    target = Path(__file__).with_name("azuredeploy.json")
    target.write_text(json.dumps(template(), indent=2) + "\n")
    print(target)
