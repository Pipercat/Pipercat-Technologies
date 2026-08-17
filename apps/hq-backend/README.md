# SystemONE HQ Backend

FastAPI-Backend für SystemONE HQ, die zentrale interne Firmenplattform von Pipercat Technologies. Siehe [ADR-0002](../../docs/architecture/adr-0002-home-assistant-backbone.md) und [`docs/product-manifest.md`](../../docs/product-manifest.md) Abschnitt 7.

## Grenzen (verbindlich)

- **Mandantengetrennt:** Jeder Datenzugriff ist an Kunde/Projekt gebunden (`S1V2-03-003`).
- **Eigenes Secret-System**, getrennt von Kundenakten und von `apps/customer-backend`.
- Importiert nichts aus `apps/customer-backend`, das Kundeninstallationsdaten oder Kundensecrets enthält.
- Ist **keine Laufzeitabhängigkeit** eines Kundensystems für dessen Kernfunktionen.
- Module (Flash/Provisioning, Kundenverwaltung, Website-Integration, Updates, Remote-Vermittlung, optionales Cloud-Backup) bekommen eigene, klar geschnittene Router/Submodule statt eines unstrukturierten Monolithen.

## Entwicklung

```bash
cd apps/hq-backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

## Status

Skeleton aus `S1V2-01-002`. Fachliche Module folgen in Phase `03 SystemONE HQ`.
