# Shared Contracts

Gemeinsame API-/Event-Verträge und Modelle, die von mehreren SystemONE-Paketen mit **identischer Semantik** verwendet werden (siehe `S1V2-01-002`-Regel: „Gemeinsame Modelle nur bei identischer Semantik teilen“ — kein Teilen nur zur Vermeidung von Duplikation, wenn die fachliche Bedeutung zwischen Kundensystem und HQ unterschiedlich ist).

## Inhalt

- `openapi/systemone-api-v1.yaml` — SystemONE-API-v1-Vertrag (`success/data/error`-Antwortformat, siehe ADR-0001/ADR-0002). Wird in `S1V2-01-004` vollständig ausdefiniert; aktuell nur Gerüst mit dem Health-Endpunkt, der bereits in `apps/customer-backend` und `apps/hq-backend` existiert.

## Grenzen

- Enthält **keine** HQ-internen Modelle (Customer/Project/SupportCase etc. aus `S1V2-03-003`) und **keine** kundenspezifischen Secrets/Konfigurationsdaten.
- Wird von `apps/customer-backend`, `apps/hq-backend` und späteren Clients (`apps/customer-app`, `apps/hq-frontend`) konsumiert, nicht umgekehrt (keine Abhängigkeit von diesem Paket zurück auf eine App — sonst zyklische Abhängigkeit).
