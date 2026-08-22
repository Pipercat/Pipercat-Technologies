"""SystemONE customer-backend entry point.

Local FastAPI service for a single customer system (Pi/Mini/Server/Rack).
Must remain fully functional without any runtime connection to SystemONE HQ
(local-first, see docs/product-manifest.md section 2).

API v1 contract (envelope, errors, events, pagination, idempotency,
concurrency) is defined in docs/architecture/api-contract.md (S1V2-01-004).
"""

import logging

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .correlation import CorrelationIdMiddleware, get_correlation_id
from .device_compatibility import lookup_compatibility
from .device_identity import (
    DeviceLicenseInvalidError,
    DeviceLicenseNotConfiguredError,
    ProductClassUnknownError,
    get_product_class,
    get_verified_device_identity,
)
from .domain import CapabilityNotSupportedError, DeviceNotFoundError, DeviceService, DomainDevice
from .domain.capabilities import CapabilityCommand, CapabilityState
from .domain.simulation_adapter import SimulationDeviceAdapter
from .envelope import ApiError, Envelope, ok
from .events import DeviceStateEvent, event_bus
from .features import require_feature
from .idempotency import idempotency_store
from .observability import configure_logging, metrics
from .pagination import Page, paginate
from .product_class import Feature, ProductClass, enabled_features

configure_logging(component="customer-backend")
logger = logging.getLogger("systemone.customer_backend")

app = FastAPI(
    title="SystemONE Customer Backend",
    version="0.1.0",
)
app.add_middleware(CorrelationIdMiddleware)

metrics.register_gauge("events_in_memory", lambda: len(event_bus._events))  # type: ignore[attr-defined]
metrics.register_gauge("idempotency_keys_cached", lambda: len(idempotency_store._store))  # type: ignore[attr-defined]

# Simulation-backed for now (S1V2-02-002). Swapped for a HomeAssistantAdapter-
# backed DeviceService in S1V2-02-016 ff. — the /api/v1/devices* routes below
# do not change when that happens, only this wiring does.
_device_adapter = SimulationDeviceAdapter()
_device_adapter.seed_lamp(name="Wohnzimmerlampe (Simulation)")
device_service = DeviceService(_device_adapter)


# --- error envelope -----------------------------------------------------


