#Requires -Version 5.1
<#
.SYNOPSIS
  Promote attorney-approved pilot outputs to skills/legal/*/examples/ (LGD2-008).

  Requires pilot_outputs/approval.json with approved=true for each artifact.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ApprovalPath = Join-Path $RepoRoot 'pilot_outputs\approval.json'

if (-not (Test-Path -LiteralPath $ApprovalPath)) {
    Write-Error "Missing $ApprovalPath -- complete attorney review first."
}

$approval = Get-Content -LiteralPath $ApprovalPath -Raw -Encoding UTF8 | ConvertFrom-Json

# --- FABLE5 H8: validate the approval record before trusting two booleans ---
# PowerShell 5.1 has no `Test-Json -Schema`, so enforce the schema's required
# fields and key semantics explicitly. Any failure aborts before a copy.

function Assert-Prop($obj, $name, $label) {
    if (-not ($obj.PSObject.Properties.Name -contains $name)) {
        Write-Error "approval.json: missing required field '$label'"
    }
}

foreach ($f in 'pilot_id', 'reviewer', 'reviewed_at', 'artifacts', 'gates_checked') {
    Assert-Prop $approval $f $f
}
Assert-Prop $approval.artifacts 'intake' 'artifacts.intake'
Assert-Prop $approval.artifacts 'review' 'artifacts.review'

# pilot_id / reviewer must be real, not the template placeholders.
if ([string]::IsNullOrWhiteSpace([string]$approval.pilot_id) -or
    ([string]$approval.pilot_id) -match 'REPLACE-WITH') {
    Write-Error "approval.json: pilot_id is missing or still the template placeholder"
}
if ([string]::IsNullOrWhiteSpace([string]$approval.reviewer)) {
    Write-Error "approval.json: reviewer is empty"
}

# reviewed_at must parse as a real timestamp and not be the placeholder.
$reviewedRaw = [string]$approval.reviewed_at
if ($reviewedRaw -match 'REPLACE-WITH') {
    Write-Error "approval.json: reviewed_at is still the placeholder -- sign with a real ISO-8601 timestamp"
}
$reviewedAt = [datetime]::MinValue
if (-not [datetime]::TryParse($reviewedRaw, [ref]$reviewedAt)) {
    Write-Error "approval.json: reviewed_at ('$reviewedRaw') is not a valid ISO-8601 date-time"
}

# gates_checked must be a non-empty array (the schema's minItems:1).
$gates = @($approval.gates_checked)
if ($gates.Count -lt 1) {
    Write-Error "approval.json: gates_checked is empty -- record the gates you verified"
}

if (-not $approval.artifacts.intake.approved) {
    Write-Error 'approval.json: intake not approved'
}
if (-not $approval.artifacts.review.approved) {
    Write-Error 'approval.json: review not approved'
}

$pilotId = $approval.pilot_id
$intakeSrc = Join-Path $RepoRoot 'pilot_outputs\intake\intake_package.md'
$reviewSrc = Join-Path $RepoRoot 'pilot_outputs\review\review_package.md'

if (-not (Test-Path -LiteralPath $intakeSrc)) {
    Write-Error "Missing $intakeSrc"
}
if (-not (Test-Path -LiteralPath $reviewSrc)) {
    Write-Error "Missing $reviewSrc"
}

# --- FABLE5 H8: re-run BOTH machine gates on the source files before copying.
# Promotion must never outrun the gates; a stale/edited package that no longer
# passes must not reach examples/. ---
Push-Location $RepoRoot
try {
    & python scripts/validate_legal_discovery_skills.py --dir pilot_outputs/intake/intake_package.md --strict | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error 'Gate failed: validator (strict) on intake package' }
    & python scripts/validate_legal_discovery_skills.py --dir pilot_outputs/review/review_package.md --strict | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error 'Gate failed: validator (strict) on review package' }
    & python pilot/check_outputs.py --phase intake --dir pilot_outputs/intake | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error 'Gate failed: check_outputs intake' }
    & python pilot/check_outputs.py --phase review --dir pilot_outputs/review | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error 'Gate failed: check_outputs review' }
}
finally {
    Pop-Location
}

$intakeDest = Join-Path $RepoRoot "skills\legal\discovery-intake\examples\$pilotId"
$reviewDest = Join-Path $RepoRoot "skills\legal\discovery-review\examples\$pilotId"

New-Item -ItemType Directory -Force -Path $intakeDest, $reviewDest | Out-Null

Copy-Item -LiteralPath $intakeSrc -Destination (Join-Path $intakeDest 'intake_package.md') -Force
Copy-Item -LiteralPath $reviewSrc -Destination (Join-Path $reviewDest 'review_package.md') -Force
Copy-Item -LiteralPath $ApprovalPath -Destination (Join-Path $intakeDest 'approval.json') -Force
Copy-Item -LiteralPath $ApprovalPath -Destination (Join-Path $reviewDest 'approval.json') -Force

Write-Host "Promoted goldens to:"
Write-Host "  $intakeDest"
Write-Host "  $reviewDest"
Write-Host ""
Write-Host "Run before commit:"
Write-Host "  python scripts/validate_legal_discovery_skills.py --strict"
Write-Host "  python pilot/check_outputs.py --phase intake --dir skills/legal/discovery-intake/examples/$pilotId"
Write-Host "  python pilot/check_outputs.py --phase review --dir skills/legal/discovery-review/examples/$pilotId"
