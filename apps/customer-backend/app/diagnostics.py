"""Diagnostic export for a household's integrations (S1V2-02-013 DoD:
"Tests, dass Diagnoseexporte Testsecrets nicht enthalten").

DEC-118: a support-facing diagnostic bundle must never contain secret
material. `export_household_integrations()` deliberately reads only
`Integration` rows (id/type/status/config - already documented as
non-secret, see db/models.py::Integration) and never touches
`IntegrationSecret`/`app.secret_store` at all, so there is no code path
by which a secret value - encrypted or not - could end up in the
exported structure. `config` values also pass through the existing
generic redaction filter (app/observability.py::redact) as a second,
independent safety net in case an integration's non-secret config ever
contains a secret-shaped string by operator mistake.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from .db.models import Integration
from .observability import redact


def export_household_integrations(session_factory: sessionmaker, *, household_id: str) -> list[dict]:
    with session_factory() as session:
        integrations = session.scalars(
            select(Integration).where(
                Integration.household_id == uuid.UUID(household_id), Integration.deleted_at.is_(None)
            )
        ).all()
        return [
            {
                "id": str(integration.id),
                "type": integration.type,
                "status": integration.status,
                "config": _redact_config(integration.config),
            }
            for integration in integrations
        ]


def _redact_config(config: dict) -> dict:
    return {key: redact(value) if isinstance(value, str) else value for key, value in config.items()}
