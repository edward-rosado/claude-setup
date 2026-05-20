<#
.SYNOPSIS
    Claude Setup - Windows-native bootstrap (PowerShell port of setup.sh).

.DESCRIPTION
    Symlinks rules, skills, and instincts into ~/.claude/ and merges
    settings.json. This is the Windows path; setup.sh is the macOS/Linux
    path. The two share settings.json and the same on-disk layout.

    Why a separate PowerShell installer: a bash-only installer forces a
    Git Bash dependency just to bootstrap. PowerShell 5.1 ships on every
    Windows 11 box and has native symlink/junction support.

    Symlink strategy on Windows:
      * Skills are DIRECTORIES - linked as directory symlinks (Developer
        Mode on) or junctions (Developer Mode off). Junctions need no
        elevation and work for directories.
      * Rules and instincts are individual FILES - junctions cannot link
        files. With Developer Mode on they are file symlinks; with it off
        they are COPIED (and the manifest records them as copies). A copy
        is a snapshot - re-run setup.ps1 -Install after editing a rule.

.PARAMETER Install
    Symlink rules + skills + instincts into ~/.claude/, merge settings.

.PARAMETER Uninstall
    Remove what was installed (manifest-driven), preserve backups.

.PARAMETER Check
    Report installation status without changing anything.

.PARAMETER GenerateMobile
    Generate mobile/project-knowledge.md for claude.ai mobile.

.PARAMETER Sync
    Pull new learned instincts from ~/.claude/ back into the repo.

.PARAMETER Test
    Run the test suite (delegates to tests/test_setup.sh via bash if
    available; otherwise reports that bash is required for the tests).

.PARAMETER ClaudeHome
    Override the ~/.claude/ location (for testing).

.PARAMETER DryRun
    Show what would happen without making changes.

.PARAMETER VerboseOutput
    Show extra detail.

.EXAMPLE
    .\setup.ps1 -Install

.EXAMPLE
    .\setup.ps1 -Check
#>
[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Check,
    [switch]$GenerateMobile,
    [switch]$Sync,
    [switch]$Test,
    [string]$ClaudeHome,
    [switch]$DryRun,
    [switch]$VerboseOutput
)

$ErrorActionPreference = 'Stop'

