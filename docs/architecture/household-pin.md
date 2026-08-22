# Haushalts-PIN mit Sperrstaffel und Admin-Reset (Stand 18.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-011 · Haushalts-PIN mit Benutzerfreigabe, Sperrstaffel und Reset implementieren`.
> Quellen: `DEC-123–125`, `DEC-129`. Implementierung: `apps/customer-backend/app/auth/household_pin.py`.

## Benutzerfreigabe durch den Kundenadmin

`HouseholdPinService.enable_pin(admin_actor, target_user_id, pin)` — **nur** ein Admin (`users:manage`) legt für einen anderen Nutzer eine PIN an, kein Selbstbedienungspfad. PIN-Format: 4–8 Ziffern (`PIN_PATTERN`), sonst `InvalidPinFormatError`. Gespeichert wird ausschließlich `hash_password(pin)` (Argon2id, wiederverwendet aus `S1V2-02-008`) in `User.pin_hash` — **nie Klartext, nie rücklesbar** (automatisiert getestet: der Hash enthält die PIN nicht als Teilstring).

## Sperrstaffel

`_PinLockoutTracker`: nach `LOCKOUT_THRESHOLD` (5) aufeinanderfolgenden Fehlversuchen greift die erste Sperrstufe (`LOCKOUT_STAGES[0]` = 1 Minute). Wird die Schwelle nach Ablauf der Sperre erneut erreicht, greift die **nächste, längere** Stufe (5 Min → 30 Min → 2 h → 24 h, danach verbleibt sie auf der längsten Stufe). Während einer aktiven Sperre wird **auch eine korrekte PIN abgelehnt** (`PinLockedError`) — die Sperre ist zeitbasiert, nicht durch einen richtigen Versuch aufhebbar. Ein erfolgreicher Verifikationsversuch setzt sowohl den Fehlerzähler als auch die Eskalationsstufe vollständig zurück.

## Reset nur nach erneuter Adminauthentifizierung

`reset_lockout(admin_actor, admin_raw_token, target_user_id)` verlangt zweierlei:
1. `require_permission(admin_actor, "users:manage")` — die übliche Autorisierung.
2. `self._admin_area.require_unlocked(admin_raw_token)` — der Admin muss seinen **eigenen** Admin-Bereich (`S1V2-02-010`) gerade frisch freigeschaltet haben. Eine bloß gültige, aber nicht frisch reautorisierte Admin-Session reicht **nicht** — automatisiert getestet (`test_reset_lockout_requires_the_admins_own_admin_area_to_be_unlocked`).

Das verbindet diese Aufgabe direkt mit `S1V2-02-010`, statt eine parallele „erneute Authentifizierung"-Logik zu erfinden.

## Fehlendes Benutzerrecht

Hat ein Nutzer keine PIN aktiviert (`pin_hash is None`), liefert `verify_pin()` `PinNotEnabledError` statt eines irreführenden „falsche PIN"-Fehlers — ein Client kann so zwischen „PIN existiert nicht" und „PIN falsch eingegeben" unterscheiden, ohne dass dabei sensible Details preisgegeben werden.

## Tests (Definition of Done)

`apps/customer-backend/tests/test_household_pin.py` (17 Tests):

- **Richtige/falsche Eingaben:** korrekte PIN verifiziert, falsche PIN abgelehnt, PIN nie im Klartext gespeichert.
- **Fehlendes Benutzerrecht:** Verifikation ohne aktivierte PIN, `enable_pin` ohne Berechtigung, ungültige PIN-Formate (parametrisiert über mehrere Fälle).
- **Staffelung:** Sperre nach 5 Fehlversuchen, Eskalation auf eine strikt längere Sperrdauer bei wiederholtem Überschreiten, Zurücksetzen des Zählers bei Erfolg.
- **Reset:** Reset ohne frische Admin-Freischaltung wird abgelehnt (Sperre bleibt bestehen), Reset nach frischer Freischaltung funktioniert, Reset ohne `users:manage` abgelehnt.
- Zusätzlich: Deaktivieren einer PIN entfernt sie und löscht eine bestehende Sperre.

Gesamt `apps/customer-backend`: **143/143 Tests bestanden**.

## Bewusst nicht Teil dieser Aufgabe

- Biometrie als PIN-Ersatz pro geschützter Aktion — das ist explizit `S1V2-02-012`.
- „Vergessene PIN"-Recovery-Flow — ebenfalls `S1V2-02-012`/spätere Aufgabe laut Notion-Suche.
- API-Routen — folgen dem etablierten Muster dünner Router.
