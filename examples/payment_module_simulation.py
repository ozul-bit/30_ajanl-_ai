from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.orchestrator import PaymentModuleOrchestrator


async def main() -> None:
    orchestrator = PaymentModuleOrchestrator()
    result = await orchestrator.orchestrate_payment_module("Complex E-commerce Payment Module")
    print(result.flow_diagram)
    print(json.dumps(result.merged_result, ensure_ascii=False, indent=2))
    print(f"agents={len(result.agent_outputs)} events={len(result.event_log)} status={result.status}")


if __name__ == "__main__":
    asyncio.run(main())