@app.exception_handler(HTTPException)
async def http_exception_envelope(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        error = ApiError(correlationId=get_correlation_id(request), **detail)
    else:
        error = ApiError(code="ERROR", message=str(detail), correlationId=get_correlation_id(request))
    return JSONResponse(
        status_code=exc.status_code,
        content=Envelope(success=False, data=None, error=error).model_dump(),
    )


@app.exception_handler(DeviceNotFoundError)
async def device_not_found_envelope(request: Request, exc: DeviceNotFoundError) -> JSONResponse:
    error = ApiError(code="DEVICE_NOT_FOUND", message=str(exc), correlationId=get_correlation_id(request))
    return JSONResponse(status_code=404, content=Envelope(success=False, data=None, error=error).model_dump())


@app.exception_handler(CapabilityNotSupportedError)
async def capability_not_supported_envelope(request: Request, exc: CapabilityNotSupportedError) -> JSONResponse:
    error = ApiError(
        code="CAPABILITY_NOT_SUPPORTED", message=str(exc), correlationId=get_correlation_id(request)
    )
    return JSONResponse(status_code=400, content=Envelope(success=False, data=None, error=error).model_dump())


@app.exception_handler(ProductClassUnknownError)
async def product_class_unknown_envelope(request: Request, exc: ProductClassUnknownError) -> JSONResponse:
    # Fail closed: an unconfigured/unknown product class is a hard 500, never
    # a silent default to the most permissive class. Logged as a warning —
    # this is an operator/provisioning problem worth surfacing, not just a
    # client-visible error.
    logger.warning("product_class_unknown")
    error = ApiError(code="PRODUCT_CLASS_UNKNOWN", message=str(exc), correlationId=get_correlation_id(request))
    return JSONResponse(status_code=500, content=Envelope(success=False, data=None, error=error).model_dump())


@app.exception_handler(DeviceLicenseNotConfiguredError)
async def device_license_not_configured_envelope(request: Request, exc: DeviceLicenseNotConfiguredError) -> JSONResponse:
    error = ApiError(code="DEVICE_LICENSE_NOT_CONFIGURED", message=str(exc), correlationId=get_correlation_id(request))
    return JSONResponse(status_code=500, content=Envelope(success=False, data=None, error=error).model_dump())


@app.exception_handler(DeviceLicenseInvalidError)
async def device_license_invalid_envelope(request: Request, exc: DeviceLicenseInvalidError) -> JSONResponse:
    # Fail closed, same reasoning as ProductClassUnknownError: an invalid
    # signature is always a hard error, never treated as "no license".
    logger.warning("device_license_invalid")
    error = ApiError(code="DEVICE_LICENSE_INVALID", message=str(exc), correlationId=get_correlation_id(request))
    return JSONResponse(status_code=500, content=Envelope(success=False, data=None, error=error).model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_envelope(request: Request, exc: Exception) -> JSONResponse:
    # Never leak exception internals (may contain secrets/PII/stack frames)
    # to the client. Full detail goes to the server log only, keyed by the
    # same correlation ID the client sees, per docs/architecture/api-contract.md.
    correlation_id = get_correlation_id(request)
    # correlationId/component are attached automatically by
    # CorrelationAndRedactionFilter (app/observability.py); the log message
    # itself must stay generic — the real exception type is enough for
    # server-side triage, its message might contain request data.
    logger.error("unhandled_exception type=%s", type(exc).__name__)
    error = ApiError(
        code="INTERNAL_ERROR",
        message="Ein unerwarteter Fehler ist aufgetreten.",
        correlationId=correlation_id,
    )
    return JSONResponse(status_code=500, content=Envelope(success=False, data=None, error=error).model_dump())


# --- health / features ---------------------------------------------------


class HealthData(BaseModel):
    status: str


class FeaturesData(BaseModel):
    productClass: str
    features: list[str]


class StatusData(BaseModel):
    status: str


@app.get("/api/v1/health", response_model=Envelope[HealthData])
def health() -> Envelope[HealthData]:
    return ok(HealthData(status="ok"))


@app.get("/api/v1/health/live", response_model=Envelope[HealthData])
def health_live() -> Envelope[HealthData]:
    """Liveness: is the process able to handle requests at all. Must never
    depend on external systems (DB/MQTT/Home Assistant) — a dependency
    outage must show up as 'not ready', not 'not alive'."""
    return ok(HealthData(status="ok"))


@app.get("/api/v1/health/ready", response_model=Envelope[HealthData])
def health_ready() -> Envelope[HealthData]:
    """Readiness: process is alive AND its dependencies are usable. No real
    dependencies (PostgreSQL/MQTT/Home Assistant) exist yet (S1V2-02-*), so
    this currently only reports the always-available in-memory subsystems.
    Extend this function's checks — not a new endpoint — as each real
    dependency lands."""
    return ok(HealthData(status="ok"))


class MetricsData(BaseModel):
    values: dict[str, int | float | str]


@app.get("/api/v1/metrics", response_model=Envelope[MetricsData])
def metrics_snapshot() -> Envelope[MetricsData]:
    """JSON metrics snapshot (see docs/architecture/observability.md for why
    not Prometheus text format yet). Subsystems register their own gauges
    via app.observability.metrics.register_gauge(); this endpoint has no
    hardcoded knowledge of DB/MQTT/HA/backup — those register themselves
    once they exist."""
    return ok(MetricsData(values=metrics.snapshot()))


@app.get("/api/v1/features", response_model=Envelope[FeaturesData])
def list_features(product_class: ProductClass = Depends(get_product_class)) -> Envelope[FeaturesData]:
    """Read-only — the product class itself is never settable through the API."""
    features = sorted(f.value for f in enabled_features(product_class))
    return ok(FeaturesData(productClass=product_class.value, features=features))


class DeviceIdentityData(BaseModel):
    deviceId: str
    serialNumber: str
    productClass: str
    issuedAt: str


@app.get("/api/v1/device/identity", response_model=Envelope[DeviceIdentityData])
def device_identity() -> Envelope[DeviceIdentityData]:
    """Verifies the signed device license offline (S1V2-02-027) and
    returns the identity it vouches for. No network call, no HQ
    dependency (docs/product-manifest.md §2)."""
    identity = get_verified_device_identity()
    return ok(
        DeviceIdentityData(
            deviceId=identity.device_id,
            serialNumber=identity.serial_number,
            productClass=identity.product_class.value,
            issuedAt=identity.issued_at.isoformat(),
        )
    )


@app.get(
    "/api/v1/nas/status",
    response_model=Envelope[StatusData],
    dependencies=[Depends(require_feature(Feature.NAS))],
)
def nas_status() -> Envelope[StatusData]:
    """Example feature-gated endpoint; the real NAS module is its own task."""
    return ok(StatusData(status="not-implemented-yet"))


@app.get(
    "/api/v1/local-ai/status",
    response_model=Envelope[StatusData],
    dependencies=[Depends(require_feature(Feature.LOCAL_AI))],
)
def local_ai_status() -> Envelope[StatusData]:
    """Example feature-gated endpoint (Server/Rack only)."""
    return ok(StatusData(status="not-implemented-yet"))


# --- devices (S1V2-02-002 domain layer) ------------------------------------


@app.get("/api/v1/devices", response_model=Envelope[list[DomainDevice]])
async def list_devices() -> Envelope[list[DomainDevice]]:
    """Lists devices through DeviceService — works identically once this is
    backed by real hardware via HomeAssistantAdapter (S1V2-02-016 ff.)."""
    return ok(await device_service.list_devices())


@app.post("/api/v1/devices/{device_id}/commands", response_model=Envelope[CapabilityState])
async def send_device_command(device_id: str, command: CapabilityCommand) -> Envelope[CapabilityState]:
    new_state = await device_service.send_command(device_id, command)
    return ok(new_state)


# --- device compatibility (S1V2-02-026) ------------------------------------


class DeviceCompatibilityData(BaseModel):
    manufacturer: str
    model: str
    integrationType: str
    capabilities: list[str]
    status: str
    disclaimer: str | None


@app.get("/api/v1/device-compatibility", response_model=Envelope[DeviceCompatibilityData])
def device_compatibility(
    manufacturer: str, model: str, integration_type: str = Query(alias="integrationType")
) -> Envelope[DeviceCompatibilityData]:
    """Read-only, no permission required - this is public product
    information (the same for every customer), not household data. See
    docs/architecture/device-compatibility.md for why the registry itself
    is static/code-shipped rather than a database table."""
    profile = lookup_compatibility(manufacturer, model, integration_type)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "DEVICE_COMPATIBILITY_NOT_FOUND",
                "message": f"No compatibility profile for {manufacturer} {model} ({integration_type}).",
            },
        )
    return ok(
        DeviceCompatibilityData(
            manufacturer=profile.manufacturer,
            model=profile.model,
            integrationType=profile.integration_type,
            capabilities=profile.capabilities,
            status=profile.status.value,
            disclaimer=profile.disclaimer,
        )
    )


