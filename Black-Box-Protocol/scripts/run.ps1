$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

& "$PSScriptRoot\setup.ps1"
$env:NEMO_GUARDRAILS_COMMAND = ".venv-nemo312/Scripts/python.exe providers/nemo_local.py --serve"
$env:GUARDRAILS_AI_COMMAND = ".venv-guardrails312/Scripts/python.exe providers/guardrails_ai_local.py --serve"
python scripts/setup_and_run.py --execute @args
