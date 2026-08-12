$ErrorActionPreference = 'Stop'
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
Write-Host 'Instalacion completada. Activa con .\.venv\Scripts\Activate.ps1'
