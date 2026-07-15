"""触发工作流端到端测试。"""
import asyncio
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent))

from app.services.workflow_scheduler import workflow_scheduler


async def main():
    wf_id = await workflow_scheduler.trigger_workflow(
        episode_date=date.today(),
        source="manual",
        channel_id=2,
        triggered_by="test",
    )
    print(f"触发成功: {wf_id}")


asyncio.run(main())
