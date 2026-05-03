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


def _find_context_value(context: Any, key: str, default: Any = None) -> Any:
    if isinstance(context, dict):
        if key in context:
            return context[key]
        for value in context.values():
            found = _find_context_value(value, key, None)
            if found is not None:
                return found
    if isinstance(context, list):
        for item in context:
            found = _find_context_value(item, key, None)
            if found is not None:
                return found
    return default


def _prompt_title(prompt: str, target: str) -> str:
    words = [word.strip(".,;:!?()[]{}\"'") for word in prompt.split() if word.strip()]
    if not words:
        return f"Yeni {target} projesi"
    title = " ".join(words[:6])
    return title[:80]


def _frontend_files(prompt: str, target: str, style: str | None, features: list[str]) -> list[dict[str, str]]:
    title = _prompt_title(prompt, target)
    feature_text = ", ".join(features) if features else "ana içerik bölümleri"
    if target == "web_site":
        return [
            {
                "path": "index.html",
                "purpose": "Statik açılış sayfası iskeleti",
                "snippet": f"<main><section class=\"hero\"><h1>{title}</h1><p>{feature_text}</p></section></main>",
            },
            {
                "path": "src/styles.css",
                "purpose": "Mobil uyumlu görsel stil",
                "snippet": f":root {{ --accent: #0f766e; }} body {{ font-family: Inter, sans-serif; }} /* style: {style or 'modern'} */",
            },
        ]
    return [
        {
            "path": "src/App.tsx",
            "purpose": "React uygulama kabuğu ve sayfa akışları",
            "snippet": f"export default function App() {{ return <main><h1>{title}</h1><FeatureList /></main>; }}",
        },
        {
            "path": "src/styles.css",
            "purpose": "Responsive layout ve tema token'ları",
            "snippet": f".app {{ min-height: 100vh; }} .card {{ border-radius: 24px; }} /* {style or 'clean'} */",
        },
    ]


def _backend_files(target: str, features: list[str]) -> list[dict[str, str]]:
    if target == "web_site":
        return [
            {
                "path": "server/README.md",
                "purpose": "Website için backend opsiyonel notu",
                "snippet": "Backend gerekli değil; form gönderimi için serverless endpoint opsiyonel tutuldu.",
            }
        ]
    endpoints = [feature.lower().replace(" ", "-") for feature in features] or ["items"]
    return [
        {
            "path": "app/main.py",
            "purpose": "FastAPI servis girişi",
            "snippet": f"from fastapi import FastAPI\napp = FastAPI()\n@app.get('/health')\ndef health(): return {{'status': 'ok', 'features': {endpoints!r}}}",
        },
        {
            "path": "app/models.py",
            "purpose": "Pydantic request/response modelleri",
            "snippet": "from pydantic import BaseModel\nclass CreateItemRequest(BaseModel):\n    name: str",
        },
    ]


