# Home Assistant Adapter

Die laut [ADR-0002](../../docs/architecture/adr-0002-home-assistant-backbone.md) einzige produktive Integrationsgrenze zwischen SystemONE und Home Assistant (und damit Zigbee/Matter/Shelly/Hue).

## Grenzen

- Wird ausschließlich von `apps/customer-backend` verwendet, nie direkt vom Client.
- Enthält keine Kunden-PII, keine HQ-Secrets.
- Herstellerspezifische Credentials/Daten verlassen diese Schicht nicht in Richtung öffentlicher API.

## Status

Nur Interface-Skeleton (`HomeAssistantAdapter`, abstrakte Basisklasse) aus `S1V2-01-002`. Reale Anbindung an eine Home-Assistant-Instanz folgt in `S1V2-02-016` ff.

## Entwicklung

```bash
cd services/home-assistant-adapter
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```
