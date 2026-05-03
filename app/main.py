from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from app.orchestrator import PaymentModuleOrchestrator

app = FastAPI(title="30 Bağımsız AI Ajan Orkestrasyonu", version="0.1.0")
orchestrator = PaymentModuleOrchestrator()


class PaymentModuleRequest(BaseModel):
    objective: str = "Complex E-commerce Payment Module"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/agents")
async def agents() -> list[dict[str, str]]:
    return orchestrator.list_agents()


@app.post("/orchestrate/payment-module")
async def orchestrate_payment_module(request: PaymentModuleRequest) -> dict:
    result = await orchestrator.orchestrate_payment_module(request.objective)
    return result.model_dump(mode="json")