def build_prompt_to_app_payload(role: str, context: dict[str, Any]) -> dict[str, Any]:
    prompt_value = _find_context_value(context, "prompt", None) or _find_context_value(context, "prompt_summary", None)
    prompt = str(prompt_value or "Kullanıcı promptundan uygulama üret")
    target = str(_find_context_value(context, "target", "web_site"))
    style_value = _find_context_value(context, "style", None)
    style = str(style_value) if style_value else None
    features_value = _find_context_value(context, "features", [])
    features = [str(item) for item in features_value] if isinstance(features_value, list) else []
    is_website = target == "web_site"
    title = _prompt_title(prompt, target)
    target_label = {
        "web_site": "statik/marketing web sitesi",
        "web_app": "etkileşimli web uygulaması",
        "api": "API servisi",
        "full_stack": "full-stack uygulama",
    }.get(target, target)
    payloads: dict[str, dict[str, Any]] = {
        "requirements": {
            "section": "product_spec",
            "prompt_summary": title,
            "target": target,
            "requirements": [
                f"{target_label} kullanıcı promptundaki ana amacı karşılamalı",
                "Mobil uyum ve hızlı ilk yükleme varsayılan kabul kriteridir",
                "İçerik bölümleri ve formlar prompt/features listesinden türetilir",
            ],
            "features": features or ["hero", "içerik bölümleri", "iletişim/CTA"],
        },
        "product_scope": {
            "section": "product_spec",
            "mvp": ["tek tutarlı görsel dil", "net navigasyon", "ölçülebilir CTA", "yayına hazır dosya planı"],
            "success_metrics": ["Lighthouse performance >= 90", "form tamamlanma oranı", "mobil kullanılabilirlik"],
        },
        "architecture": {
            "section": "implementation_steps",
            "technical_direction": "Vite/React frontend" if target in {"web_app", "full_stack"} else "semantik HTML + CSS + küçük JS",
            "components": ["presentation layer", "routing/content map", "form handling", "deployment pipeline"],
            "backend_position": "opsiyonel/serverless" if is_website else "FastAPI servis katmanı",
        },
        "database": {
            "section": "data_model",
            "required": target in {"web_app", "api", "full_stack"},
            "plan": "Website-only hedefte kalıcı veritabanı gerekli değil; rezervasyon/iletişim formları için serverless veya üçüncü parti form inbox opsiyonel." if is_website else "PostgreSQL üzerinde kullanıcı, içerik ve form/işlem tabloları önerilir.",
            "entities": [] if is_website else ["User", "ProjectItem", "Submission", "AuditEvent"],
        },
        "api_contract": {
            "section": "api_contract",
            "required": target in {"api", "full_stack", "web_app"},
            "endpoints": ["POST /api/contact", "POST /api/reservations"] if is_website else ["GET /health", "GET /api/items", "POST /api/items", "POST /api/auth/session"],
            "note": "Website hedefinde API opsiyoneldir; form submit için progressive enhancement olarak tasarlanır." if is_website else "API sözleşmesi frontend/backend bağımsız geliştirme için sabit tutulur.",
        },
        "domain_model": {
            "section": "information_architecture",
            "site_map": ["Ana sayfa", "Özellik/menü bölümü", "Form", "İletişim", "Yasal/footer"],
            "content_model": ["Hero", "FeatureCard", "CTA", "FormSubmission", "ContactInfo"],
        },
        "backend": {
            "section": "backend_code_plan",
            "required": target in {"api", "full_stack"},
            "modules": ["health endpoint", "form validation", "persistence adapter", "email/notification adapter"] if not is_website else ["opsiyonel serverless form handler", "spam koruması", "email yönlendirme"],
            "generated_files": _backend_files(target, features),
        },
        "payment_integration": {
            "section": "backend_code_plan",
            "required": "ödeme" in prompt.lower() or "payment" in prompt.lower(),
            "plan": "Prompt ödeme istemiyorsa ödeme entegrasyonu eklenmez; ileride Stripe/Iyzico adapter portu açılabilir.",
        },
        "security": {
            "section": "security_privacy",
            "controls": ["input validation", "CSRF/spam koruması", "secret değerleri env üzerinden", "güvenli response header'ları"],
            "website_note": "Statik website için saldırı yüzeyi form endpoint'i ve üçüncü parti scriptlerle sınırlı tutulur." if is_website else "Auth, rate limit ve authorization katmanları zorunludur.",
        },
        "compliance": {"section": "security_privacy", "controls": ["KVKK/GDPR aydınlatma metni", "çerez banner gereksinimi değerlendirmesi", "minimum veri toplama"]},
        "frontend": {
            "section": "frontend_code_plan",
            "components": ["Hero", "FeatureGrid", "ResponsiveNav", "ContactOrReservationForm", "Footer"],
            "state": "minimal client state" if is_website else "route, auth/session and server cache state",
            "generated_files": _frontend_files(prompt, target, style, features),
        },
        "ux": {
            "section": "ui_design",
            "style": style or "modern, temiz, mobil öncelikli",
            "flows": ["ilk bakışta değer önerisi", "bölüm keşfi", "form doldurma", "başarılı gönderim geri bildirimi"],
            "layout": ["sticky nav", "hero CTA", "kart tabanlı içerik", "tek kolon mobil form"],
        },
        "mobile": {"section": "ui_design", "items": ["360px genişlikte tek kolon", "dokunmatik hedefler >= 44px", "lazy-loaded media", "offline-friendly static shell"]},
        "qa": {"section": "test_plan", "tests": ["prompt-derived content smoke test", "responsive viewport checks", "form validation", "accessibility scan", "404/empty state"]},
        "test_automation": {"section": "test_plan", "automation": ["Playwright homepage/form e2e", "Vitest component tests", "API contract tests" if not is_website else "static link checker"]},
        "performance": {"section": "test_plan", "budgets": ["LCP < 2.5s", "JS bundle < 170KB for website", "image lazy loading", "API p95 < 300ms when backend exists"]},
        "deployment": {"section": "deployment_plan", "items": ["static hosting on Vercel/Netlify" if is_website else "containerized API + static frontend", "preview deploy per change", "environment-specific config"]},
        "reliability": {"section": "deployment_plan", "items": ["form submission retry", "health check" if not is_website else "static uptime check", "rollback to previous deployment"]},
        "observability": {"section": "deployment_plan", "signals": ["page_view", "form_submit_success", "form_submit_error", "web_vitals"]},
        "privacy": {"section": "security_privacy", "controls": ["PII minimization", "form retention policy", "analytics anonymization", "delete/export request path"]},
        "code_review": {"section": "risk_register", "risks": ["prompt kapsamının fazla genişlemesi", "form validasyonunun atlanması", "mobil kırılmalar", "gereksiz backend karmaşıklığı"]},
        "refactoring": {"section": "implementation_steps", "items": ["UI bileşenlerini küçük parçalara ayır", "form logic'i ayrı module taşı", "content config'i JSON/TS sabitine çıkar"]},
        "documentation": {"section": "implementation_steps", "docs": ["README setup", "deployment notes", "content editing guide", "API usage" if not is_website else "form provider setup"]},
        "release": {"section": "implementation_steps", "checklist": ["preview approval", "Lighthouse + a11y pass", "env vars verified", "DNS/caching configured"]},
        "risk_register": {"section": "risk_register", "risks": ["prompt belirsizliği", "üçüncü parti form servisi kesintisi", "SEO metadata eksikleri", "KVKK metni eksikliği"]},
        "integration": {"section": "api_contract", "items": ["form provider integration" if is_website else "frontend/backend API boundary", "email notification", "analytics event mapping"]},
        "localization": {"section": "ui_design", "items": ["Türkçe varsayılan metinler", "çok dilli içerik dosyası opsiyonu", "locale-aware date/phone formatting"]},
        "accessibility": {"section": "ui_design", "items": ["WCAG 2.2 AA renk kontrastı", "semantik landmark'lar", "label/error aria bağlantıları", "klavye navigasyonu"]},
        "cost_controls": {"section": "deployment_plan", "controls": ["static hosting free tier", "serverless form quota", "image optimization", "observability sampling"]},
        "final_integration": {
            "section": "generated_files",
            "project_blueprint": title,
            "implementation_steps": ["İçerik ve IA'yı sabitle", "Frontend dosyalarını üret", "Opsiyonel API/form handler ekle", "Testleri çalıştır", "Preview deploy al"],
            "generated_files": _frontend_files(prompt, target, style, features) + _backend_files(target, features),
        },
    }
    return payloads.get(role, {"section": "implementation_steps", "items": [f"{role} için prompt-to-app çıktısı"], "target": target})


def build_output(package: dict[str, Any], provider: dict[str, Any], sandbox_root: Path) -> dict[str, Any]:
    role = package["role"]
    minimal_context = package.get("minimal_context", {})
    if _find_context_value(minimal_context, "generation_mode") == "prompt_to_app":
        role_payload = build_prompt_to_app_payload(role, minimal_context)
    else:
        role_payload = ROLE_PAYLOADS.get(role, {"section": role, "items": [f"{role} için bağımsız çıktı"]})
    objective = package.get("objective", "")
    context_keys = sorted(minimal_context.keys())
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
