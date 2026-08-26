#!/bin/bash
cd "$(dirname "$0")/.."
source .venv/bin/activate
while true; do
    echo "[$(date)] MCP Server starting..."
    python -m orchestrator.interfaces.mcp.server
    EXIT_CODE=$?
    echo "[$(date)] MCP Server exited with code $EXIT_CODE"
    echo "Restarting in 2 seconds..."
    sleep 2
done
