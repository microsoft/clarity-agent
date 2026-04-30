# Clarity bootstrap installer — Windows.
#
# Downloads uv, clones the repo, then hands off to Python.
# Python handles everything else (app assembly, shortcuts, etc.)
#
# Usage (PowerShell):
#   irm https://raw.githubusercontent.com/microsoft/clarity-agent/main/scripts/install.ps1 | iex
#   irm ... | iex; # or with branch: & ([scriptblock]::Create((irm ...))) --branch my-branch

param(
    [string]$Branch = "main",
    [Parameter(ValueFromRemainingArguments)][string[]]$ForwardArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Repo = "https://github.com/microsoft/clarity-agent.git"
$Work = Join-Path $env:TEMP "clarity-install-$(Get-Random)"
New-Item -ItemType Directory -Path $Work | Out-Null

try {
    # --- Download uv ---------------------------------------------------------
    Write-Host "Downloading uv..."
    $UvZip = Join-Path $Work "uv.zip"
    $UvDir = Join-Path $Work "uv-extract"
    Invoke-WebRequest `
        -Uri "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" `
        -OutFile $UvZip
    Expand-Archive -Path $UvZip -DestinationPath $UvDir -Force
    $Uv = Get-ChildItem -Path $UvDir -Filter "uv.exe" -Recurse | Select-Object -First 1 -ExpandProperty FullName

    # --- Clone the repo ------------------------------------------------------
    Write-Host "Downloading Clarity (branch: $Branch)..."
    $AppSrc = Join-Path $Work "clarity-agent"
    git clone --depth 1 --branch $Branch $Repo $AppSrc

    # --- Hand off to Python --------------------------------------------------
    # Python detects the platform and handles everything from here.
    & $Uv run --directory $AppSrc python clarity.py install @ForwardArgs

} finally {
    Remove-Item -Recurse -Force $Work -ErrorAction SilentlyContinue
}
