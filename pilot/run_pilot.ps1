#Requires -Version 5.1
<#
.SYNOPSIS
  Run legal discovery synthetic pilot with wall-clock guard and auto gates.

.PARAMETER Phase
  intake | review | all | validate-only

.PARAMETER MaxTurns
  Hermes --max-turns cap (iteration budget proxy).

.PARAMETER TimeoutMinutes
  Wall-clock kill for Hermes process.

.PARAMETER DryRun
  Skip Hermes; run validators and check_outputs only.

.EXAMPLE
  .\pilot\run_pilot.ps1 -Phase intake -DryRun
  .\pilot\run_pilot.ps1 -Phase all -MaxTurns 40 -TimeoutMinutes 90
#>
param(
    [ValidateSet('intake', 'review', 'all', 'validate-only')]
    [string] $Phase = 'intake',

    [int] $MaxTurns = 40,

    [int] $TimeoutMinutes = 90,

    [switch] $DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$PilotId = (Get-Date -Format 'yyyy-MM-dd') + '-synthetic-v1'
$LedgerPath = Join-Path $PSScriptRoot 'COMMAND_LEDGER.jsonl'
$BillingPatterns = @(
    'billing', 'quota', 'credit', 'overage', 'insufficient', 'rate limit',
    'payment required', 'exceeded'
)

function Write-Ledger {
    param(
        [string] $Purpose,
        [string] $Command,
        [int] $ExitCode,
        [string] $Notes = ''
    )
    $entry = [ordered]@{
        ts       = (Get-Date).ToUniversalTime().ToString('o')
        pilot_id = $PilotId
        purpose  = $Purpose
        command  = $Command
        exit     = $ExitCode
        notes    = $Notes
    } | ConvertTo-Json -Compress
    Add-Content -Path $LedgerPath -Value $entry -Encoding UTF8
}

function Get-AgentLogPath {
    $hermesHome = $env:HERMES_HOME
    if (-not $hermesHome) {
        $hermesHome = Join-Path $env:USERPROFILE '.hermes'
    }
    return Join-Path $hermesHome 'logs\agent.log'
}

function Test-BillingSignal {
    param([string] $LogPath)
    if (-not (Test-Path -LiteralPath $LogPath)) { return $false }
    try {
        $tail = Get-Content -LiteralPath $LogPath -Tail 80 -ErrorAction SilentlyContinue
        $blob = ($tail -join ' ').ToLowerInvariant()
        foreach ($pat in $BillingPatterns) {
            if ($blob.Contains($pat)) { return $true }
        }
    } catch { }
    return $false
}

function Stop-ProcessTree {
    # FABLE5 M10: the watchdog owns the `python invoke_hermes.py` wrapper, but
    # that wrapper spawns `hermes` as a child; on Windows, killing the parent
    # leaves the child (and its model spend) running orphaned. taskkill /T kills
    # the whole tree. Fall back to a direct kill if taskkill is unavailable.
    param([int] $ProcessId)
    try {
        & taskkill.exe /T /F /PID $ProcessId | Out-Null
    } catch { }
    try {
        $p = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($p -and -not $p.HasExited) { $p.Kill() }
    } catch { }
}

function Invoke-AutoGates {
    param(
        [string] $GatePhase,
        [string] $OutputDir
    )
    $fail = 0

    $packageName = if ($GatePhase -eq 'intake') { 'intake_package.md' } else { 'review_package.md' }
    $packagePath = Join-Path $OutputDir $packageName
    $scanTarget = if (Test-Path -LiteralPath $packagePath) { $packagePath } else { $OutputDir }

    # FABLE5 M9: pipe each gate's native stdout to Out-Host so it is DISPLAYED
    # but does not enter this function's output stream. Previously the validator
    # / check_outputs console lines were emitted into the success stream and
    # concatenated ahead of $fail, so callers compared/aggregated an array of
    # strings instead of the intended integer -- making gate propagation on the
    # live path unreliable. $LASTEXITCODE is still set by the native command.
    $valCmd = "python scripts/validate_legal_discovery_skills.py --dir `"$scanTarget`" --strict"
    Write-Host "`n== Validator ($GatePhase) ==" -ForegroundColor Cyan
    Invoke-Expression $valCmd | Out-Host
    $valExit = $LASTEXITCODE
    Write-Ledger -Purpose "validator-$GatePhase" -Command $valCmd -ExitCode $valExit
    if ($valExit -ne 0) { $fail++ }

    $chkCmd = "python pilot/check_outputs.py --phase $GatePhase --dir `"$OutputDir`""
    Write-Host "`n== check_outputs ($GatePhase) ==" -ForegroundColor Cyan
    Invoke-Expression $chkCmd | Out-Host
    $chkExit = $LASTEXITCODE
    Write-Ledger -Purpose "check_outputs-$GatePhase" -Command $chkCmd -ExitCode $chkExit
    if ($chkExit -ne 0) { $fail++ }

    return [int]$fail
}

function Invoke-HermesPhase {
    param(
        [string] $HermesPhase,
        [string] $SkillName,
        [string] $PromptFile,
        [string] $OutputDir,
        [int] $Turns
    )

    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

    if ($DryRun) {
        Write-Host "DryRun: skipping Hermes for $HermesPhase" -ForegroundColor Yellow
        return 0
    }

    $logPath = Get-AgentLogPath

    Write-Host "`n== Hermes $HermesPhase (max-turns=$Turns, timeout=${TimeoutMinutes}m) ==" -ForegroundColor Cyan

    $invokeScript = Join-Path $PSScriptRoot 'invoke_hermes.py'
    $invokeCmd = @(
        $invokeScript,
        '--prompt-file', $PromptFile,
        '--skill', $SkillName,
        '--max-turns', "$Turns",
        '--output-dir', $OutputDir
    )

    $proc = Start-Process -FilePath 'python' `
        -ArgumentList $invokeCmd `
        -WorkingDirectory $RepoRoot `
        -PassThru -NoNewWindow
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)

    while (-not $proc.HasExited) {
        if ((Get-Date) -gt $deadline) {
            Write-Host "TIMEOUT: killing Hermes after $TimeoutMinutes minutes" -ForegroundColor Red
            Stop-ProcessTree -ProcessId $proc.Id
            $statusPath = Join-Path $RepoRoot 'pilot_outputs\STATUS_NEEDS_OWNER.md'
            @(
                '# Pilot stopped — runtime timeout',
                "",
                "Phase: $HermesPhase",
                "TimeoutMinutes: $TimeoutMinutes",
                "Time: $((Get-Date).ToUniversalTime().ToString('o'))"
            ) | Set-Content -Path $statusPath -Encoding UTF8
            Write-Ledger -Purpose "hermes-$HermesPhase" -Command ($invokeCmd -join ' ') -ExitCode 124 -Notes 'timeout'
            return 124
        }
        if (Test-BillingSignal -LogPath $logPath) {
            Write-Host "BILLING SIGNAL: killing Hermes" -ForegroundColor Red
            Stop-ProcessTree -ProcessId $proc.Id
            $statusPath = Join-Path $RepoRoot 'pilot_outputs\STATUS_NEEDS_OWNER.md'
            @(
                '# Pilot stopped — billing signal',
                "",
                "Phase: $HermesPhase",
                "Check: $logPath",
                "Time: $((Get-Date).ToUniversalTime().ToString('o'))"
            ) | Set-Content -Path $statusPath -Encoding UTF8
            Write-Ledger -Purpose "hermes-$HermesPhase" -Command ($invokeCmd -join ' ') -ExitCode 125 -Notes 'billing'
            return 125
        }
        Start-Sleep -Seconds 5
    }

    $exit = $proc.ExitCode
    if ($null -eq $exit) { $exit = 1 }

    Write-Ledger -Purpose "hermes-$HermesPhase" -Command ($invokeCmd -join ' ') -ExitCode $exit
    Write-Host "Hermes exit: $exit (transcript: $(Join-Path $OutputDir 'hermes_transcript.txt'))"
    return $exit
}

# --- main ---

New-Item -ItemType Directory -Force -Path (Join-Path $RepoRoot 'pilot_outputs') | Out-Null
Write-Ledger -Purpose 'pilot-start' -Command "run_pilot.ps1 -Phase $Phase" -ExitCode 0 -Notes $(if ($DryRun) { 'dry-run' } else { 'live' })

$overallFail = 0

function Run-Intake {
    $out = Join-Path $RepoRoot 'pilot_outputs\intake'
    $hExit = Invoke-HermesPhase -HermesPhase 'intake' -SkillName 'legal-discovery-intake' `
        -PromptFile (Join-Path $PSScriptRoot 'PILOT_PROMPT_INTAKE.md') -OutputDir $out -Turns $MaxTurns
    if ($DryRun) { return 0 }
    if ($hExit -ne 0) { return $hExit }
    $gFail = Invoke-AutoGates -GatePhase 'intake' -OutputDir $out
    if ($gFail -gt 0) { return 1 }
    return 0
}

function Run-Review {
    $out = Join-Path $RepoRoot 'pilot_outputs\review'
    $reviewTurns = [Math]::Max($MaxTurns, 50)
    $hExit = Invoke-HermesPhase -HermesPhase 'review' -SkillName 'legal-discovery-review' `
        -PromptFile (Join-Path $PSScriptRoot 'PILOT_PROMPT_REVIEW.md') -OutputDir $out -Turns $reviewTurns
    if ($DryRun) { return 0 }
    if ($hExit -ne 0) { return $hExit }
    $gFail = Invoke-AutoGates -GatePhase 'review' -OutputDir $out
    if ($gFail -gt 0) { return 1 }
    return 0
}

switch ($Phase) {
    'validate-only' {
        $overallFail += Invoke-AutoGates -GatePhase 'intake' -OutputDir (Join-Path $RepoRoot 'pilot_outputs\intake')
        $overallFail += Invoke-AutoGates -GatePhase 'review' -OutputDir (Join-Path $RepoRoot 'pilot_outputs\review')
    }
    'intake' { if (Run-Intake) { $overallFail++ } }
    'review' { if (Run-Review) { $overallFail++ } }
    'all' {
        if (Run-Intake) { $overallFail++ }
        if (Run-Review) { $overallFail++ }
    }
}

# Attorney handoff doc
$pendingPath = Join-Path $RepoRoot 'pilot_outputs\ATTORNEY_REVIEW_PENDING.md'
@(
    '# Attorney review required',
    '',
    "Pilot ID: **$PilotId**",
    '',
    'Machine gates completed (see COMMAND_LEDGER.jsonl). **Attorney sign-off required** before goldens.',
    '',
    '## Review locations',
    '',
    '- `pilot_outputs/intake/intake_package.md` — SOL Issue Flag, FELA gate, discovery plan',
    '- `pilot_outputs/review/review_package.md` — issue matrix, chronology, deposition seeds, damages gate',
    '',
    '## Sign-off steps',
    '',
    '1. Read both packages; edit in place if needed.',
    '2. Copy `pilot/approval.template.json` -> `pilot_outputs/approval.json`.',
    '3. Set `"approved": true` for each artifact and fill `gates_checked`.',
    '4. Run: `.\pilot\promote_goldens.ps1`',
    '',
    '**Do not use on real client matters until approval.json is complete.**'
) | Set-Content -Path $pendingPath -Encoding UTF8

Write-Ledger -Purpose 'pilot-end' -Command "run_pilot.ps1 -Phase $Phase" -ExitCode $(if ($overallFail) { 1 } else { 0 })

if ($overallFail -gt 0) {
    Write-Host "`nPILOT FAIL: $overallFail gate(s) failed. Fix outputs or re-run Hermes." -ForegroundColor Red
    exit 1
}

if ($DryRun) {
    Write-Host "`nDryRun complete (no Hermes invocation)." -ForegroundColor Yellow
    exit 0
}

Write-Host "`nPILOT RUN complete. Next: attorney review, pilot_outputs/approval.json, promote_goldens.ps1" -ForegroundColor Green
exit 0
