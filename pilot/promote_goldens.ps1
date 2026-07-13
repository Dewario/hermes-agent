#Requires -Version 5.1
<#
.SYNOPSIS
  Promote attorney-approved pilot outputs to skills/legal/*/examples/ (LGD2-008).

  Requires pilot_outputs/approval.json with approved=true for each artifact,
  the full gates_checked set, and sha256 hashes that match the package files.
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$ApprovalPath = Join-Path $RepoRoot 'pilot_outputs\approval.json'

if (-not (Test-Path -LiteralPath $ApprovalPath)) {
    Write-Error "Missing $ApprovalPath -- complete attorney review first."
}

$approval = Get-Content -LiteralPath $ApprovalPath -Raw -Encoding UTF8 | ConvertFrom-Json

function Assert-Prop($obj, $name, $label) {
    if (-not ($obj.PSObject.Properties.Name -contains $name)) {
        Write-Error "approval.json: missing required field '$label'"
    }
}

function Get-FileSha256([string] $Path) {
    $hash = Get-FileHash -LiteralPath $Path -Algorithm SHA256
    return $hash.Hash.ToLowerInvariant()
}

foreach ($f in 'pilot_id', 'reviewer', 'reviewed_at', 'artifacts', 'gates_checked') {
    Assert-Prop $approval $f $f
}
Assert-Prop $approval.artifacts 'intake' 'artifacts.intake'
Assert-Prop $approval.artifacts 'review' 'artifacts.review'
Assert-Prop $approval.artifacts.intake 'sha256' 'artifacts.intake.sha256'
Assert-Prop $approval.artifacts.review 'sha256' 'artifacts.review.sha256'

if ([string]::IsNullOrWhiteSpace([string]$approval.pilot_id) -or
    ([string]$approval.pilot_id) -match 'REPLACE-WITH') {
    Write-Error "approval.json: pilot_id is missing or still the template placeholder"
}
if ([string]::IsNullOrWhiteSpace([string]$approval.reviewer)) {
    Write-Error "approval.json: reviewer is empty"
}

$reviewedRaw = [string]$approval.reviewed_at
if ($reviewedRaw -match 'REPLACE-WITH') {
    Write-Error "approval.json: reviewed_at is still the placeholder -- sign with a real ISO-8601 timestamp"
}
$reviewedAt = [datetime]::MinValue
if (-not [datetime]::TryParse($reviewedRaw, [ref]$reviewedAt)) {
    Write-Error "approval.json: reviewed_at ('$reviewedRaw') is not a valid ISO-8601 date-time"
}

$RequiredGates = @(
    'SOL_issue_flag_not_deadline',
    'FELA_attorney_review_gate',
    'damages_expert_review_gate',
    'production_preflight_step_0',
    'no_prohibited_legal_conclusions',
    'fixture_grounded_facts',
    'validator_strict_pass',
    'check_outputs_pass',
    'casegraph_verify_cites_pass',
    'casegraph_verify_chronology_pass',
    'casegraph_check_isolation_pass'
)
$gates = @($approval.gates_checked)
$missingGates = @($RequiredGates | Where-Object { $gates -notcontains $_ })
if ($missingGates.Count -gt 0) {
    Write-Error ("approval.json: gates_checked missing required gates: " + ($missingGates -join ', '))
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

$intakeHash = Get-FileSha256 $intakeSrc
$reviewHash = Get-FileSha256 $reviewSrc
$signedIntake = ([string]$approval.artifacts.intake.sha256).ToLowerInvariant()
$signedReview = ([string]$approval.artifacts.review.sha256).ToLowerInvariant()
if ($signedIntake -ne $intakeHash) {
    Write-Error "approval.json: artifacts.intake.sha256 mismatch (signed=$signedIntake disk=$intakeHash) -- re-sign after edits"
}
if ($signedReview -ne $reviewHash) {
    Write-Error "approval.json: artifacts.review.sha256 mismatch (signed=$signedReview disk=$reviewHash) -- re-sign after edits"
}

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

    # Casegraph handoff gates on a throwaway synthetic matter (or CASEGRAPH_MATTER_DIR).
    $cgMatter = $env:CASEGRAPH_MATTER_DIR
    if (-not $cgMatter) {
        $cgMatter = Join-Path $env:TEMP 'hermes-promote-casegraph'
    }
    $cgScript = 'skills/legal/casegraph/scripts/casegraph.py'
    $fpStore = Join-Path $cgMatter 'fingerprints.json'
    if (-not (Test-Path -LiteralPath (Join-Path $cgMatter '.casegraph'))) {
        New-Item -ItemType Directory -Force -Path (Join-Path $cgMatter 'production') | Out-Null
        $fixDir = Join-Path $RepoRoot 'skills\legal\discovery-review\fixtures'
        Copy-Item -Path (Join-Path $fixDir '*') -Destination (Join-Path $cgMatter 'production') -Force
        & python $cgScript init $cgMatter --matter-id PROMOTE-SYN --bates-prefix TVRR-PROD --force | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Error 'Gate failed: casegraph init' }
        & python $cgScript build $cgMatter | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Error 'Gate failed: casegraph build' }
        & python $cgScript export-fingerprint $cgMatter --store $fpStore | Out-Null
    }
    # No --strict on chronology/isolation here: WARNs are the DESIGNED
    # attorney-review list (casegraph SPEC) and the attorney signs approval.json
    # having seen them; the throwaway synthetic index has only header-harvested
    # entities so strict mode rejects template prose, not contamination. FAIL
    # classes (fabricated cites, foreign bates, fingerprint hits, vacuous
    # PASSes) still abort promotion.
    #
    # HONESTY (red-team P1-3): gate names '*_pass' mean no FAIL-class findings.
    # They do NOT mean --strict WARN-clean. Attorney signature attests WARN review.
    Write-Host "NOTE: chronology/isolation run WITHOUT --strict (FAIL-only)."
    Write-Host "      Gate '*_pass' = no FAIL class; WARN-class findings are attorney-attested via approval.json."
    & python $cgScript verify-cites $cgMatter $reviewSrc | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error 'Gate failed: casegraph verify-cites (review)' }
    & python $cgScript verify-chronology $cgMatter $reviewSrc | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error 'Gate failed: casegraph verify-chronology (FAIL-only; not --strict)' }
    & python $cgScript check-isolation $cgMatter $reviewSrc --fingerprints $fpStore | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error 'Gate failed: casegraph check-isolation (FAIL-only; not --strict)' }
    & python $cgScript verify-cites $cgMatter $intakeSrc --allow-empty --no-quotes | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error 'Gate failed: casegraph verify-cites (intake)' }
    & python $cgScript check-isolation $cgMatter $intakeSrc --fingerprints $fpStore | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error 'Gate failed: casegraph check-isolation (intake; FAIL-only; not --strict)' }

    # Synthetic-only faithfulness gate: Bates-cited claims vs review fixtures.
    Write-Host 'Running faithfulness eval (synthetic review package vs fixture corpus)...'
    & python pilot/eval_faithfulness.py `
        --package pilot_outputs/review/review_package.md `
        --corpus skills/legal/discovery-review/fixtures | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Error 'Gate failed: eval_faithfulness (review package vs fixtures)' }
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
