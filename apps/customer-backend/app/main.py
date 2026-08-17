"""SystemONE customer-backend entry point.

Local FastAPI service for a single customer system (Pi/Mini/Server/Rack).
Must remain fully functional without any runtime connection to SystemONE HQ
(local-first, see docs/product-manifest.md section 2).
"""

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .device_identity import ProductClassUnknownError, get_product_class
from .features import require_feature
from .product_class import Feature, ProductClass, enabled_features

app = FastAPI(
    title="SystemONE Customer Backend",
    version="0.1.0",
)


@app.exception_handler(HTTPException)
async def http_exception_envelope(_: Request, exc: HTTPException) -> JSONResponse:
    """Wraps every HTTPException in the success/data/error envelope that
    packages/shared-contracts/openapi/systemone-api-v1.yaml defines, instead
    of FastAPI's default {"detail": ...} shape."""
    detail = exc.detail
    error = detail if isinstance(detail, dict) else {"code": "ERROR", "message": str(detail)}
    return JSONResponse(status_code=exc.status_code, content={"success": False, "data": None, "error": error})


@app.exception_handler(ProductClassUnknownError)
async def product_class_unknown_envelope(_: Request, exc: ProductClassUnknownError) -> JSONResponse:
    # Fail closed: an unconfigured/unknown product class is a hard 500, never
    # a silent default to the most permissive class.
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "error": {"code": "PRODUCT_CLASS_UNKNOWN", "message": str(exc)},
        },
    )


@app.get("/api/v1/health")
def health() -> dict:
    """Liveness/readiness probe. Contract shape follows the success/data/error
    envelope defined in docs/architecture/adr-0002-home-assistant-backbone.md
    once the full API v1 contract lands in S1V2-01-004."""
    return {"success": True, "data": {"status": "ok"}, "error": None}


@app.get("/api/v1/features")
def list_features(product_class: ProductClass = Depends(get_product_class)) -> dict:
    """Returns the feature set enabled for this device's product class
    (S1V2-01-003). Read-only — the product class itself is never settable
    through the API."""
    features = sorted(f.value for f in enabled_features(product_class))
    return {
        "success": True,
        "data": {"productClass": product_class.value, "features": features},
        "error": None,
    }


@app.get("/api/v1/nas/status", dependencies=[Depends(require_feature(Feature.NAS))])
def nas_status() -> dict:
    """Example feature-gated endpoint demonstrating the S1V2-01-003
    enforcement mechanism; the real NAS module lands with its own task."""
    return {"success": True, "data": {"status": "not-implemented-yet"}, "error": None}


@app.get("/api/v1/local-ai/status", dependencies=[Depends(require_feature(Feature.LOCAL_AI))])
def local_ai_status() -> dict:
    """Example feature-gated endpoint (Server/Rack only)."""
    return {"success": True, "data": {"status": "not-implemented-yet"}, "error": None}