# --- Paths ----------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ClaudeHome) {
    $ClaudeHome = Join-Path $HOME '.claude'
}
$BackupDir = Join-Path $ClaudeHome ("backups/claude-setup-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$ManifestFile = Join-Path $ClaudeHome '.claude-setup-manifest'

# --- Logging --------------------------------------------------------------
function Write-Log    { param($m) Write-Host "[INFO]  $m"  -ForegroundColor Blue }
function Write-Ok     { param($m) Write-Host "[OK]    $m"  -ForegroundColor Green }
function Write-Warn   { param($m) Write-Host "[WARN]  $m"  -ForegroundColor Yellow }
function Write-Err    { param($m) Write-Host "[ERROR] $m"  -ForegroundColor Red }
function Write-Dry    { param($m) Write-Host "[DRY]   $m"  -ForegroundColor Yellow }

# --- Developer Mode detection ---------------------------------------------
# Developer Mode lets a non-admin process create symlinks. Without it we
# fall back to junctions (directories) and copies (files).
function Test-DeveloperMode {
    try {
        $key = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock'
        $val = (Get-ItemProperty -Path $key -Name 'AllowDevelopmentWithoutDevLicense' -ErrorAction Stop).AllowDevelopmentWithoutDevLicense
        return ($val -eq 1)
    } catch {
        return $false
    }
}

$script:DevMode = Test-DeveloperMode

# --- Link / copy a single source into a target ---------------------------
# Returns the kind actually used: "symlink", "junction", or "copy".
function Install-Link {
    param(
        [Parameter(Mandatory)] [string]$Source,
        [Parameter(Mandatory)] [string]$Target,
        [Parameter(Mandatory)] [bool]$IsDirectory
    )

    # Already linked to the right place?
    if (Test-Path $Target) {
        $item = Get-Item $Target -Force
        $existingTarget = $item.Target
        if ($existingTarget) {
            $resolvedExisting = (Resolve-Path -LiteralPath (Join-Path (Split-Path $Target) $existingTarget) -ErrorAction SilentlyContinue)
            if ($resolvedExisting -and ((Resolve-Path $Source).Path -eq $resolvedExisting.Path)) {
                if ($VerboseOutput) { Write-Ok "Already linked: $Target" }
                return 'unchanged'
            }
        }
    }

    if ($DryRun) {
        Write-Dry "Would link: $Target -> $Source"
        return 'dry'
    }

    # Back up an existing real file/dir before replacing it.
    if (Test-Path $Target) {
        New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
        $backupName = Split-Path $Target -Leaf
        $backupPath = Join-Path $BackupDir $backupName
        if (-not (Test-Path $backupPath)) {
            Copy-Item -Recurse -Force $Target $backupPath
            Write-Warn "Backed up: $Target -> $backupPath"
        }
        Remove-Item -Recurse -Force $Target
    }

    $parent = Split-Path $Target -Parent
    New-Item -ItemType Directory -Force -Path $parent | Out-Null

    $kind = 'copy'
    if ($IsDirectory) {
        if ($script:DevMode) {
            New-Item -ItemType SymbolicLink -Path $Target -Target $Source | Out-Null
            $kind = 'symlink'
        } else {
            # Junctions need no elevation and work for directories.
            New-Item -ItemType Junction -Path $Target -Target $Source | Out-Null
            $kind = 'junction'
        }
    } else {
        if ($script:DevMode) {
            New-Item -ItemType SymbolicLink -Path $Target -Target $Source | Out-Null
            $kind = 'symlink'
        } else {
            # Junctions cannot link files. Copy instead - a snapshot.
            Copy-Item -Force $Source $Target
            $kind = 'copy'
        }
    }

    Write-Ok "Linked ($kind): $Target -> $Source"
    Add-Content -LiteralPath $ManifestFile -Value "$Target|$Source|$kind"
    return $kind
}

# --- Install --------------------------------------------------------------
function Invoke-Install {
    Write-Log "Installing claude-setup into $ClaudeHome"
    if (-not $script:DevMode) {
        Write-Warn "Developer Mode is OFF. Skill directories -> junctions; rule/instinct FILES -> copies (snapshots; re-run -Install after editing one). Enable Developer Mode (Settings > Privacy & Security > For Developers) for live file symlinks."
    }

    New-Item -ItemType Directory -Force -Path (Join-Path $ClaudeHome 'rules') | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $ClaudeHome 'skills') | Out-Null

    if (-not $DryRun) { Set-Content -LiteralPath $ManifestFile -Value '' }

    # Rules - flatten the grouped structure; each is an individual file.
    Write-Log "Linking rules..."
    $copyCount = 0
    Get-ChildItem -Directory (Join-Path $ScriptDir 'rules') -ErrorAction SilentlyContinue | ForEach-Object {
        Get-ChildItem -File -Filter '*.md' $_.FullName | ForEach-Object {
            $kind = Install-Link -Source $_.FullName -Target (Join-Path $ClaudeHome ("rules/" + $_.Name)) -IsDirectory $false
            if ($kind -eq 'copy') { $copyCount++ }
        }
    }

    # Skills - flatten the grouped structure; each is a directory.
    Write-Log "Linking skills..."
    Get-ChildItem -Directory (Join-Path $ScriptDir 'skills') -ErrorAction SilentlyContinue | ForEach-Object {
        Get-ChildItem -Directory $_.FullName | ForEach-Object {
            Install-Link -Source $_.FullName -Target (Join-Path $ClaudeHome ("skills/" + $_.Name)) -IsDirectory $true | Out-Null
        }
    }

    # Learned instincts - individual files, into homunculus/instincts/.
    $instinctSrc = Join-Path $ScriptDir 'learned/instincts'
    if (Test-Path $instinctSrc) {
        Write-Log "Linking learned instincts..."
        Get-ChildItem -File $instinctSrc | ForEach-Object {
            $kind = Install-Link -Source $_.FullName -Target (Join-Path $ClaudeHome ("homunculus/instincts/" + $_.Name)) -IsDirectory $false
            if ($kind -eq 'copy') { $copyCount++ }
        }
    }

    Write-Log "Merging settings..."
    Merge-Settings

    Write-Log "Installing plugins..."
    Install-Plugins

    Write-Host ''
    if ($copyCount -gt 0) {
        Write-Warn "$copyCount file(s) were COPIED, not symlinked (Developer Mode off). Re-run '.\setup.ps1 -Install' after editing a rule or instinct."
    }
    Write-Ok "Installation complete!"
}

