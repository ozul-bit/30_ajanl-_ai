from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from app.models import AgentOutput, AgentStatus, IndependentTaskPackage, ProviderConfig
from app.sandbox import SandboxManager


class AgentExecutionError(RuntimeError):
    pass


class Agent(Protocol):
    async def run(self, independent_task_package: IndependentTaskPackage) -> AgentOutput:
        ...


class IndependentAgent:
    def __init__(self, agent_id: str, role: str, provider_config: ProviderConfig, sandbox_manager: SandboxManager | None = None) -> None:
        self.agent_id = agent_id
        self.role = role
        self.provider_config = provider_config
        self.sandbox_manager = sandbox_manager or SandboxManager()

    async def run(self, independent_task_package: IndependentTaskPackage) -> AgentOutput:
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc)
        sandbox = self.sandbox_manager.create(self.agent_id, independent_task_package.correlation_id)
        independent_task_package.sandbox = sandbox
        independent_task_package.agent_id = self.agent_id
        independent_task_package.role = self.role
        sandbox = self.sandbox_manager.write_package(sandbox, independent_task_package)
        output_path = sandbox.root_path / "agent_output.json"
        provider_json = self.provider_config.model_dump_json()
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "app.agent_worker",
                "--package",
                str(sandbox.package_path),
                "--provider",
                provider_json,
                "--output",
                str(output_path),
                cwd=str(Path(__file__).resolve().parents[1]),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.provider_config.timeout_seconds)
            except asyncio.TimeoutError as exc:
                proc.kill()
                await proc.communicate()
                raise AgentExecutionError(f"agent timeout after {self.provider_config.timeout_seconds}s") from exc
            if proc.returncode != 0:
                message = stderr.decode("utf-8", errors="replace") or stdout.decode("utf-8", errors="replace")
                raise AgentExecutionError(message.strip() or f"agent exited with {proc.returncode}")
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            output = AgentOutput.model_validate(payload)
            output.timings["duration_seconds"] = round(time.perf_counter() - started, 4)
            output.started_at = started_at
            output.finished_at = datetime.now(timezone.utc)
            return output
        except Exception as exc:
            status = AgentStatus.timed_out if "timeout" in str(exc).lower() else AgentStatus.failed
            return AgentOutput(
                task_id=independent_task_package.task_id,
                correlation_id=independent_task_package.correlation_id,
                agent_id=self.agent_id,
                role=self.role,
                status=status,
                summary=f"{self.agent_id} izole süreçte başarısız oldu; hata yalnızca orkestratöre bildirildi.",
                errors=[str(exc)],
                artifacts={},
                sandbox_path=str(sandbox.root_path),
                timings={"duration_seconds": round(time.perf_counter() - started, 4)},
                attempt=independent_task_package.attempt,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
            )
