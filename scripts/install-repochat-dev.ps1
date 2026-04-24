$ErrorActionPreference = "Stop"

# Find the repository root by walking upward until we find pyproject.toml
# and the repo_assistant package directory.
function Find-RepoRoot {
    param(
        [string]$StartPath
    )

    $Current = Resolve-Path $StartPath

    while ($true) {
        $PyprojectPath = Join-Path $Current "pyproject.toml"
        $PackagePath = Join-Path $Current "repo_assistant"

        if ((Test-Path $PyprojectPath) -and (Test-Path $PackagePath)) {
            return $Current
        }

        $Parent = Split-Path -Parent $Current

        if ($Parent -eq $Current -or [string]::IsNullOrWhiteSpace($Parent)) {
            throw "Could not find repo root. Expected pyproject.toml and repo_assistant/ above $StartPath"
        }

        $Current = $Parent
    }
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Find-RepoRoot -StartPath $ScriptDir

# Create a user-local bin folder for the repochat launcher.
$BinDir = Join-Path $env:USERPROFILE ".repochat\bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

# Create repochat.cmd.
$CmdPath = Join-Path $BinDir "repochat.cmd"

$CmdContent = @"
@echo off
set "PYTHONPATH=$RepoRoot;%PYTHONPATH%"
py -X utf8 -m repo_assistant.cli %*
"@

Set-Content -Path $CmdPath -Value $CmdContent -Encoding ASCII

# Add the bin directory to the user's PATH if it is not already there.
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$PathParts = @()

if ($UserPath) {
    $PathParts = $UserPath -split ";"
}

if ($PathParts -notcontains $BinDir) {
    $NewPath = if ($UserPath) { "$UserPath;$BinDir" } else { $BinDir }
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Write-Host "Added $BinDir to your user PATH."
} else {
    Write-Host "$BinDir is already on your user PATH."
}

# Update PATH for the current PowerShell session too.
if (($env:Path -split ";") -notcontains $BinDir) {
    $env:Path = "$BinDir;$env:Path"
}

Write-Host ""
Write-Host "Installed repochat launcher:"
Write-Host $CmdPath
Write-Host ""
Write-Host "Repo root:"
Write-Host $RepoRoot
Write-Host ""
Write-Host "Try:"
Write-Host "repochat.cmd --help"
Write-Host "repochat.cmd ask `"How does the backend work?`""