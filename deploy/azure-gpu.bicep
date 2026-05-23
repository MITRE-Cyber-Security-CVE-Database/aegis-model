// AEGIS Azure GPU Training Infrastructure
// Deploys an NC-series VM for model fine-tuning
// Cost: ~$3/hour for NC6s_v3 (Tesla V100)
// With $100 Azure student credit = ~33 hours training time

@description('VM size for training. NC6s_v3 = V100, NC24s_v3 = 4x V100')
param vmSize string = 'Standard_NC6s_v3'

@description('Admin username for VM')
param adminUsername string = 'cyberviser'

@description('SSH public key for VM access')
@secure()
param adminSshKey string

@description('Azure region. Use East US or West US 2 for GPU availability')
param location string = 'eastus'

@description('Resource group name')
param rgName string = 'aegis-training'

@description('Auto-shutdown time (24h format) to save credits')
param autoShutdownTime string = '2200'

// Resource Group
resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: rgName
  location: location
}

// Virtual Network
resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: 'aegis-vnet'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: ['10.0.0.0/16']
    }
    subnets: [
      {
        name: 'gpu-subnet'
        properties: {
          addressPrefix: '10.0.1.0/24'
        }
      }
    ]
  }
}

// Network Security Group
resource nsg 'Microsoft.Network/networkSecurityGroups@2023-09-01' = {
  name: 'aegis-nsg'
  location: location
  properties: {
    securityRules: [
      {
        name: 'SSH'
        properties: {
          priority: 1000
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '22'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'Jupyter'
        properties: {
          priority: 1001
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '8888'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'TensorBoard'
        properties: {
          priority: 1002
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '6006'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

// Public IP
resource publicIP 'Microsoft.Network/publicIPAddresses@2023-09-01' = {
  name: 'aegis-gpu-ip'
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}

// Network Interface
resource nic 'Microsoft.Network/networkInterfaces@2023-09-01' = {
  name: 'aegis-gpu-nic'
  location: location
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          subnet: {
            id: vnet.properties.subnets[0].id
          }
          publicIPAddress: {
            id: publicIP.id
          }
          privateIPAllocationMethod: 'Dynamic'
        }
      }
    ]
    networkSecurityGroup: {
      id: nsg.id
    }
  }
}

// GPU VM
resource gpuVM 'Microsoft.Compute/virtualMachines@2023-09-01' = {
  name: 'aegis-gpu-trainer'
  location: location
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    osProfile: {
      computerName: 'aegis-gpu'
      adminUsername: adminUsername
      linuxConfiguration: {
        disablePasswordAuthentication: true
        ssh: {
          publicKeys: [
            {
              path: '/home/${adminUsername}/.ssh/authorized_keys'
              keyData: adminSshKey
            }
          ]
        }
      }
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: '0001-com-ubuntu-server-jammy'
        sku: '22_04-lts-gen2'
        version: 'latest'
      }
      osDisk: {
        name: 'aegis-osdisk'
        caching: 'ReadWrite'
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'Premium_LRS'
        }
        diskSizeGB: 256
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic.id
        }
      ]
    }
  }
}

// Custom Script Extension - Install ML Stack
resource vmExtension 'Microsoft.Compute/virtualMachines/extensions@2023-09-01' = {
  parent: gpuVM
  name: 'install-ml-stack'
  location: location
  properties: {
    publisher: 'Microsoft.Azure.Extensions'
    type: 'CustomScript'
    typeHandlerVersion: '2.1'
    autoUpgradeMinorVersion: true
    settings: {
      commandToExecute: '''
#!/bin/bash
set -e

# Update system
apt-get update && apt-get upgrade -y

# Install NVIDIA drivers and CUDA
apt-get install -y linux-headers-$(uname -r)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID | sed -e 's/\.//g')
wget https://developer.download.nvidia.com/compute/cuda/repos/$distribution/x86_64/cuda-keyring_1.0-1_all.deb
dpkg -i cuda-keyring_1.0-1_all.deb
apt-get update
apt-get install -y cuda-drivers cuda-toolkit-12-2

# Install Docker
apt-get install -y docker.io docker-compose
usermod -aG docker cyberviser

# Install Python + ML libraries
apt-get install -y python3-pip python3-venv git
pip3 install --upgrade pip
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip3 install transformers peft accelerate bitsandbytes datasets wandb

# Install Ollama for local inference
curl -fsSL https://ollama.com/install.sh | sh

# Clone AEGIS repo
cd /home/cyberviser
git clone https://github.com/gulfofamerica/aegis-model.git || true
chown -R cyberviser:cyberviser /home/cyberviser

# Setup auto-shutdown to save credits
echo "0 ${autoShutdownTime} * * * root /sbin/shutdown -h now" > /etc/cron.d/auto-shutdown

# Log completion
echo "AEGIS GPU setup complete at $(date)" > /home/cyberviser/setup.log
'''
    }
  }
}

// Budget alert (critical for student credits!)
resource budget 'Microsoft.Consumption/budgets@2023-05-01' = {
  name: 'aegis-student-budget'
  properties: {
    category: 'Cost'
    amount: 100
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: '${utcNow('yyyy-MM-dd')}'
      endDate: '${dateTimeAdd(utcNow(), 'P3M')}'
    }
    notifications: {
      Actual_GreaterThan80: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        contactEmails: ['johnny.watters@email.phoenix.edu']
      }
      Actual_GreaterThan100: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        contactEmails: ['johnny.watters@email.phoenix.edu']
      }
    }
  }
}

// Outputs
output sshCommand string = 'ssh ${adminUsername}@${publicIP.properties.ipAddress}'
output jupyterUrl string = 'http://${publicIP.properties.ipAddress}:8888'
output tensorboardUrl string = 'http://${publicIP.properties.ipAddress}:6006'
output costWarning string = 'WARNING: NC6s_v3 costs ~$3/hour. $100 credit = ~33 hours. Auto-shutdown at ${autoShutdownTime}:00 UTC.'
