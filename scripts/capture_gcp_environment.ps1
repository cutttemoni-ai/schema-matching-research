$ErrorActionPreference='Stop'
Set-Location -LiteralPath (Join-Path $PSScriptRoot '..')
$evidence = Join-Path (Get-Location) 'research-artifacts/gcp-v1/environment'
New-Item -ItemType Directory -Path $evidence -Force | Out-Null
function Save-Query([string]$Name,[scriptblock]$Command) {
    $value = & $Command
    if ($LASTEXITCODE -ne 0) { throw "Read-only capture failed: $Name" }
    $value | Set-Content -LiteralPath (Join-Path $evidence $Name) -Encoding UTF8
}
Save-Query 'azure-vm.json' { az vm show --subscription f01f27b9-f573-4f0a-bfbc-4c1f883bcc5e --resource-group schema-match-demo-rg --name schema-match-llm-vm --show-details --query '{id:id,name:name,resourceGroup:resourceGroup,powerState:powerState,size:hardwareProfile.vmSize,location:location,osDisk:storageProfile.osDisk.managedDisk.id}' -o json }
Save-Query 'azure-retained.json' { az resource list --subscription f01f27b9-f573-4f0a-bfbc-4c1f883bcc5e --resource-group schema-match-demo-rg --query '[].{name:name,type:type,location:location}' -o json }
Save-Query 'azure-shutdown.json' { az resource show --subscription f01f27b9-f573-4f0a-bfbc-4c1f883bcc5e --resource-group schema-match-demo-rg --resource-type Microsoft.DevTestLab/schedules --name shutdown-computevm-schema-match-llm-vm --api-version 2018-09-15 --query '{status:properties.status,time:properties.dailyRecurrence.time,timeZone:properties.timeZoneId,target:properties.targetResourceId}' -o json }
Save-Query 'gcloud-research.json' { gcloud --configuration=schema-research-gemini config list --format='json(core.account,core.project)' }
Save-Query 'gcloud-default-unchanged.json' { gcloud --configuration=default config list --format='json(core.account,core.project)' }
Save-Query 'gcloud-version.json' { gcloud version --format=json }
Save-Query 'billing-account.json' { gcloud --configuration=schema-research-gemini billing accounts describe 011896-2738F2-CBDC0D --format='json(name,open,currencyCode)' }
Save-Query 'billing-project.json' { gcloud --configuration=schema-research-gemini billing projects describe schema-match-gemini-261103 --format=json }
Save-Query 'enabled-apis.json' { gcloud --configuration=schema-research-gemini services list --enabled --project=schema-match-gemini-261103 --format='json(config.name)' }
Write-Output 'Read-only environment evidence saved. Credentials/tokens were not captured.'