# --- Settings merge -------------------------------------------------------
# Reuses the same Python merge logic as setup.sh - no jq dependency.
function Merge-Settings {
    $manifest = Join-Path $ScriptDir 'settings.json'
    $target = Join-Path $ClaudeHome 'settings.json'

    if (-not (Test-Path $manifest)) {
        Write-Warn "No settings.json manifest found, skipping"
        return
    }
    if ($DryRun) {
        Write-Dry "Would merge settings from $manifest into $target"
        return
    }
    if (-not (Test-Path $target)) {
        Set-Content -LiteralPath $target -Value '{}'
    }

    $py = $null
    foreach ($candidate in @('python3', 'python')) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) { $py = $candidate; break }
    }
    if (-not $py) {
        Write-Err "Python not found. Cannot merge settings. Install Python 3 and retry."
        return
    }

    $mergeScript = @'
import json, sys

manifest_path, target_path = sys.argv[1], sys.argv[2]
with open(manifest_path) as f:
    manifest = json.load(f)
with open(target_path) as f:
    existing = json.load(f)

if "env" in manifest:
    existing.setdefault("env", {})
    existing["env"].update(manifest["env"])

if "plugins" in manifest:
    existing.setdefault("enabledPlugins", {})
    for plugin in manifest["plugins"]:
        existing["enabledPlugins"][plugin] = True

if "marketplaces" in manifest:
    existing.setdefault("extraKnownMarketplaces", {})
    for name, config in manifest["marketplaces"].items():
        existing["extraKnownMarketplaces"][name] = {"source": config}

with open(target_path, "w") as f:
    json.dump(existing, f, indent=2)
'@
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("claude-setup-merge-" + [System.Guid]::NewGuid().ToString() + ".py")
    Set-Content -LiteralPath $tmp -Value $mergeScript -Encoding utf8
    try {
        & $py $tmp $manifest $target
        if ($LASTEXITCODE -ne 0) { Write-Err "Settings merge failed (python exit $LASTEXITCODE)."; return }
    } finally {
        Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue
    }
    Write-Ok "Settings merged"
}

# --- Plugin install -------------------------------------------------------
function Install-Plugins {
    $manifest = Join-Path $ScriptDir 'settings.json'
    if (-not (Test-Path $manifest)) { return }
    if ($DryRun) { Write-Dry "Would install plugins from manifest"; return }

    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
        Write-Warn "Claude CLI not found. Plugins are declared in settings.json (merged above) and will be enabled when Claude Code next reads its settings."
        return
    }
    Write-Log "Plugins are declared in settings.json (merged). Claude Code enables them on next start."
}

