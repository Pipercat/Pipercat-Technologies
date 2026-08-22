# Observability-, Health- und Correlation-Grundlage (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-01-005 · Gemeinsame Observability-, Health- und Correlation-Grundlage implementieren`.
> Quellen: `DEC-130`, `DEC-178–183`. Implementierung: `apps/customer-backend/app/observability.py` (+ `correlation.py` aus `S1V2-01-004`).

## Health-Endpunkte

- `GET /api/v1/health` — allgemeiner, bestehender Health-Check (Kompatibilität mit `S1V2-01-002`/`-004`).
- `GET /api/v1/health/live` — Liveness: Prozess läuft. Darf **nie** von externen Systemen abhängen (DB/MQTT/Home Assistant) — ein Abhängigkeitsausfall ist „nicht ready“, nicht „nicht alive“.
- `GET /api/v1/health/ready` — Readiness: Prozess läuft UND Abhängigkeiten nutzbar. Da PostgreSQL/MQTT/Home Assistant noch nicht existieren (`S1V2-02-*`), aktuell nur ein Platzhalter — die Funktion `health_ready()` ist der einzige Ort, an dem künftige Abhängigkeits-Checks ergänzt werden (keine neuen Endpunkte pro Abhängigkeit).

## Strukturierte Logs

`app/observability.py::configure_logging(component)` richtet den Logger `"systemone"` (und alle Kind-Logger wie `"systemone.customer_backend"`) mit einem JSON-Formatter ein. Jeder Log-Eintrag enthält:

```json
{"timestamp": "...", "level": "WARNING", "component": "customer-backend", "correlationId": "...", "message": "..."}
```

- **`correlationId`**: automatisch aus einer `ContextVar` (`correlation_id_var`), die `app/correlation.py`s Middleware pro Request setzt/zurücksetzt — kein manuelles Durchreichen durch jede Funktion nötig. Für Aufrufe außerhalb eines Requests bleibt der Default `"-"`.
- **`component`**: pro Service fest übergeben (`configure_logging(component="customer-backend")` bzw. künftig `"hq-backend"`), unterscheidet Log-Quellen in einem gemeinsamen Log-Sink.
- Der Root-Logger `"systemone"` hat `propagate = False` und eigene Handler — verhindert doppelte/unkontrollierte Ausgabe über Bibliotheks-Root-Logger-Konfiguration.

## Secret-Redaction

`redact()` in `app/observability.py` ersetzt vor jeder Log-Ausgabe (über `CorrelationAndRedactionFilter`, automatisch für **jeden** Log-Aufruf über den `"systemone"`-Logger-Baum) erkennbare Secret-Muster: `password=`/`token=`/`api_key=` u. ä., `Bearer <token>`, `user:pass@`-Anteile in Connection-Strings — bewusst breit gefasst (ein falsch-positiver Treffer kostet nichts, ein geleaktes Secret schon), analog zur bereits bewährten Redaction im bestehenden Node.js-Piloten (`mvp/systemone-pi/lib/diagnostics.js`).

Der Catch-all-Exception-Handler (`S1V2-01-004`) loggt bei unerwarteten Fehlern bewusst **nur den Exception-Typ**, nie `str(exc)` — die Exception-Nachricht könnte Request-/Konfigurationsdaten enthalten, die auch redigiert unnötiges Risiko wären.

## Metriken

`MetricsRegistry` (`app/observability.py`) — ein leichtgewichtiges In-Process-Register, **bewusst kein Prometheus-Client** (keine Scraping-Infrastruktur vorhanden, die das rechtfertigt; einfachste tragfähige Lösung). Subsysteme registrieren sich selbst via `metrics.register_gauge(name, fn)`, sobald sie existieren — dieses Modul kennt DB/MQTT/HA/Backup/Update nicht hart-codiert. Aktuell registriert: `events_in_memory`, `idempotency_keys_cached`. Abgerufen über `GET /api/v1/metrics` (Envelope-Format, JSON — kein Prometheus-Textformat, da (noch) kein Scraper existiert; bei Bedarf später ergänzbar, ohne die Registrierungs-API zu ändern).

## Kamera-/Audioinhalte niemals in Standardlogs

Verbindliche Regel (noch nicht durch Code erzwingbar, da es noch kein Kamera-/Audio-Modul in `apps/customer-backend` gibt — der alte Node-Pilot hat eins, `mvp/systemone-pi/lib/camera-module.js`): Kein Kamera-Frame- oder Audio-Payload darf jemals an den strukturierten Logger übergeben werden (Datenschutz + Payload-Größe). Wenn das Kamera-Modul im neuen Stack entsteht, muss es eigene, payload-freie Log-Statements verwenden (z. B. „Frame empfangen, Größe X Bytes“, nie den Frame-Inhalt selbst) — als Prüfpunkt in die Definition of Done der jeweiligen künftigen Aufgabe aufzunehmen.

## End-to-End-Nachverfolgbarkeit (Definition of Done)

`tests/test_observability.py::test_end_to_end_correlation_id_flows_into_logs` schickt einen Request mit einer festen `X-Correlation-Id`, lässt ihn bewusst in einen Fehler laufen (fehlende Produktklasse) und prüft, dass derselbe Correlation-ID-Wert sowohl im Response-Header als auch im serverseitigen strukturierten Log-Eintrag auftaucht — das ist der geforderte Nachweis „Ein End-to-End-Request kann über Client/API/Adapter verfolgt werden“ für den aktuellen Implementierungsstand (Client → API; Adapter-Ebene folgt inhaltlich erst mit `services/home-assistant-adapter`s echter Anbindung in `S1V2-02-016` ff. und wird dort um dieselbe Correlation-ID erweitert, nicht neu erfunden).

`test_redaction_filter_applies_to_real_log_records` und `test_redact_hides_secret_shaped_values` sind die automatisierten Secret-Redaction-Tests.

## Für hq-backend und services/home-assistant-adapter

Dieselben Bausteine (`configure_logging`, `redact`, `MetricsRegistry`) sind bewusst in `apps/customer-backend/app/observability.py` belassen worden statt vorschnell in ein neues gemeinsames Paket (`packages/`) extrahiert zu werden — `apps/hq-backend` hat noch keine eigene Logik, die das rechtfertigt (aktuell nur der Health-Endpoint aus `S1V2-01-002`). **Sobald `hq-backend` oder `home-assistant-adapter` einen zweiten echten Bedarf für dieselbe Logik zeigen, gehört der Code nach `packages/` verschoben** (Duplizierung vermeiden, aber keine verfrühte Abstraktion für einen einzigen Verwender).
