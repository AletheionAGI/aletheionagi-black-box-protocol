$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

$Uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $Uv) {
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $Uv = Get-Command uv -ErrorAction SilentlyContinue
}
if (-not $Uv) {
    $Candidate = Join-Path $HOME ".local\bin\uv.exe"
    if (Test-Path $Candidate) { $UvPath = $Candidate }
    else { throw "uv was installed but could not be located" }
} else {
    $UvPath = $Uv.Source
}

python scripts/setup_providers.py --uv $UvPath
