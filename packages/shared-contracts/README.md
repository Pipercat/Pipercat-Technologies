# Shared Contracts

Gemeinsame API-/Event-Verträge und Modelle, die von mehreren SystemONE-Paketen mit **identischer Semantik** verwendet werden (siehe `S1V2-01-002`-Regel: „Gemeinsame Modelle nur bei identischer Semantik teilen“ — kein Teilen nur zur Vermeidung von Duplikation, wenn die fachliche Bedeutung zwischen Kundensystem und HQ unterschiedlich ist).

## Inhalt

- `openapi/systemone-api-v1.yaml` — schlanker, handgeschriebener Cross-Service-Referenzentwurf (`success/data/error`-Antwortformat, siehe ADR-0001/ADR-0002), u. a. für `apps/hq-backend`, das noch keine Endpunkte über den Health-Check hinaus hat. **Für `apps/customer-backend` ist das lebende, maßgebliche Schema ab `S1V2-01-004` `app.openapi()` / `GET /openapi.json`** — vollständiger Vertrag (Envelope, Fehlerformat, Events, Pagination, Idempotency, Concurrency) in [`../../docs/architecture/api-contract.md`](../../docs/architecture/api-contract.md). Diese YAML-Datei bewusst nicht synthetisch nachgezogen, um keine zwei parallel zu pflegenden Wahrheiten zu erzeugen.

## Grenzen

- Enthält **keine** HQ-internen Modelle (Customer/Project/SupportCase etc. aus `S1V2-03-003`) und **keine** kundenspezifischen Secrets/Konfigurationsdaten.
- Wird von `apps/customer-backend`, `apps/hq-backend` und späteren Clients (`apps/customer-app`, `apps/hq-frontend`) konsumiert, nicht umgekehrt (keine Abhängigkeit von diesem Paket zurück auf eine App — sonst zyklische Abhängigkeit).
