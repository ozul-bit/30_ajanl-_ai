from __future__ import annotations

import copy
import re
import time
from typing import Any
from uuid import uuid4

from app.agent import IndependentAgent
from app.models import AgentOutput, AgentStatus, DispatchEvent, IndependentTaskPackage

SECRET_KEY_PATTERN = re.compile(r"(api[_-]?key|secret|token|password|credential|authorization|private[_-]?key)", re.IGNORECASE)
PROJECT_IDENTIFIER_PATTERN = re.compile(r"30_ajanl-_ai|ozul-bit/30_ajanl-_ai|/home/30_ajanl-_ai", re.IGNORECASE)


class Dispatcher:
    def __init__(self, max_retries: int = 1) -> None:
        self.max_retries = max_retries
        self.event_log: list[DispatchEvent] = []
        self.immutable_outputs: list[AgentOutput] = []

    def reset(self) -> None:
        self.event_log = []
        self.immutable_outputs = []

    def anonymize(self, payload: Any) -> Any:
        if isinstance(payload, dict):
            clean: dict[str, Any] = {}
            for key, value in payload.items():
                if SECRET_KEY_PATTERN.search(key):
                    clean[key] = "[REDACTED]"
                else:
                    clean[key] = self.anonymize(value)
            return clean
        if isinstance(payload, list):
            return [self.anonymize(item) for item in payload]
        if isinstance(payload, str):
            return PROJECT_IDENTIFIER_PATTERN.sub("[PROJECT]", payload)
        return payload

    def build_minimal_package(
        self,
        correlation_id: str,
        agent: IndependentAgent,
        objective: str,
        minimal_context: dict[str, Any],
        constraints: list[str] | None = None,
        attempt: int = 1,
    ) -> IndependentTaskPackage:
        sanitized = self.anonymize(copy.deepcopy(minimal_context))
        package = IndependentTaskPackage(
            correlation_id=correlation_id,
            agent_id=agent.agent_id,
            role=agent.role,
            objective=self.anonymize(objective),
            minimal_context=sanitized,
            constraints=constraints or [
                "Sadece bu JSON paketini kullan.",
                "Paylaşılan state veya ana repo erişimi yok.",
                "Çıktıyı yalnızca sandbox içinde artifact olarak üret.",
                "Yapılandırılmış JSON döndür.",
            ],
            anonymized=True,
            attempt=attempt,
        )
        self.event_log.append(
            DispatchEvent(
                correlation_id=correlation_id,
                agent_id=agent.agent_id,
                role=agent.role,
                task_id=package.task_id,
                status="sanitized",
                anonymized=True,
                message="Postman minimal paketi anonimleştirdi ve global bağlamı çıkardı.",
            )
        )
        return package

    async def dispatch(
        self,
        agent: IndependentAgent,
        correlation_id: str,
        objective: str,
        minimal_context: dict[str, Any],
        constraints: list[str] | None = None,
    ) -> AgentOutput:
        last_output: AgentOutput | None = None
        for attempt in range(1, self.max_retries + 2):
            package = self.build_minimal_package(correlation_id, agent, objective, minimal_context, constraints, attempt)
            self.event_log.append(
                DispatchEvent(
                    correlation_id=correlation_id,
                    agent_id=agent.agent_id,
                    role=agent.role,
                    task_id=package.task_id,
                    status="dispatched",
                    anonymized=True,
                    message=f"Postman paketi bağımsız ajana iletti; deneme {attempt}.",
                )
            )
            started = time.perf_counter()
            output = await agent.run(package)
            self.immutable_outputs.append(output.model_copy(deep=True))
            self.event_log.append(
                DispatchEvent(
                    correlation_id=correlation_id,
                    agent_id=agent.agent_id,
                    role=agent.role,
                    task_id=package.task_id,
                    status=output.status,
                    anonymized=True,
                    message="Ajan tamamlandı; sonuç yalnızca orkestratör immutable output deposuna eklendi.",
                    errors=output.errors,
                    timings={"duration_seconds": round(time.perf_counter() - started, 4)},
                )
            )
            if output.status == AgentStatus.succeeded:
                return output
            last_output = output
            if attempt <= self.max_retries:
                self.event_log.append(
                    DispatchEvent(
                        correlation_id=correlation_id,
                        agent_id=agent.agent_id,
                        role=agent.role,
                        task_id=package.task_id,
                        status=AgentStatus.retried,
                        anonymized=True,
                        message="Ajan hatası izole edildi; yalnızca aynı ajan yeniden denenecek, diğer ajanlara bilgi verilmeyecek.",
                        errors=output.errors,
                    )
                )
        return last_output or output

    def package_from_outputs(self, outputs: list[AgentOutput], sections: list[str]) -> dict[str, Any]:
        focused: dict[str, Any] = {section: [] for section in sections}
        for output in outputs:
            if output.status != AgentStatus.succeeded:
                continue
            section = output.data.get("section", output.role)
            if section in focused:
                focused[section].append({"role": output.role, "summary": output.summary, "data": output.data})
        return self.anonymize(focused)
