from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from uuid import uuid4

from app.agent import IndependentAgent
from app.dispatcher import Dispatcher
from app.models import AgentOutput, AgentStatus, OrchestrationResult, ProviderConfig
from app.prompts import AGENT_PROMPTS
from app.sandbox import SandboxManager

PAYMENT_MODULE_FLOW_DIAGRAM = """```mermaid
flowchart TD
    U[İstek: E-commerce Payment Module] --> P[Postman / Dispatcher]
    P --> W1[Dalga 1: gereksinim, ürün, mimari, domain]
    W1 --> P
    P --> W2[Dalga 2: DB, API, backend, ödeme, güvenlik, frontend]
    W2 --> P
    P --> W3[Dalga 3: QA, performans, DevOps, SRE, privacy, accessibility, risk]
    W3 --> P
    P --> F[agent_30_final_integrator]
    F --> M[Final merge: requirements, architecture, DB, API, security, backend, frontend, tests, deployment, docs, risk]
```
"""

PROVIDER_ROTATION = [
    ("openai", "gpt-4.1"),
    ("anthropic", "claude-3-5-sonnet"),
    ("local", "llama-3.1-8b"),
    ("azure-openai", "gpt-4o"),
    ("google", "gemini-1.5-pro"),
]

WAVES: list[list[str]] = [
    [
        "agent_01_requirements_analyst",
        "agent_02_product_owner",
        "agent_03_system_architect",
        "agent_06_domain_modeler",
    ],
    [
        "agent_04_database_architect",
        "agent_05_api_designer",
        "agent_07_backend_specialist",
        "agent_08_payment_integration",
        "agent_09_security_auditor",
        "agent_10_compliance_specialist",
        "agent_11_react_specialist",
        "agent_12_ux_designer",
        "agent_13_mobile_specialist",
        "agent_20_data_privacy",
        "agent_26_integration_engineer",
    ],
    [
        "agent_14_qa_engineer",
        "agent_15_test_automation",
        "agent_16_performance_engineer",
        "agent_17_devops_specialist",
        "agent_18_sre_specialist",
        "agent_19_observability",
        "agent_21_code_reviewer",
        "agent_22_refactoring_specialist",
        "agent_23_documentation",
        "agent_24_release_manager",
        "agent_25_risk_manager",
        "agent_27_localization",
        "agent_28_accessibility",
        "agent_29_finops",
    ],
    ["agent_30_final_integrator"],
]

SECTION_KEYS = [
    "requirements",
    "architecture",
    "db_schema",
    "api_contract",
    "security",
    "backend",
    "frontend",
    "tests",
    "deployment",
    "docs",
    "risk_register",
]


