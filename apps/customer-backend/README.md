# SystemONE Customer Backend

FastAPI-Backend, das lokal auf jedem Kundensystem (Pi/Mini/Server/Rack) läuft. Siehe [ADR-0002](../../docs/architecture/adr-0002-home-assistant-backbone.md) für die Zielarchitektur und [`docs/product-manifest.md`](../../docs/product-manifest.md) für die Produktregeln.

## Grenzen (verbindlich)

- **Local-first:** Muss ohne Laufzeitverbindung zu `apps/hq-backend` vollständig funktionieren.
- **Keine HQ-Secrets/Kundendaten anderer Kunden:** Dieses Paket importiert nichts aus `apps/hq-backend` oder `services/provisioning`.
- Geräteintegration ausschließlich über `services/home-assistant-adapter`, nie direkt gegen Hersteller-APIs.
- Gemeinsame Datenverträge kommen aus `packages/shared-contracts`, nicht aus Kopien.

## Entwicklung

```bash
cd apps/customer-backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

## Status

Skeleton aus `S1V2-01-002` (Repository-Strukturierung). Domain Layer, PostgreSQL-Anbindung, Auth/Rollen, MQTT-Eventbus etc. folgen in `S1V2-02-*`.