# --- Uninstall ------------------------------------------------------------
function Invoke-Uninstall {
    Write-Log "Uninstalling claude-setup from $ClaudeHome"
    if (-not (Test-Path $ManifestFile)) {
        Write-Warn "No manifest found - nothing to uninstall (or it was never installed)."
        return
    }
    Get-Content -LiteralPath $ManifestFile | ForEach-Object {
        if (-not $_) { return }
        $parts = $_ -split '\|'
        $target = $parts[0]
        if ($target -and (Test-Path $target)) {
            if ($DryRun) {
                Write-Dry "Would remove: $target"
            } else {
                Remove-Item -Recurse -Force $target
                Write-Ok "Removed: $target"
            }
        }
    }
    if (-not $DryRun) { Remove-Item -LiteralPath $ManifestFile -ErrorAction SilentlyContinue }
    Write-Host ''
    Write-Ok "Uninstall complete. Backups remain in $ClaudeHome/backups/"
}

# --- Check ----------------------------------------------------------------
function Invoke-Check {
    Write-Log "Checking claude-setup installation status..."
    $allGood = $true

    Get-ChildItem -Directory (Join-Path $ScriptDir 'rules') -ErrorAction SilentlyContinue | ForEach-Object {
        Get-ChildItem -File -Filter '*.md' $_.FullName | ForEach-Object {
            $target = Join-Path $ClaudeHome ("rules/" + $_.Name)
            if ((Test-Path $target) -and (Get-Item $target).Length -ge 0) {
                Write-Ok "Rule: $($_.Name)"
            } else {
                Write-Warn "Missing: $($_.Name)"; $script:allGood = $false
            }
        }
    }
    Get-ChildItem -Directory (Join-Path $ScriptDir 'skills') -ErrorAction SilentlyContinue | ForEach-Object {
        Get-ChildItem -Directory $_.FullName | ForEach-Object {
            $target = Join-Path $ClaudeHome ("skills/" + $_.Name)
            if (Test-Path $target) {
                Write-Ok "Skill: $($_.Name)"
            } else {
                Write-Warn "Missing: $($_.Name)"; $script:allGood = $false
            }
        }
    }
    if (Test-Path $ManifestFile) { Write-Ok "Manifest: present" }
    else { Write-Warn "Manifest: missing (run -Install to create)" }

    if ($allGood) {
        Write-Ok "All components installed correctly"
        return 0
    }
    Write-Warn "Some components are missing. Run: .\setup.ps1 -Install"
    return 1
}

# --- Generate mobile ------------------------------------------------------
function Invoke-GenerateMobile {
    $output = Join-Path $ScriptDir 'mobile/project-knowledge.md'
    Write-Log "Generating mobile project knowledge..."
    if ($DryRun) { Write-Dry "Would generate: $output"; return }

    New-Item -ItemType Directory -Force -Path (Split-Path $output) | Out-Null
    $sb = [System.Text.StringBuilder]::new()
    [void]$sb.AppendLine("# Eddie's AI Tooling Setup - Project Knowledge")
    [void]$sb.AppendLine('')
    [void]$sb.AppendLine('> Auto-generated by `setup.ps1 -GenerateMobile`. Do not edit directly.')
    [void]$sb.AppendLine('> Source: github.com/edward-rosado/claude-setup')
    [void]$sb.AppendLine('')
    [void]$sb.AppendLine('---')
    [void]$sb.AppendLine('')

    Get-ChildItem -Directory (Join-Path $ScriptDir 'rules') -ErrorAction SilentlyContinue | ForEach-Object {
        $groupName = $_.Name
        $cap = $groupName.Substring(0,1).ToUpper() + $groupName.Substring(1)
        [void]$sb.AppendLine("## Rules - $cap")
        [void]$sb.AppendLine('')
        Get-ChildItem -File -Filter '*.md' $_.FullName | ForEach-Object {
            [void]$sb.AppendLine((Get-Content -Raw $_.FullName))
            [void]$sb.AppendLine('')
            [void]$sb.AppendLine('---')
            [void]$sb.AppendLine('')
        }
    }

    [void]$sb.AppendLine('## Available Skills')
    [void]$sb.AppendLine('')
    Get-ChildItem -Directory (Join-Path $ScriptDir 'skills') -ErrorAction SilentlyContinue | ForEach-Object {
        Get-ChildItem -Directory $_.FullName | ForEach-Object {
            [void]$sb.AppendLine("- **/$($_.Name)**")
            $skillMd = Join-Path $_.FullName 'SKILL.md'
            if (Test-Path $skillMd) {
                $descLine = Select-String -Path $skillMd -Pattern '^description:' | Select-Object -First 1
                if ($descLine) {
                    $desc = $descLine.Line -replace '^description:\s*', ''
                    if ($desc) { [void]$sb.AppendLine("  $desc") }
                }
            }
        }
    }
    [void]$sb.AppendLine('')

    Set-Content -LiteralPath $output -Value $sb.ToString() -Encoding utf8
    Write-Ok "Generated: $output"
}

