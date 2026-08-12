$ErrorActionPreference = 'Stop'
.\.venv\Scripts\Activate.ps1
maoq init
$id = maoq task create 'Ejecutar prueba de humo' --executor simulated
maoq worker --once
maoq task list
pytest -q
