$ErrorActionPreference = 'Stop'
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[mcp]'
python -m orchestrator.interfaces.mcp.server
