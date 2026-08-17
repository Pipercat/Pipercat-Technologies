"""Product-class / feature-flag matrix for SystemONE Pi/Mini/Server/Rack.

Source: Notion DEC-14, DEC-18 and the current product matrix
(docs/product-manifest.md, section 1). Any new feature or product line
change starts here — this module is the single source of truth the API
layer enforces against (S1V2-01-003).
"""

from enum import Enum


class ProductClass(str, Enum):
    PI = "pi"
    MINI = "mini"
    SERVER = "server"
    RACK = "rack"


class Feature(str, Enum):
    SMART_HOME = "smart_home"
    PI_HOLE = "pi_hole"
    NAS = "nas"
    CAMERA_LIVE = "camera_live"
    CAMERA_STORAGE = "camera_storage"
    LOCAL_AI = "local_ai"
    CLOUD_BACKUP = "cloud_backup"


# Verbindliche Matrix, siehe Notion-Aufgabe S1V2-01-003 "Verbindliche Matrix".
FEATURE_MATRIX: dict[ProductClass, frozenset[Feature]] = {
    ProductClass.PI: frozenset(
        {
            Feature.SMART_HOME,
            Feature.PI_HOLE,
            Feature.CAMERA_LIVE,  # "zunächst Live/limitiert", kein CAMERA_STORAGE
            Feature.CLOUD_BACKUP,  # optionales Cloud Backup auf allen Klassen möglich
        }
    ),
    ProductClass.MINI: frozenset(
        {
            Feature.SMART_HOME,
            Feature.PI_HOLE,
            Feature.NAS,
            Feature.CAMERA_LIVE,
            Feature.CAMERA_STORAGE,
            Feature.CLOUD_BACKUP,
        }
    ),
    ProductClass.SERVER: frozenset(
        {
            Feature.SMART_HOME,
            Feature.PI_HOLE,
            Feature.NAS,
            Feature.CAMERA_LIVE,
            Feature.CAMERA_STORAGE,
            Feature.LOCAL_AI,
            Feature.CLOUD_BACKUP,
        }
    ),
    ProductClass.RACK: frozenset(
        {
            Feature.SMART_HOME,
            Feature.PI_HOLE,
            Feature.NAS,
            Feature.CAMERA_LIVE,
            Feature.CAMERA_STORAGE,
            Feature.LOCAL_AI,
            Feature.CLOUD_BACKUP,
        }
    ),
}


def enabled_features(product_class: ProductClass) -> frozenset[Feature]:
    return FEATURE_MATRIX[product_class]


def is_feature_enabled(product_class: ProductClass, feature: Feature) -> bool:
    return feature in FEATURE_MATRIX[product_class]
