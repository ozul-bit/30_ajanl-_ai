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

PROMPT_TO_APP_FLOW_DIAGRAM = """```mermaid
flowchart TD
    U[Kullanıcı prompt'u + target] --> P[Postman / Dispatcher]
    P --> W1[Dalga 1: ürün gereksinimi, bilgi mimarisi, teknik yön]
    W1 --> P
    P --> W2[Dalga 2: frontend, UX, API, backend, veri, güvenlik, entegrasyon]
    W2 --> P
    P --> W3[Dalga 3: QA, performans, DevOps, SRE, docs, release, accessibility, localization, risk, finops]
    W3 --> P
    P --> F[agent_30_final_integrator]
    F --> M[Structured project blueprint: spec, IA, UI, code plans, generated files, tests, deployment, risks]
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

APP_SECTION_KEYS = [
    "product_spec",
    "information_architecture",
    "ui_design",
    "frontend_code_plan",
    "backend_code_plan",
    "data_model",
    "api_contract",
    "security_privacy",
    "test_plan",
    "deployment_plan",
    "generated_files",
    "implementation_steps",
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

    async def generate_from_prompt(
        self,
        prompt: str,
        target: str = "web_site",
        style: str | None = None,
        features: list[str] | None = None,
    ) -> OrchestrationResult:
        self.dispatcher.reset()
        started = datetime.now(timezone.utc)
        start_perf = time.perf_counter()
        correlation_id = str(uuid4())
        all_outputs: list[AgentOutput] = []
        requested_features = features or []
        objective = f"Prompt-to-{target} generation blueprint"
        base_context = {
            "generation_mode": "prompt_to_app",
            "prompt": prompt,
            "target": target,
            "style": style,
            "features": requested_features,
            "routing_note": "Only anonymized prompt facts and role-focused summaries are sent to agents.",
        }
        for wave_index, wave in enumerate(WAVES, start=1):
            tasks = []
            for agent_id in wave:
                agent = self.agents[agent_id]
                if agent.role == "final_integration":
                    context = {
                        "generation_mode": "prompt_to_app",
                        "target": target,
                        "style": style,
                        "features": requested_features,
                        "postman_previous_summaries": self.dispatcher.package_from_outputs(all_outputs, APP_SECTION_KEYS),
                    }
                elif wave_index == 1:
                    context = {"wave": wave_index, "base": base_context, "role_focus": agent.role}
                else:
                    context = {
                        "generation_mode": "prompt_to_app",
                        "wave": wave_index,
                        "target": target,
                        "style": style,
                        "features": requested_features,
                        "role_focus": agent.role,
                        "postman_previous_summaries": self.dispatcher.package_from_outputs(all_outputs, self._app_sections_for_role(agent.role)),
                    }
                tasks.append(self.dispatcher.dispatch(agent, correlation_id, objective, context))
            wave_outputs = await asyncio.gather(*tasks)
            all_outputs.extend(wave_outputs)
        merged = self._merge_outputs(all_outputs, APP_SECTION_KEYS)
        status = "completed" if any(output.status == AgentStatus.succeeded for output in all_outputs) else "failed"
        return OrchestrationResult(
            correlation_id=correlation_id,
            status=status,
            objective=objective,
            agent_outputs=all_outputs,
            event_log=self.dispatcher.event_log,
            merged_result=merged,
            flow_diagram=PROMPT_TO_APP_FLOW_DIAGRAM,
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

    def _app_sections_for_role(self, role: str) -> list[str]:
        mapping = {
            "requirements": ["product_spec", "information_architecture"],
            "product_scope": ["product_spec", "information_architecture"],
            "architecture": ["product_spec", "backend_code_plan", "frontend_code_plan", "api_contract"],
            "domain_model": ["product_spec", "data_model"],
            "database": ["product_spec", "data_model", "backend_code_plan"],
            "api_contract": ["product_spec", "api_contract", "backend_code_plan"],
            "backend": ["product_spec", "api_contract", "backend_code_plan", "data_model"],
            "payment_integration": ["product_spec", "api_contract", "backend_code_plan"],
            "security": ["product_spec", "api_contract", "backend_code_plan", "security_privacy"],
            "compliance": ["product_spec", "security_privacy"],
            "frontend": ["product_spec", "information_architecture", "ui_design", "frontend_code_plan"],
            "ux": ["product_spec", "information_architecture", "ui_design"],
            "mobile": ["product_spec", "ui_design", "frontend_code_plan"],
            "privacy": ["product_spec", "security_privacy", "data_model"],
            "integration": ["api_contract", "backend_code_plan", "deployment_plan"],
            "qa": ["product_spec", "frontend_code_plan", "backend_code_plan", "test_plan"],
            "test_automation": ["product_spec", "test_plan", "generated_files"],
            "performance": ["frontend_code_plan", "backend_code_plan", "test_plan", "deployment_plan"],
            "deployment": ["backend_code_plan", "frontend_code_plan", "deployment_plan"],
            "reliability": ["deployment_plan", "test_plan"],
            "observability": ["deployment_plan", "backend_code_plan"],
            "documentation": APP_SECTION_KEYS,
            "release": ["deployment_plan", "implementation_steps", "risk_register"],
            "risk_register": APP_SECTION_KEYS,
        }
        return mapping.get(role, APP_SECTION_KEYS[:4])

    def _merge_outputs(self, outputs: list[AgentOutput], section_keys: list[str] | None = None) -> dict[str, list[dict[str, object]]]:
        keys = section_keys or SECTION_KEYS
        merged: dict[str, list[dict[str, object]]] = {key: [] for key in keys}
        failed: list[dict[str, object]] = []
        for output in outputs:
            if output.status != AgentStatus.succeeded:
                failed.append({"agent_id": output.agent_id, "role": output.role, "errors": output.errors})
                continue
            section = output.data.get("section")
            target = section if section in merged else self._fallback_section(output.role, keys)
            if target in merged:
                merged[target].append({"agent_id": output.agent_id, "role": output.role, "summary": output.summary, "data": output.data})
        merged["risk_register"].extend(failed)
        return merged

    def _fallback_section(self, role: str, section_keys: list[str] | None = None) -> str:
        keys = section_keys or SECTION_KEYS
        if keys == APP_SECTION_KEYS:
            if role in {"requirements", "product_scope", "domain_model"}:
                return "product_spec"
            if role in {"architecture", "integration"}:
                return "implementation_steps"
            if role in {"database"}:
                return "data_model"
            if role in {"api_contract"}:
                return "api_contract"
            if role in {"backend", "payment_integration", "refactoring"}:
                return "backend_code_plan"
            if role in {"security", "privacy", "compliance"}:
                return "security_privacy"
            if role in {"frontend", "ux", "mobile", "localization", "accessibility"}:
                return "ui_design"
            if role in {"qa", "test_automation", "performance", "code_review"}:
                return "test_plan"
            if role in {"deployment", "reliability", "observability", "release", "cost_controls"}:
                return "deployment_plan"
            if role in {"documentation", "final_integration"}:
                return "implementation_steps"
            return "risk_register"
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
