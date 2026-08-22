# Produktklassen- und Feature-Flag-Architektur (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-01-003 · Produktklassen- und Feature-Flag-Architektur für Pi, Mini, Server und Rack bauen`.
> Quellen: `DEC-14`, `DEC-18`, aktuelle Produktmatrix ([`../product-manifest.md`](../product-manifest.md), Abschnitt 1).

## Verbindliche Matrix

| Feature | Pi | Mini | Server | Rack |
|---|---|---|---|---|
| Smart Home | ✅ | ✅ | ✅ | ✅ |
| Pi-hole | ✅ | ✅ | ✅ | ✅ |
| NAS | ❌ | ✅ | ✅ | ✅ |
| Kamera live | ✅ (limitiert) | ✅ | ✅ | ✅ |
| Kamera-Speicherung | ❌ | ✅ | ✅ | ✅ |
| Lokale KI/PEET | ❌ | ❌ | ✅ | ✅ |
| Optionales Cloud Backup | ✅ | ✅ | ✅ | ✅ |

## Implementierung

- `apps/customer-backend/app/product_class.py` — `ProductClass`-Enum, `Feature`-Enum, `FEATURE_MATRIX` als einzige Quelle der Wahrheit.
- `apps/customer-backend/app/device_identity.py` — `get_product_class()` liest die Produktklasse **serverseitig** (aktuell: Environment-Variable `SYSTEMONE_PRODUCT_CLASS`, gesetzt bei Provisioning/Image-Erstellung). **Nicht vom Client setzbar.** Fail-closed: fehlt oder ist der Wert unbekannt, wird die Anfrage mit `500 PRODUCT_CLASS_UNKNOWN` abgelehnt statt eine Produktklasse zu erraten oder die freizügigste Klasse anzunehmen.
- `apps/customer-backend/app/features.py` — `require_feature(feature)` als FastAPI-Dependency; liefert `403 FEATURE_NOT_AVAILABLE` (im `success/data/error`-Envelope), wenn die aktuelle Produktklasse das Feature nicht besitzt.
- Beispiel-Endpunkte in `app/main.py`: `GET /api/v1/features` (Klartext-Liste, ungegatet), `GET /api/v1/nas/status` (gegatet auf `NAS`), `GET /api/v1/local-ai/status` (gegatet auf `LOCAL_AI`) — demonstrieren den Mechanismus; die echten Module (NAS, lokale KI) sind eigene spätere Aufgaben.

## Migration für spätere Features

Ein neues Feature/eine neue Produktklasse wird ausschließlich in `product_class.py` ergänzt (neuer `Feature`-Wert + Eintrag in `FEATURE_MATRIX`); alle bestehenden Endpunkte, die `require_feature(...)` nutzen, greifen die Änderung automatisch auf. Kein Endpunkt darf Produktklassen-Logik dupliziert selbst prüfen.

## Migrationspfad zur echten Geräteidentität

`get_product_class()` ist bewusst als eigene Funktion mit stabilem Rückgabetyp (`ProductClass` oder `ProductClassUnknownError`) gekapselt. Sobald `S1V2-02-027` (signierte Geräteidentität/Lizenz) steht, wird nur die Implementierung dieser einen Funktion ausgetauscht (liest dann die signierte Lizenz statt der Environment-Variable) — Aufrufer (`features.py`, Endpunkte) ändern sich nicht.

## Tests

`apps/customer-backend/tests/test_feature_matrix.py`: parametrisierte Matrix über alle vier Produktklassen für zwei Beispiel-Features (`nas`, `local_ai`), plus Tests für die Feature-Liste und für Fail-closed-Verhalten bei fehlender/unbekannter Produktklasse. Ergebnis: **8/8 Tests bestanden** (`apps/customer-backend`, inkl. bestehendem Health-Test).
