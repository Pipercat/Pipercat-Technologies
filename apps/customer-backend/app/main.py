"""SystemONE customer-backend entry point.

Local FastAPI service for a single customer system (Pi/Mini/Server/Rack).
Must remain fully functional without any runtime connection to SystemONE HQ
(local-first, see docs/product-manifest.md section 2).
"""

from fastapi import FastAPI

app = FastAPI(
    title="SystemONE Customer Backend",
    version="0.1.0",
)


@app.get("/api/v1/health")
def health() -> dict:
    """Liveness/readiness probe. Contract shape follows the success/data/error
    envelope defined in docs/architecture/adr-0002-home-assistant-backbone.md
    once the full API v1 contract lands in S1V2-01-004."""
    return {"success": True, "data": {"status": "ok"}, "error": None}