class PaymentModuleOrchestrator:
    def __init__(self, dispatcher: Dispatcher | None = None, sandbox_manager: SandboxManager | None = None) -> None:
        self.dispatcher = dispatcher or Dispatcher(max_retries=1)
        self.sandbox_manager = sandbox_manager or SandboxManager(cleanup_on_exit=False)
        self.agents = self._register_agents()

    def _register_agents(self) -> dict[str, IndependentAgent]:
        agents: dict[str, IndependentAgent] = {}
        for index, (agent_id, prompt) in enumerate(AGENT_PROMPTS.items()):
            provider, model = PROVIDER_ROTATION[index % len(PROVIDER_ROTATION)]
            env_provider = provider.upper().replace("-", "_")
            api_key_env = f"AGENT_{index + 1:02d}_{env_provider}_API_KEY"
            agents[agent_id] = IndependentAgent(
                agent_id=agent_id,
                role=prompt["role"],
                provider_config=ProviderConfig(provider=provider, model=model, api_key_env=api_key_env, timeout_seconds=6.0),
                sandbox_manager=self.sandbox_manager,
            )
        return agents

    def list_agents(self) -> list[dict[str, str]]:
        return [
            {
                "agent_id": agent_id,
                "name": prompt["name"],
                "role": prompt["role"],
                "provider": self.agents[agent_id].provider_config.provider,
                "model": self.agents[agent_id].provider_config.model,
                "api_key_env": self.agents[agent_id].provider_config.api_key_env,
            }
            for agent_id, prompt in AGENT_PROMPTS.items()
        ]

    async def orchestrate_payment_module(self, objective: str = "Complex E-commerce Payment Module") -> OrchestrationResult:
        self.dispatcher.reset()
        started = datetime.now(timezone.utc)
        start_perf = time.perf_counter()
        correlation_id = str(uuid4())
        all_outputs: list[AgentOutput] = []
        base_context = {
            "module": "E-commerce Payment Module",
            "scope": ["payment authorization", "capture", "refund", "webhooks", "frontend checkout"],
            "sensitive_example_api_key": "should-never-leak",
            "project_path": "/home/30_ajanl-_ai",
        }
        for wave_index, wave in enumerate(WAVES, start=1):
            tasks = []
            for agent_id in wave:
                agent = self.agents[agent_id]
                if agent.role == "final_integration":
                    context = self.dispatcher.package_from_outputs(all_outputs, SECTION_KEYS)
                elif wave_index == 1:
                    context = {"wave": wave_index, "base": base_context, "role_focus": agent.role}
                else:
                    context = {
                        "wave": wave_index,
                        "role_focus": agent.role,
                        "postman_previous_summaries": self.dispatcher.package_from_outputs(all_outputs, self._sections_for_role(agent.role)),
                    }
                tasks.append(self.dispatcher.dispatch(agent, correlation_id, objective, context))
            wave_outputs = await asyncio.gather(*tasks)
            all_outputs.extend(wave_outputs)
        merged = self._merge_outputs(all_outputs)
        status = "completed" if any(output.status == AgentStatus.succeeded for output in all_outputs) else "failed"
        return OrchestrationResult(
            correlation_id=correlation_id,
            status=status,
            objective=objective,
            agent_outputs=all_outputs,
            event_log=self.dispatcher.event_log,
            merged_result=merged,
            flow_diagram=PAYMENT_MODULE_FLOW_DIAGRAM,
            timings={"duration_seconds": round(time.perf_counter() - start_perf, 4)},
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )

    def _sections_for_role(self, role: str) -> list[str]:
        mapping = {
            "database": ["requirements", "architecture"],
            "api_contract": ["requirements", "architecture"],
            "backend": ["requirements", "architecture", "db_schema", "api_contract"],
            "payment_integration": ["requirements", "architecture", "api_contract"],
            "security": ["requirements", "api_contract", "backend"],
            "frontend": ["requirements", "api_contract"],
            "qa": ["requirements", "api_contract", "backend", "frontend"],
            "deployment": ["architecture", "backend", "security"],
            "documentation": SECTION_KEYS,
            "risk_register": SECTION_KEYS,
        }
        return mapping.get(role, SECTION_KEYS[:4])

    def _merge_outputs(self, outputs: list[AgentOutput]) -> dict[str, list[dict[str, object]]]:
        merged: dict[str, list[dict[str, object]]] = {key: [] for key in SECTION_KEYS}
        failed: list[dict[str, object]] = []
        for output in outputs:
            if output.status != AgentStatus.succeeded:
                failed.append({"agent_id": output.agent_id, "role": output.role, "errors": output.errors})
                continue
            section = output.data.get("section")
            target = section if section in merged else self._fallback_section(output.role)
            if target in merged:
                merged[target].append({"agent_id": output.agent_id, "role": output.role, "summary": output.summary, "data": output.data})
        merged["risk_register"].extend(failed)
        return merged

    def _fallback_section(self, role: str) -> str:
        if role in {"requirements", "product_scope"}:
            return "requirements"
        if role in {"architecture", "domain_model", "integration"}:
            return "architecture"
        if role in {"security", "privacy", "compliance"}:
            return "security"
        if role in {"frontend", "ux", "mobile", "localization", "accessibility"}:
            return "frontend"
        if role in {"qa", "test_automation", "performance"}:
            return "tests"
        if role in {"deployment", "reliability", "observability", "release"}:
            return "deployment"
        if role == "documentation":
            return "docs"
        return "risk_register"
