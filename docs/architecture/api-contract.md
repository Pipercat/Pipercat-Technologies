# SystemONE API v1 Contract (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-01-004 · API-v1, Events und Fehlerformat als stabile Verträge definieren`.
> Referenzimplementierung: `apps/customer-backend/app/{envelope,correlation,events,pagination,idempotency}.py`. Lebendes OpenAPI-Schema: `GET /openapi.json` am laufenden `customer-backend` (siehe `packages/shared-contracts/README.md` für das Verhältnis zum handgeschriebenen Entwurf dort).

## Envelope

Jede Antwort — Erfolg wie Fehler — hat die Form:

```json
{"success": true, "data": { ... } | null, "error": null}
{"success": false, "data": null, "error": {"code": "...", "message": "...", "correlationId": "...", "details": null}}
```

`Envelope[T]`/`ApiError` in `app/envelope.py` sind Pydantic-Generics, damit FastAPI korrekte, generierbare OpenAPI-Schemas produziert (`Envelope_HealthData_` usw. in `/openapi.json`).

## Fehlerformat

- **`code`**: stabiler, maschinenlesbarer Fehlercode (`FEATURE_NOT_AVAILABLE`, `PRODUCT_CLASS_UNKNOWN`, `VERSION_CONFLICT`, `INTERNAL_ERROR`, …). Clients dürfen auf `code`, nie auf `message` prüfen (message ist für Menschen, kann sich ändern).
- **`message`**: verständliche, **sichere** Meldung. Nie Secrets, Stack Traces oder interne Pfade.
- **`correlationId`**: siehe unten — immer gesetzt, auch bei Fehlern ohne registrierten spezifischen Handler.
- **`details`**: optional, nur sicherheitsgeprüfte Zusatzinformation (aktuell ungenutzt/`null`).

Drei Handler-Ebenen in `app/main.py`:
1. `HTTPException` → Envelope mit `code`/`message` aus `exc.detail`, falls dort ein Dict mit diesen Feldern übergeben wurde (Konvention für alle `raise HTTPException(status_code=..., detail={"code": ..., "message": ...})`-Aufrufe).
2. Bekannte Domänenfehler (`ProductClassUnknownError`) → eigener Handler, fail-closed (500, nie stille Annahme).
3. **Alles andere** (`Exception`) → generischer `INTERNAL_ERROR`, feste, sichere Nachricht. Die echte Exception wird nur serverseitig geloggt (`logger.exception`), keyed auf dieselbe `correlationId`, die der Client sieht — Support kann so ohne Client-seitige Details nachvollziehen, was passiert ist.

**Getestet** in `tests/test_api_contract.py`: kein Stacktrace, keine Exception-Nachricht im Response-Body bei unerwarteten Fehlern.

## Correlation ID

`app/correlation.py` — reines ASGI-Middleware (bewusst **nicht** `Starlette.BaseHTTPMiddleware`: diese ist in der hier verwendeten FastAPI/Starlette-Version dafür bekannt, registrierte Exception-Handler für nicht-`HTTPException`-Typen zu umgehen, siehe Codekommentar). Jede Anfrage bekommt eine `X-Correlation-Id` (aus dem Request-Header übernommen, falls vorhanden, sonst neu erzeugt), gespiegelt im Response-Header und in jedem Error-Envelope.

## Ereignismodell

`app/events.py` — `DeviceStateEvent` (id, type, occurredAt, correlationId, payload) über die `EventBus`-Schnittstelle (`publish`/`recent`). **MQTT bleibt intern gekapselt:** kein Aufrufer importiert einen MQTT-Client direkt, alle gehen über `EventBus` — analog zum `HomeAssistantAdapter`-Grenzmuster in `services/home-assistant-adapter`. `InMemoryEventBus` ist ausschließlich Dev-/Test-Stand-in; die produktive MQTT-Anbindung ist `S1V2-02-004` und tauscht nur die Implementierung aus, nicht den Aufrufer-Contract.

Demo-Endpunkt: `GET /api/v1/events/recent?limit=&cursor=`.

## Pagination

