import asyncio
import json
from orchestrator.interfaces.mcp.server import mcp

async def test():
    # Use the plan_id from the create_plan result
    plan_task_ids = [
        "b59f67666c3e4e0cab6b088073eb4d2b",
        "6f666a690e454ccdaa90483ce064cf0d",
        "690ad15c0c2b48b9ad1ee713d1d709b5",
        "30e0ec0ef4e844c1931e46515f6d9400",
        "72627bed25334f9b9add32073a4a7784",
        "0640e3775c28471db5ead59f6cdcbfe0"
    ]
    
    result = await mcp.call_tool('execute_plan', {'plan_task_ids': plan_task_ids, 'approved_by': 'copilot'})
    print('Execute Plan Result:')
    for item in result:
        if hasattr(item, 'text'):
            print(item.text)
        else:
            print(json.dumps(item, indent=2))

asyncio.run(test())