# --- Sync instincts -------------------------------------------------------
function Invoke-Sync {
    Write-Log "Syncing learned instincts from $ClaudeHome into repo..."
    $instinctSrc = Join-Path $ClaudeHome 'homunculus'
    $instinctTgt = Join-Path $ScriptDir 'learned/instincts'

    if (-not (Test-Path $instinctSrc)) {
        Write-Warn "No homunculus directory found at $instinctSrc"
        return
    }
    if ($DryRun) { Write-Dry "Would sync instincts from $instinctSrc"; return }

    New-Item -ItemType Directory -Force -Path $instinctTgt | Out-Null
    $count = 0
    Get-ChildItem -Recurse -File -Filter '*.json' $instinctSrc -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '[\\/]instincts[\\/]' } |
        ForEach-Object {
            $dest = Join-Path $instinctTgt $_.Name
            if (-not (Test-Path $dest)) {
                Copy-Item -Force $_.FullName $dest
                Write-Ok "Synced: $($_.Name)"
                $count++
            }
        }
    if ($count -eq 0) { Write-Log "No new instincts to sync" }
}

# --- Test -----------------------------------------------------------------
function Invoke-Test {
    Write-Log "Running test suite..."
    $testFile = Join-Path $ScriptDir 'tests/test_setup.sh'
    if (-not (Test-Path $testFile)) {
        Write-Err "Test file not found: tests/test_setup.sh"
        return 1
    }
    $bash = Get-Command bash -ErrorAction SilentlyContinue
    if (-not $bash) {
        Write-Warn "The test suite (tests/test_setup.sh) requires bash. Install Git for Windows (provides Git Bash) and re-run, or run the tests on macOS/Linux."
        return 1
    }
    & $bash.Source $testFile $ScriptDir
    return $LASTEXITCODE
}

# --- Usage ----------------------------------------------------------------
function Show-Usage {
    @'
Usage: .\setup.ps1 [OPTIONS] <COMMAND>

Claude Setup - Windows-native AI tooling bootstrap (PowerShell).

Commands (pass exactly one):
  -Install           Symlink rules + skills into ~/.claude/, merge settings
  -Uninstall         Remove what was installed, preserve backups
  -Check             Report installation status
  -GenerateMobile    Generate mobile/project-knowledge.md
  -Sync              Pull new learned instincts into the repo
  -Test              Run the test suite (requires bash / Git Bash)

Options:
  -ClaudeHome DIR    Override ~/.claude/ location (for testing)
  -DryRun            Show what would happen without making changes
  -VerboseOutput     Show extra detail

Examples:
  .\setup.ps1 -Install
  .\setup.ps1 -Check
  .\setup.ps1 -Install -DryRun
'@ | Write-Host
}

# --- Main -----------------------------------------------------------------
$commands = @($Install, $Uninstall, $Check, $GenerateMobile, $Sync, $Test) | Where-Object { $_ }
if ($commands.Count -ne 1) {
    Show-Usage
    exit 1
}

if ($Install)        { Invoke-Install }
elseif ($Uninstall)  { Invoke-Uninstall }
elseif ($Check)      { exit (Invoke-Check) }
elseif ($GenerateMobile) { Invoke-GenerateMobile }
elseif ($Sync)       { Invoke-Sync }
elseif ($Test)       { exit (Invoke-Test) }