Cursor-basiert (`app/pagination.py`), bewusst **nicht** Offset-basiert (nicht stabil unter gleichzeitigen Schreibvorgängen, relevant sobald Events/Audit-Einträge laufend geschrieben werden). `Page[T]` = `{items: T[], nextCursor: string | null}`. `cursor` ist ein opakes Token — Clients dürfen es nicht parsen oder selbst konstruieren.

## Idempotency

Kritische Schreiboperationen verlangen einen `Idempotency-Key`-Header (FastAPI validiert das Fehlen bereits als `422`). Serverseitig wird die erste Antwort pro Schlüssel zwischengespeichert (`app/idempotency.py`, aktuell In-Memory — **muss vor Produktivbetrieb persistent werden, sobald PostgreSQL da ist, `S1V2-02-001`**) und bei Wiederholung mit demselben Schlüssel unverändert zurückgegeben, unabhängig vom (ggf. veralteten) Request-Body. Demonstriert an `POST /api/v1/system/restart`.

## Concurrency-Schutz

Optimistisches Locking über ein `expectedVersion`-Feld im Request-Body (statt HTTP-`If-Match`/ETag, um mit dem `success/data/error`-Envelope konsistent zu bleiben statt Standard-HTTP-Conditional-Request-Semantik zu mischen). Stimmt `expectedVersion` nicht mit dem aktuellen Zustand überein: `409 VERSION_CONFLICT`. Demonstriert an `POST /api/v1/system/restart`.

## Versionierung

- URL-Präfix `/api/v1/*`. Additive Änderungen (neue optionale Felder, neue Endpunkte) sind innerhalb v1 erlaubt.
- **Breaking Changes nur versioniert:** neuer Präfix (`/api/v2/*`) mit dokumentiertem Migrationspfad und Übergangsfrist, nie ein stillschweigend geändertes v1-Verhalten.
- Jede Breaking-Change-Entscheidung gehört ins Notion-Entscheidungslog, bevor sie umgesetzt wird.

## Contract-Tests und generierbare Clientmodelle (Definition of Done)

- `tests/test_api_contract.py::test_openapi_schema_is_served_and_documents_core_paths` prüft, dass `/openapi.json` erreichbar ist, alle Kernpfade enthält und `Envelope`-/`ApiError`-Schemas mit den erwarteten Feldern exportiert — das ist die Grundlage für Client-Codegenerierung (z. B. `openapi-generator`, `quicktype`) für Flutter/TypeScript, ohne dass hier bereits ein Generator-Tool fest verdrahtet wird (bewusst nicht vorgezogen, keine zusätzliche Build-Abhängigkeit ohne konkreten Bedarf).
- „API-Dokumentation CI-validiert" wird dadurch erfüllt, dass dieser Contract-Test Teil der reguären `pytest`-Suite ist, die in `.github/workflows/systemone-core-neubau.yml` (Job `customer-backend`) läuft — bewusst kein zusätzlicher Snapshot-Diff-Mechanismus für die generierte `openapi.json`, um die Pflege nicht unnötig zu verdoppeln (einfachste tragfähige Lösung).
- `packages/shared-contracts/openapi/systemone-api-v1.yaml` bleibt ein schlanker, handgeschriebener Cross-Service-Referenzentwurf (u. a. für `hq-backend`, das noch keine FastAPI-Endpunkte über den Health-Check hinaus hat); das **lebende, maßgebliche** Schema für `customer-backend` ist ab jetzt `app.openapi()` / `GET /openapi.json`.

## Bekannter Stolperstein für künftige Tests

`fastapi.testclient.TestClient` reraised in der hier installierten Version (FastAPI 0.141.1 / Starlette 1.6.0) mit dem Default `raise_server_exceptions=True` die **ursprüngliche** Exception an den Testcode, selbst wenn ein registrierter Exception-Handler bereits eine gültige Response erzeugt hat. Tests, die absichtlich einen unerwarteten Fehler auslösen, um das Fehlerformat zu prüfen, müssen `TestClient(app, raise_server_exceptions=False)` verwenden (siehe `tests/test_api_contract.py`).
