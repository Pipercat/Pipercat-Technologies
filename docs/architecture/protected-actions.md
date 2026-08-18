# Neue Freigabe pro geschützter Aktion, Biometrie als Eingabe-Ersatz (Stand 18.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-012 · Haushalts-PIN pro geschützter Aktion neu verlangen und Biometrie korrekt anbinden`.
> Quellen: `DEC-127–129`. Implementierung: `apps/customer-backend/app/auth/protected_action.py`.

## Kein Freischalt-/Session-Konzept

Bewusst der Gegenentwurf zu `S1V2-02-010` (Admin-Bereich, ein 5-Minuten-Zeitfenster nach einer Freischaltung): für Kamera-, Türschloss- und vergleichbare Aktionen gibt es **keine** PIN-Freischaltsession. `ProtectedActionGuard.authorize_action()` ist der einzige Aufrufpunkt, den jeder Use-Case unmittelbar vor der eigentlichen Aktion aufrufen muss — er speichert nichts über einen vorherigen erfolgreichen Aufruf und hat dafür auch keinen internen Zustand, der das könnte. Ein zweiter, unmittelbar folgender Aufruf verlangt exakt dieselbe frische Verifikation wie der erste.

Für den PIN-Pfad wird dazu `HouseholdPinService.verify_pin()` (`S1V2-02-011`) direkt wiederverwendet — der Dienst hat selbst kein Freischaltsession-Konzept (nur die serverseitige Sperrstaffel bei wiederholten Fehlversuchen), wodurch sich „keine Freischaltsession" hier ergibt, statt separat neu erfunden zu werden.

## Biometrie ersetzt nur Eingabe, nie Berechtigungsprüfung

`authorize_action()` ruft **immer zuerst** `require_permission(actor, permission)` auf — unabhängig davon, ob anschließend per PIN oder per Biometrie verifiziert wird. Eine erfolgreich verifizierte Biometrie ersetzt ausschließlich den Eingabeschritt (Tippen der PIN durch eine Geräte-Biometrie-Prüfung); sie kann niemals eine fehlende Berechtigung des Actors kompensieren (automatisiert getestet: `test_biometric_success_does_not_bypass_the_underlying_permission_check`).

Biometrie ist zusätzlich **explizit Opt-in pro Nutzer**, entschieden vom Kundenadmin (`ProtectedActionGuard.allow_biometric()` / `disallow_biometric()`, beide hinter `users:manage`) — kein Nutzer kann sich selbst dafür freischalten, und ohne diese Freigabe wird eine ansonsten gültige Biometrie-Assertion abgelehnt (`BiometricNotAllowedError`). Die eigentliche Assertion-Prüfung nutzt denselben `BiometricVerifier`-Port wie der Admin-Bereich (`S1V2-02-010`), statt eine zweite Biometrie-Anbindung zu erfinden.

**Bewusst nicht Teil dieser Aufgabe:** Die Freigabe ist aktuell pro Nutzer (nicht pro einzelnem, registriertem Client-Gerät) im Dienst gehalten. Eine echte Gerätebindung („berechtigtes Gerät") würde eine Client-Device-Pairing-/Registrierungsfunktion voraussetzen, die im Repository noch nicht existiert (`ClientDevice`-Tabelle ist reines Schema ohne Repository/Service-Anbindung, siehe `docs/architecture/data-model.md`) — das ist Gegenstand einer künftigen, eigenen Aufgabe, nicht dieser.

## Vergessene PIN: neu setzen statt wiederherstellen

Kein Recovery-Pfad existiert oder ist geplant — `HouseholdPinService.enable_pin()` überschreibt `pin_hash` bedingungslos (Argon2id, `S1V2-02-008`), sodass ein Admin bei einer vergessenen PIN schlicht eine **neue** PIN vergibt. Die alte PIN ist danach nirgends mehr prüfbar oder rekonstruierbar (automatisiert getestet: `test_forgotten_pin_is_reset_by_an_admin_setting_a_new_one_not_recovering_the_old`).

## Tests (Definition of Done)

`apps/customer-backend/tests/test_protected_action.py` (12 Tests):

- **Keine Freischaltsession:** zwei aufeinanderfolgende Aktionen verlangen je eine eigene, frische PIN-Eingabe; eine Aktion ohne mitgelieferte PIN/Biometrie wird abgelehnt, obwohl die vorherige Aktion soeben erfolgreich verifiziert wurde (exakt die geforderte DoD).
- Falsche PIN bei der zweiten Aktion wird trotz korrekter erster Aktion abgelehnt.
- Die Sperrstaffel aus `S1V2-02-011` wirkt unverändert durch den Guard hindurch.
- Biometrie: ohne Admin-Freigabe abgelehnt, mit Freigabe erfolgreich, verlangt auch bei erlaubter Biometrie pro Aktion eine eigene Assertion, verworfene/gefälschte Assertion wird abgelehnt, `disallow_biometric()` entzieht eine zuvor erteilte Freigabe, `allow_biometric()` verlangt `users:manage`.
- Biometrie ersetzt nie die Berechtigungsprüfung (verifizierte Biometrie + fehlende Permission → weiterhin `AuthorizationError`).
- Vergessene PIN: erneutes `enable_pin()` macht die alte PIN ungültig, die neue funktioniert sofort.

Gesamt `apps/customer-backend`: **155/155 Tests bestanden** (143 aus `S1V2-01-003`–`S1V2-02-011` + 12 neue Tests aus dieser Aufgabe).

**Betriebshinweis:** `DATABASE_URL` muss das `psycopg`-Schema (v3, `postgresql+psycopg://...`) verwenden, nicht `postgresql://...` (das lädt implizit `psycopg2`, das im lokalen `.venv312` nicht installiert ist — nur `psycopg`/`psycopg-binary` 3.x). Verwechslung führt zu `ModuleNotFoundError: No module named 'psycopg2'` in allen DB-gestützten Tests (`test_migrations.py`, `test_models.py`, `test_services_sqlalchemy.py`).

## Bewusst nicht Teil dieser Aufgabe

- Echte Gerätebindung der Biometrie-Freigabe an ein registriertes `ClientDevice` (siehe oben) — folgt mit der Client-Device-Pairing-Aufgabe.
- API-Routen — folgen dem etablierten Muster dünner Router, noch nicht verdrahtet (wie bei allen bisherigen `app/auth/*`-Diensten).
- Rate-Limiting auf `authorize_action()` selbst über die bereits vorhandene PIN-Sperrstaffel hinaus (z. B. für den reinen Biometrie-Pfad) — nicht durch `DEC-127–129` gefordert.
