# Authentifizierung, Passwortspeicherung, Sessionmodell (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-008 · Authentifizierung, Passwortspeicherung und Sessionmodell sicher implementieren`.
> Quellen: `DEC-9`, `DEC-119–122`. Implementierung: `apps/customer-backend/app/auth/`, `app/authorization.py`.

## Passwort-/PIN-Hashing

**Argon2id** über `argon2-cffi` (`app/auth/password_hashing.py`) — der aktuelle OWASP-Standardempfehlung für neue Anwendungen (speicherhart, seitenkanalresistent). `hash_password`/`verify_password`/`needs_rehash` (für spätere transparente Parameter-Upgrades). Nirgends existiert eine Klartext-Passwort-/PIN-Spalte (`app/db/models.py::User`, bereits in `S1V2-02-001` erzwungen, hier automatisiert erneut getestet).

## Sessions

`app/auth/sessions.py::SessionStore` — bewusst **In-Memory**, keine neue PostgreSQL-Tabelle: Sessions sind kurzlebiger, prozesslokaler Zustand auf einem Single-Node-Local-first-System; kein Redis/externer Store ohne nachgewiesenen Bedarf (`AGENTS.md`-Stack-Regel). Ein Prozessneustart invalidiert alle Sessions — ein bewusster, dokumentierter Kompromiss (Nutzer müssen sich neu anmelden; kein Sicherheitsproblem, da lokal).

- Tokens werden **nie im Klartext gespeichert** — nur ein SHA-256-Hash liegt im Speicher (Muster aus dem bestehenden Node-Piloten, `mvp/systemone-pi/lib/local-sessions.js`, übernommen).
- **Rotation:** `SessionStore.rotate()` widerruft das alte Token und stellt ein neues aus derselben Berechtigung/Gerätekennung aus — nie zwei gleichzeitig gültige Tokens für denselben Login.
- **Widerruf:** `SessionStore.revoke()`; eine widerrufene Session liefert `SessionRevokedError`, nicht stillschweigend Zugriff.
- **Ablauf:** jede Session hat eine `expires_at`-Zeit (Standard 12 h); `is_expired()` wird bei jeder Authentifizierung geprüft.

## Rate-Limiting

`app/auth/rate_limiter.py::RateLimiter` — Sliding-Window pro Schlüssel (aktuell `login:{user_id}`), Standard 5 Versuche/60 s. Ein erfolgreicher Login setzt das Budget zurück (`reset()`), damit ein legitimer Nutzer nach falschen Versuchen nicht dauerhaft bestraft wird. Das Limit greift **unabhängig vom finalen Ergebnis** — selbst ein danach korrektes Passwort wird abgelehnt, wenn das Kontingent aufgebraucht ist (Test `test_rate_limit_blocks_after_too_many_failed_attempts`).

## CSRF-Schutz (Cookie-Sessions)

`app/auth/csrf.py` — Double-Submit-Muster: jede Session trägt ein `csrf_token` (`SessionStore`); eine zustandsändernde, **cookie-authentifizierte** Anfrage muss dieses Token in einem Header spiegeln. Nur relevant für Cookie-Transport — ein Bearer-Token im `Authorization`-Header (der normale Weg der Flutter-App) ist von CSRF nicht betroffen, da Browser keine Custom-Header cross-site automatisch mitschicken.

## Serverseitige Rechteprüfung / kein Kunden-Root

`AuthenticationService.authenticate()` liefert einen `Actor` mit **genau** den zum Login-Zeitpunkt aus Rolle/Rechten (`role_permissions`-Join, `S1V2-02-001`-Schema) aufgelösten Berechtigungen — dieselbe `require_permission()`-Durchsetzung an der Use-Case-Grenze wie in `S1V2-02-003`. **„Kein Kunden-Root":** `app/authorization.py::Actor` lehnt jetzt strukturell jede Wildcard-Berechtigung (`"*"`) ab (`WildcardPermissionError`) — nicht nur als Konvention, sondern als Konstruktor-Validierung. Es gibt keinen Rollen-Bypass, jede Berechtigung muss einzeln in der `role_permissions`-Tabelle stehen.

## Client-Geräteregistrierung

Jede Session trägt ein `device_label` (Pflichtparameter bei `SessionStore.create()`), das künftig mit einem `ClientDevice`-Datensatz (`S1V2-02-001`) verknüpft wird — die eigentliche Geräteregistrierung/-verwaltung ist eine spätere fachliche Aufgabe (siehe „Bewusst nicht Teil dieser Aufgabe").

## Tests (Definition of Done)

`apps/customer-backend/tests/test_auth.py` (13 Tests) + Ergänzung in `test_services_sqlalchemy.py` (1 Integrationstest gegen echtes PostgreSQL):

- **Falsche Passwörter:** falsches Passwort abgelehnt; unbekannter Nutzer liefert **denselben** Fehlertyp/dieselbe Meldung wie ein falsches Passwort (keine Nutzer-Enumeration möglich).
- **Rate-Limit:** Sperre nach zu vielen Fehlversuchen (auch für ein danach korrektes Passwort); Reset nach Erfolg.
- **Ablauf:** abgelaufene Session wird abgelehnt.
- **Widerruf:** widerrufene Session wird abgelehnt; Rotation invalidiert das alte Token nachweislich.
- **CSRF:** fehlendes/falsches Token abgelehnt, korrektes akzeptiert.
- **Rechteüberschreitung:** ein `Actor` mit den Rechten einer `member`-Rolle kann eine `emergency:manage`-geschützte Aktion nicht ausführen; Wildcard-Berechtigung wird grundsätzlich abgelehnt.
- **Integration:** vollständiger Login-/Authenticate-Zyklus gegen eine echte PostgreSQL-Datenbank mit echten `User`/`Role`/`Permission`/`RolePermission`-Zeilen.

Gesamt `apps/customer-backend`: **101/101 Tests bestanden**.

## Bewusst nicht Teil dieser Aufgabe

- Client-Geräteregistrierung als eigener Use Case (Verknüpfung mit `ClientDevice`-Tabelle) — hier nur als Pflichtfeld auf der Session vorgesehen.
- Haushalts-PIN-Ablauf (per-Aktion erneut verlangen, Sperrstaffel) — eigene, im Produktmanifest bereits vorgesehene Aufgabe (`S1V2-02-011`/`-012`).
- API-Routen (Login/Logout-Endpunkte, Cookie-Ausgabe) — dünne Router folgen dem etablierten Muster, sobald eine fachliche Aufgabe dafür ansteht.
- Persistente Sessions/Multi-Node-Session-Sharing — bewusst außerhalb des lokalen Single-Node-Modells.
