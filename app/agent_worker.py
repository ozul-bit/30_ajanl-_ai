from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROLE_PAYLOADS: dict[str, dict[str, Any]] = {
    "requirements": {"section": "requirements", "items": ["kart tokenizasyonu", "3DS doğrulama", "iade/iptal akışı", "idempotent ödeme denemeleri"]},
    "product_scope": {"section": "requirements", "items": ["MVP: kart ödeme, kayıtlı kart, iade", "KPI: başarılı ödeme oranı ve işlem süresi"]},
    "architecture": {"section": "architecture", "components": ["payment-api", "payment-worker", "provider-adapter", "ledger-service", "webhook-consumer"]},
    "database": {"section": "db_schema", "tables": ["payments", "payment_attempts", "refunds", "webhook_events", "payment_methods"]},
    "api_contract": {"section": "api_contract", "endpoints": ["POST /payments", "GET /payments/{id}", "POST /payments/{id}/refunds", "POST /webhooks/providers/{provider}"]},
    "domain_model": {"section": "architecture", "models": ["Payment", "PaymentAttempt", "Refund", "ProviderWebhook", "Money"]},
    "backend": {"section": "backend", "modules": ["idempotency middleware", "provider adapter interface", "transactional ledger writes"]},
    "payment_integration": {"section": "backend", "providers": ["stripe-like adapter", "iyzico-like adapter", "local fake gateway"], "rules": ["provider secrets env üzerinden okunur"]},
    "security": {"section": "security", "controls": ["PCI kapsamını tokenizasyonla azalt", "webhook imza doğrulaması", "PII log redaksiyonu"]},
    "compliance": {"section": "security", "controls": ["KVKK/GDPR veri minimizasyonu", "PCI DSS SAQ-A hedefi", "saklama politikası"]},
    "frontend": {"section": "frontend", "components": ["PaymentForm", "SavedCards", "PaymentStatus", "RefundPanel"]},
    "ux": {"section": "frontend", "flows": ["kart ekleme", "ödeme onayı", "başarısız ödeme kurtarma", "iade bilgilendirme"]},
    "mobile": {"section": "frontend", "items": ["mobil cüzdan deep-link", "3DS webview dönüşü", "düşük bant genişliği durumu"]},
    "qa": {"section": "tests", "tests": ["happy path", "3DS failure", "provider timeout", "duplicate idempotency key", "partial refund"]},
    "test_automation": {"section": "tests", "automation": ["contract tests", "fake gateway integration suite", "webhook replay tests"]},
    "performance": {"section": "tests", "checks": ["p95 ödeme başlatma < 500ms", "webhook tüketimi backpressure", "adapter circuit breaker"]},
    "deployment": {"section": "deployment", "items": ["containerized API", "separate worker", "secret manager env injection", "blue-green release"]},
    "reliability": {"section": "deployment", "items": ["queue retry with DLQ", "provider failover policy", "runbook for stuck payments"]},
    "observability": {"section": "deployment", "signals": ["payment_success_rate", "provider_latency_ms", "webhook_signature_failures", "refund_error_rate"]},
    "privacy": {"section": "security", "controls": ["PAN saklama yok", "maskelenmiş kart son dört hane", "silme talepleri için veri haritası"]},
    "code_review": {"section": "risk_register", "risks": ["adapter arayüzü sızıntısı", "eksik transactional boundary", "yetersiz negatif test"]},
    "refactoring": {"section": "backend", "items": ["payment state machine'i izole et", "provider SDK bağımlılığını port/adapter arkasına al"]},
    "documentation": {"section": "docs", "items": ["API kullanım örnekleri", "webhook doğrulama rehberi", "operasyon runbook"]},
    "release": {"section": "deployment", "items": ["feature flag", "pilot merchant rollout", "rollback checklist"]},
    "risk_register": {"section": "risk_register", "risks": ["provider outage", "chargeback artışı", "webhook replay saldırısı", "yanlış iade mutabakatı"]},
    "integration": {"section": "architecture", "items": ["order-service callback", "ledger reconciliation", "notification-service events"]},
    "localization": {"section": "frontend", "items": ["TRY para formatı", "Türkçe hata mesajları", "çoklu para birimi metinleri"]},
    "accessibility": {"section": "frontend", "items": ["WCAG 2.2 AA form etiketleri", "klavye ile 3DS dönüşü", "ekran okuyucu hata özetleri"]},
    "cost_controls": {"section": "risk_register", "risks": ["aşırı webhook tekrar maliyeti", "yüksek fraud kontrol API maliyeti"], "controls": ["quota", "batch reconciliation"]},
    "final_integration": {"section": "final", "items": ["Postman özetlerini tek teslimata dönüştür", "çakışmaları kaynak rolüne göre işaretle"]},
}


def build_output(package: dict[str, Any], provider: dict[str, Any], sandbox_root: Path) -> dict[str, Any]:
    role = package["role"]
    role_payload = ROLE_PAYLOADS.get(role, {"section": role, "items": [f"{role} için bağımsız çıktı"]})
    objective = package.get("objective", "")
    context_keys = sorted(package.get("minimal_context", {}).keys())
    artifact = {
        "agent_id": package["agent_id"],
        "role": role,
        "objective": objective,
        "used_context_keys": context_keys,
        "provider": {"provider": provider["provider"], "model": provider["model"], "api_key_env": provider["api_key_env"]},
        "result": role_payload,
        "sandbox_only": True,
    }
    artifact_path = sandbox_root / "artifact.json"
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "task_id": package["task_id"],
        "correlation_id": package["correlation_id"],
        "agent_id": package["agent_id"],
        "role": role,
        "status": "succeeded",
        "summary": f"{package['agent_id']} ({role}) bağımsız sandbox içinde çıktı üretti.",
        "data": role_payload | {"used_context_keys": context_keys, "provider_model": provider["model"]},
        "errors": [],
        "artifacts": {"artifact": str(artifact_path)},
        "sandbox_path": str(sandbox_root),
        "attempt": package.get("attempt", 1),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    package_path = Path(args.package).resolve()
    output_path = Path(args.output).resolve()
    sandbox_root = package_path.parent.resolve()
    if sandbox_root not in output_path.parents:
        raise SystemExit("output path must stay inside sandbox")
    package = json.loads(package_path.read_text(encoding="utf-8"))
    provider = json.loads(args.provider)
    if package.get("minimal_context", {}).get("simulate_hang"):
        time.sleep(float(os.getenv("AGENT_SIMULATED_HANG_SECONDS", "60")))
    if package.get("minimal_context", {}).get("simulate_failure"):
        raise RuntimeError("simulated contained agent failure")
    result = build_output(package, provider, sandbox_root)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
