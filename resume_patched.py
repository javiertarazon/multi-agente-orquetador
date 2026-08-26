import asyncio
import json
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Importar directamente el modulo del servidor MCP (con el parche aplicado)
from orchestrator.interfaces.mcp.server import mcp

async def main():
    # Reanudar el plan: reencola no terminales y arranca supervisor con codigo parcheado
    result = await mcp.call_tool('resume_plan', {'plan_id': 'd5bd6d2cd138494c947e6b63abccebff'})
    for item in result:
        if hasattr(item, 'text'):
            print(item.text)

asyncio.run(main())