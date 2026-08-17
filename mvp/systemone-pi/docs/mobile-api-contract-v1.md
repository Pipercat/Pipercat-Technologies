# SystemONE Mobile API- und Event-Vertrag v1

## Versionierung und Kompatibilität

Neue Web-, iOS- und Android-Clients verwenden `/api/v1/*`. `/api/*` bleibt als Migrationsalias erhalten. Innerhalb v1 sind ausschließlich additive Felder und neue Endpunkte erlaubt; Entfernung, Umbenennung oder Bedeutungsänderung erfordern `/api/v2`. Jede JSON-Antwort trägt `apiVersion: "1"` und `X-SystemONE-API-Version: 1`.

Erfolg: `{ "apiVersion":"1", "success":true, "data":..., "error":null }`. Fehler: `{ "apiVersion":"1", "success":false, "data":null, "error":{"code":"...","message":"...","details":{}} }`. Details sind optional und redigiert; Clients entscheiden anhand stabiler Codes, nicht anhand übersetzter Meldungen.

## Lokale Authentifizierung

Pairing erzeugt eine zwölf Stunden gültige lokale Session. Browser nutzen `HttpOnly; SameSite=Strict`-Cookie, native Clients einen Bearer-Token. Jede Route prüft die Rollenrechte erneut. Cookie-Schreibzugriffe benötigen lokalen Host, gültige Origin und `X-SystemONE-Request`; TLS-Geräteidentitäten sind für den Pilot vorgesehen. 401 bedeutet ungültig/abgelaufen/widerrufen, 403 fehlende Rolle oder Schreibschutz.

## Live-Events und Reconnect

`GET /api/v1/events/devices` liefert SSE mit Event-Schema v1, monotoner `sequence`, ISO-Zeitstempel und den Typen `device.added`, `device.updated`, `devices.resync`. Der Server sendet `retry: 5000`. Clients speichern die letzte ID; bei Lücke, Neustart oder `devices.resync` laden sie `/api/v1/state` vollständig neu. Wenn SSE nicht verfügbar ist, erfolgt höchstens alle 15 Sekunden lokales Polling. Eventfelder dürfen in v1 nur additiv erweitert werden.

`GET /api/v1/contract` veröffentlicht den maschinenlesbaren Vertrag. Contract-Tests prüfen Präfix, Envelope, Fehler, Rollen, Reconnect und Event-Schema und verhindern dadurch inkompatible Änderungen.