# --- events / pagination --------------------------------------------------


@app.get("/api/v1/events/recent", response_model=Envelope[Page[DeviceStateEvent]])
async def recent_events(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> Envelope[Page[DeviceStateEvent]]:
    """Cursor-paginated recent events, newest first. See
    docs/architecture/api-contract.md for the pagination convention."""
    events = await event_bus.recent(limit=500)
    return ok(paginate(events, limit=limit, cursor=cursor))


# --- idempotent write + optimistic concurrency demo -----------------------

_system_state = {"version": 1}


class RestartRequest(BaseModel):
    expectedVersion: int


class SystemStateData(BaseModel):
    version: int


@app.post("/api/v1/system/restart", response_model=Envelope[SystemStateData])
async def restart_system(
    body: RestartRequest,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> Envelope[SystemStateData]:
    """Demonstrates the idempotency + optimistic-concurrency convention for
    critical write operations (S1V2-01-004). A real restart implementation
    is a later, separate task."""
    cached = idempotency_store.get(idempotency_key)
    if cached is not None:
        return cached

    if body.expectedVersion != _system_state["version"]:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "VERSION_CONFLICT",
                "message": "expectedVersion does not match the current system state version.",
            },
        )

    _system_state["version"] += 1
    await event_bus.publish(
        DeviceStateEvent(
            type="system.restart_requested",
            correlationId=get_correlation_id(request),
            payload={"version": _system_state["version"]},
        )
    )
    response = ok(SystemStateData(version=_system_state["version"]))
    idempotency_store.set(idempotency_key, response)
    return response
