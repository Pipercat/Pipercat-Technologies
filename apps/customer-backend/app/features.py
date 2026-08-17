"""FastAPI dependency that enforces the S1V2-01-003 feature matrix."""

from fastapi import Depends, HTTPException

from .device_identity import get_product_class
from .product_class import Feature, ProductClass, is_feature_enabled


def require_feature(feature: Feature):
    """Returns a FastAPI dependency that 403s with a structured error unless
    the current device's product class supports `feature`."""

    def _dependency(product_class: ProductClass = Depends(get_product_class)) -> ProductClass:
        if not is_feature_enabled(product_class, feature):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FEATURE_NOT_AVAILABLE",
                    "message": f"'{feature.value}' is not available on product class '{product_class.value}'",
                },
            )
        return product_class

    return _dependency
