from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class AgentStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    timed_out = "timed_out"
    retried = "retried"


class ProviderConfig(BaseModel):
    provider: str
    model: str
    api_key_env: str
    endpoint: str | None = None
    timeout_seconds: float = 8.0


class SandboxInfo(BaseModel):
    run_id: str
    agent_id: str
    root_path: Path
    package_path: Path | None = None
    artifact_path: Path | None = None
    cleanup_on_exit: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(arbitrary_types_allowed=True)


class IndependentTaskPackage(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str
    agent_id: str
    role: str
    objective: str
    minimal_context: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    anonymized: bool = False
    sandbox: SandboxInfo | None = None
    attempt: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentOutput(BaseModel):
    task_id: str
    correlation_id: str
    agent_id: str
    role: str
    status: AgentStatus
    summary: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
    sandbox_path: str | None = None
    timings: dict[str, float] = Field(default_factory=dict)
    attempt: int = 1
    started_at: datetime | None = None
    finished_at: datetime | None = None


class DispatchEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    correlation_id: str
    agent_id: str
    role: str
    task_id: str | None = None
    status: AgentStatus | Literal["dispatched", "sanitized", "merged"]
    anonymized: bool = False
    message: str
    errors: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timings: dict[str, float] = Field(default_factory=dict)


class OrchestrationResult(BaseModel):
    correlation_id: str
    status: str
    objective: str
    agent_outputs: list[AgentOutput]
    event_log: list[DispatchEvent]
    merged_result: dict[str, Any]
    flow_diagram: str
    timings: dict[str, float] = Field(default_factory=dict)
    started_at: datetime
    finished_at: datetime


class GenerateFromPromptRequest(BaseModel):
    prompt: str = Field(min_length=1)
    target: Literal["web_site", "web_app", "api", "full_stack"] = "web_site"
    style: str | None = None
    features: list[str] = Field(default_factory=list)
