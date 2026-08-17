"""SystemONE HQ backend entry point.

Internal Pipercat company platform. Never a runtime dependency for a
customer system's core functions (see docs/product-manifest.md section 2/7).
Owns its own secret system, strictly separate from customer-backend secrets
(see ADR-0002, "Trust Boundaries und Datenflüsse").
"""

from fastapi import FastAPI

app = FastAPI(
    title="SystemONE HQ Backend",
    version="0.1.0",
)


@app.get("/api/v1/health")
def health() -> dict:
    return {"success": True, "data": {"status": "ok"}, "error": None}
