$ErrorActionPreference = 'Stop'
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[api]'
python -m uvicorn orchestrator.interfaces.api.app:app --host 127.0.0.1 --port 8765
