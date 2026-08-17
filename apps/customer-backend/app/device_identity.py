"""Server-side source of truth for this device's product class.

Deliberately NOT settable by any client request — the product class must
come from server-side provisioning configuration, never from client input
(S1V2-01-003: "Hardwareklasse aus Geräteidentität ableiten, nicht vom
Client frei setzen").

Today this reads an environment variable populated at image/provisioning
time (see infrastructure/docker-compose/.env.example). Once the signed
device identity/license lands (S1V2-02-027), this function's *implementation*
will read that instead — its public contract (a ProductClass, or a clear
failure) stays the same, so callers do not need to change.
"""

import os

from .product_class import ProductClass

_ENV_VAR = "SYSTEMONE_PRODUCT_CLASS"


class ProductClassUnknownError(RuntimeError):
    """Raised when the device's product class cannot be determined. The API
    layer must treat this as fail-closed (deny all feature-gated access),
    never default to the most permissive product class."""


def get_product_class() -> ProductClass:
    raw = os.environ.get(_ENV_VAR)
    if not raw:
        raise ProductClassUnknownError(
            f"{_ENV_VAR} is not set. Product class must be provisioned "
            "server-side; refusing to guess."
        )
    try:
        return ProductClass(raw)
    except ValueError as exc:
        raise ProductClassUnknownError(f"Unknown product class '{raw}'") from exc
