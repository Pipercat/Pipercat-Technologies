# Repository-Struktur: Apps, Services, Packages (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-01-002 · Repository in klar getrennte Apps, Services und gemeinsame Pakete strukturieren`.
> Siehe [ADR-0002](adr-0002-home-assistant-backbone.md) für die fachliche Architektur, dieses Dokument für die konkrete Verzeichnisstruktur und Importgrenzen.

## Layout

```
apps/
  customer-backend/   FastAPI — läuft lokal auf jedem Kundensystem
  customer-app/        Flutter — Kunden-Client
  hq-backend/          FastAPI — SystemONE HQ
  hq-frontend/          Platzhalter, Framework noch offen (interne Admin-UI)
  website/              Platzhalter — öffentliche Website/Konfigurator
services/
  home-assistant-adapter/  Python — einzige produktive HA-Integrationsgrenze
  provisioning/             Platzhalter — HQ-Flash-/Provisioning-Engine
packages/
  shared-contracts/    OpenAPI-Vertrag + künftige gemeinsame Modelle
infrastructure/
  docker-compose/      lokale Compose-Basis für ein Kundensystem
mvp/systemone-pi/       bestehender Node.js-Pilot (ADR-0001) — unverändert, Referenz
docs/                   projektweite Dokumentation (unverändert am Ort)
```

`mvp/systemone-pi/` und `docs/` wurden **nicht verschoben** — „Bestehende Struktur nur soweit nötig migrieren“ (Notion-Vorgabe). Der neue Code entsteht parallel; eine echte Migration/Portierung von Node.js-Logik in die neuen Python-/Dart-Pakete ist keine Aufgabe dieser Strukturierung, sondern der jeweiligen fachlichen `S1V2-02-*`-Aufgaben.

## Importgrenzen

| Von | Darf importieren | Darf **nicht** importieren |
|---|---|---|
| `apps/customer-backend` | `services/home-assistant-adapter`, `packages/shared-contracts` | `apps/hq-backend`, `services/provisioning` |
| `apps/hq-backend` | `packages/shared-contracts`, `services/provisioning` (sobald implementiert) | `apps/customer-backend`-interne Module |
| `services/home-assistant-adapter` | (keine internen Abhängigkeiten) | jede `apps/*`-App (ist Leaf-Dependency, wird konsumiert, konsumiert nicht) |
| `packages/shared-contracts` | (keine internen Abhängigkeiten) | jede `apps/*`/`services/*`-Komponente |
| `apps/customer-app` (Flutter) | `packages/shared-contracts` (API-Vertrag) | jeden Python-Code direkt |
| `apps/hq-frontend` | `apps/hq-backend`-API | `apps/customer-backend`-interne Module |

Automatisiert geprüft für die Python-Pakete (`apps/customer-backend`, `apps/hq-backend`, `services/home-assistant-adapter`) durch [`scripts/check-import-boundaries.py`](../../scripts/check-import-boundaries.py):

```bash
python3 scripts/check-import-boundaries.py
```

Für Flutter/Dart und für noch nicht implementierte Bereiche (`hq-frontend`, `website`, `provisioning`) gibt es aktuell keine automatisierte Prüfung — dort gelten die Regeln zunächst nur als dokumentierte Konvention, bis dort echter Code entsteht (dann automatisiert nachzuziehen, „soweit möglich automatisiert geprüft“ laut Definition of Done).

## Weitere Regeln (aus Notion-Vorgabe übernommen)

- Gemeinsame Modelle nur bei **identischer Semantik** in `packages/shared-contracts` — HQ-interne Modelle (`Customer`, `Project`, `SupportCase` usw. aus `S1V2-03-003`) gehören nicht dorthin, auch wenn sie strukturell ähnlich aussehen.
- HQ-Secrets/Kundendaten/Adminlogik wandern nicht in Kundensystem-Pakete (bereits in jeder App-`README.md` als Grenze festgehalten).
- Keine zyklischen Abhängigkeiten — `packages/shared-contracts` und `services/home-assistant-adapter` sind bewusst als Leaf-Dependencies ohne interne Abhängigkeiten angelegt.
- Jedes Modul hat eine klare öffentliche Schnittstelle: FastAPI-Apps über ihre `/api/v1/*`-Routen, `home-assistant-adapter` über die abstrakte `HomeAssistantAdapter`-Klasse, `shared-contracts` über sein OpenAPI-Dokument.

## Build-/Testnachweis

| Paket | Kommando | Ergebnis (17.08.2026) |
|---|---|---|
| `apps/customer-backend` | `pytest` | 8 passed (siehe `docs/architecture/product-classes.md` für die seit `S1V2-01-003` hinzugekommenen Feature-Matrix-Tests) |
| `apps/hq-backend` | `pytest` | 1 passed |
| `services/home-assistant-adapter` | `pytest` | 2 passed |
| `infrastructure/docker-compose` | `docker compose config` | erfolgreich validiert |
| `apps/customer-app` | `flutter pub get && flutter test` | **nicht verifiziert** — kein Flutter-SDK in dieser Sandbox, siehe `apps/customer-app/README.md` |
| gesamt | `python3 scripts/check-import-boundaries.py` | keine Verletzung gefunden |

## Bewusst nicht in dieser Aufgabe entschieden

- HQ-Frontend-Framework (kein `DEC-*` legt es fest).
- Website-Framework.
- Ob `packages/shared-contracts` später generierte Client-/Servermodelle (z. B. via `openapi-generator`) enthält — folgt mit `S1V2-01-004`.
