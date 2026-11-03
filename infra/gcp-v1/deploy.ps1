param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $projectRoot
$gcpSettings = Get-Content -LiteralPath 'config/gcp_research_v1.json' -Raw | ConvertFrom-Json
$gcpProject = $gcpSettings.project
$jobRegion = 'asia-northeast3'
$runtimeAccount = "schema-research-worker@$gcpProject.iam.gserviceaccount.com"
$repositoryImage = "$jobRegion-docker.pkg.dev/$gcpProject/schema-research/worker:v1"
function Invoke-Gcloud([string[]]$Arguments) {
    $allArguments = @('--configuration=schema-research-gemini') + $Arguments
    if (-not $Apply) { Write-Output ('gcloud ' + ($allArguments -join ' ')); return }
    & gcloud @allArguments
    if ($LASTEXITCODE -ne 0) { throw 'Deployment stopped. Existing resources are preserved; inspect the failed command.' }
}
if ($Apply -and -not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Local Docker is required. No resources changed.' }
# Docker's gcloud credential helper inherits this process-only configuration;
# it must not fall back to the user's unrelated default account.
if ($Apply) { $env:CLOUDSDK_ACTIVE_CONFIG_NAME = 'schema-research-gemini' }
Invoke-Gcloud @('services','enable','aiplatform.googleapis.com','run.googleapis.com','storage.googleapis.com','artifactregistry.googleapis.com','iam.googleapis.com',"--project=$gcpProject",'--quiet')
foreach ($suffix in @('raw','profiles','results')) {
    Invoke-Gcloud @('storage','buckets','create',"gs://$gcpProject-$suffix", "--project=$gcpProject", "--location=$jobRegion",'--uniform-bucket-level-access','--public-access-prevention')
}
Invoke-Gcloud @('iam','service-accounts','create','schema-research-worker',"--project=$gcpProject",'--display-name=Private schema research worker')
Invoke-Gcloud @('iam','roles','create','schemaMatcherPredictor',"--project=$gcpProject",'--file=infra/gcp-v1/predictor-role.yaml')
Invoke-Gcloud @('projects','add-iam-policy-binding',$gcpProject,"--member=serviceAccount:$runtimeAccount","--role=projects/$gcpProject/roles/schemaMatcherPredictor",'--condition=None','--quiet')
foreach ($suffix in @('raw','profiles','results')) {
    Invoke-Gcloud @('storage','buckets','add-iam-policy-binding',"gs://$gcpProject-$suffix","--member=serviceAccount:$runtimeAccount",'--role=roles/storage.objectViewer')
    if ($suffix -ne 'raw') { Invoke-Gcloud @('storage','buckets','add-iam-policy-binding',"gs://$gcpProject-$suffix","--member=serviceAccount:$runtimeAccount",'--role=roles/storage.objectCreator') }
}
Invoke-Gcloud @('artifacts','repositories','create','schema-research',"--project=$gcpProject","--location=$jobRegion",'--repository-format=docker')
Invoke-Gcloud @('auth','configure-docker',"$jobRegion-docker.pkg.dev",'--quiet')
if ($Apply) {
    & docker build -f infra/gcp-v1/Dockerfile -t $repositoryImage .
    if ($LASTEXITCODE -ne 0) { throw 'Docker build failed; no job was deployed.' }
    & docker push $repositoryImage
    if ($LASTEXITCODE -ne 0) { throw 'Docker push failed; no job was deployed.' }
} else {
    Write-Output "docker build -f infra/gcp-v1/Dockerfile -t $repositoryImage ."
    Write-Output "docker push $repositoryImage"
}
Invoke-Gcloud @('storage','cp','research-artifacts/gcp-v1/development-plan.json',"gs://$gcpProject-raw/plans/development.json")
Invoke-Gcloud @('run','jobs','deploy','schema-research-dry-run',"--project=$gcpProject","--region=$jobRegion", "--image=$repositoryImage", "--service-account=$runtimeAccount",'--tasks=1','--parallelism=1','--max-retries=0','--task-timeout=3600s','--cpu=1','--memory=2Gi',
    "--set-env-vars=GOOGLE_CLOUD_PROJECT=$gcpProject,GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=true", "--args=--mode,dry-run,--plan,gs://$gcpProject-raw/plans/development.json,--output,gs://$gcpProject-results/dry-run")
Write-Output 'Job creation does not execute it. No public web service or model VM is created. Default mode is dry-run.'
