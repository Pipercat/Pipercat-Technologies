# Owner, Haus, Standort, Zeitzone und Räume im Ersteinrichtungswizard (Stand 22.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-030 · Owner, Haus, Standort, Zeitzone und Räume im Ersteinrichtungswizard anlegen`.
> Quellen: `DEC-9`, `DEC-120`. Implementierung: `apps/customer-backend/app/services/setup_wizard.py`.

## „Owner, Haus" ist bereits erledigt — diese Aufgabe ergänzt den Rest

`S1V2-02-028`s `DevicePairingService.claim_device()` legt bereits Haushalt + ersten Owner-User atomar an (Abhängigkeit dieser Aufgabe). `SetupWizardService` ist der nächste Schritt im selben Assistenten: Standort, Zeitzone und die ersten Räume — aufgerufen, nachdem die Kopplung aus `-028` bereits abgeschlossen ist.

## „Standort nur in minimal erforderlicher Genauigkeit speichern"

`set_location_and_timezone()` rundet Breiten-/Längengrad auf **2 Nachkommastellen** (~1,1 km Genauigkeit), bevor überhaupt gespeichert wird — genug für Zeitzone/Sonnenauf-/-untergang/regionale Wetterdaten, nie straßengenaue Ortung. Die volle, vom Gerät gemeldete Präzision wird nirgendwo persistiert.

## „Teilabbruch wiederaufnehmbar, aber kein halb autorisiertes System erzeugen"

Zwei getrennte Garantien:

1. **Jeder Schritt ist seine eigene atomare Transaktion** (`with uow_factory() as uow: ... uow.commit()`) — dasselbe Muster wie `DevicePairingService`/`RoomService`. Ein fehlgeschlagener Schritt hinterlässt nie einen halb angewendeten Zustand.
2. **`add_rooms()` ist wiederholungssicher**: bereits vorhandene Raumnamen (groß-/kleinschreibungsunabhängig verglichen) werden beim erneuten Aufruf übersprungen, nie dupliziert — ein Netzwerk-Timeout, nach dem der Client denselben Request wiederholt, erzeugt keine doppelten Räume.

**Kein Raten beim Fortschritt**: `get_progress()` liefert den **tatsächlichen** aktuellen Zustand (echte Zeitzone, echter Standort, echte vorhandene Raumnamen, `completed`-Flag) — nicht eine Vermutung wie „Zeitzone weicht vom Standardwert ab, also wohl schon gesetzt" (was bei einem deutschen Kunden, dessen echte Zeitzone zufällig dem Standardwert entspricht, falsch läge). Ein wiederaufgenommener Assistent sieht echte Daten, nie eine Schätzung.

`complete_setup()` ist selbst idempotent (`HouseholdRepository.mark_setup_completed()` setzt `setup_completed_at` nur, wenn es noch `NULL` ist) — ein erneuter Aufruf ist ein No-op, nie ein Fehler.

## Neue Datenbank-Spalte

`households.setup_completed_at` (nullable, `TIMESTAMPTZ`, neue Migration `0006_household_setup_completion.py`) — `NULL`, bis der letzte Assistenten-Schritt sie setzt. Eine echte, abfragbare Antwort auf „wurde dieser Haushalt je fertig eingerichtet", nicht aus anderen Feldern abgeleitet.

## Neue Repository-Fähigkeiten

`HouseholdRepository` (aus `S1V2-02-028`) erweitert um `set_timezone_and_location()` und `mark_setup_completed()` — sowohl in der echten SQLAlchemy-Implementierung als auch im Fake.

## Tests

`apps/customer-backend/tests/test_setup_wizard.py` (15 Tests): Zeitzone/Standort werden übernommen, Standort wird auf 2 Nachkommastellen gerundet, Berechtigungsprüfung (fehlende Berechtigung, haushaltsübergreifender Zugriff), nicht existierender Haushalt wird abgelehnt, erfolgreiche Standort-Setzung wird auditiert, Räume werden angelegt, wiederholter Aufruf mit teilweise gleichen Namen erzeugt keine Duplikate (auch nicht bei anderer Groß-/Kleinschreibung), Abschluss markiert den Haushalt, Abschluss ist idempotent, Fortschritt liefert den echten Zustand über mehrere Schritte hinweg.

Zusätzlich: `alembic/versions/0006_household_setup_completion.py` gegen echtes PostgreSQL verifiziert (`tests/test_migrations.py`s Upgrade/Downgrade/Upgrade-Rundlauf).

Gesamt `apps/customer-backend`: **371/371 bestanden** (356 aus `S1V2-01-003`–`S1V2-02-029` + 15 neue). `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund. `docker compose config`: erfolgreich validiert (unverändert).

## Architekturentscheidungen

- `WizardProgress` liefert echte Werte, keine abgeleiteten Booleans — vermeidet die „weicht vom Standardwert ab" Falle (siehe oben).
- `add_rooms()`s Duplikat-Vermeidung direkt im Service, nicht als DB-Constraint — ein Raumname ist bewusst nicht global eindeutig (zwei Haushalte, oder derselbe Haushalt mit Absicht umbenannter Räume, dürfen identische Namen haben); die Prüfung gilt nur für den einen Wiederholungssicherheits-Anwendungsfall dieser Aufgabe.
- Standort-Rundung im Service, nicht in der Datenbank (kein `CHECK`/Trigger) — die Rundung ist eine Anwendungslogik-Entscheidung, keine Datenintegritätsregel.

## Bekannte Grenzen

- **Kein API-Endpunkt** — `SetupWizardService` ist vollständig gebaut und getestet, wartet wie `DevicePairingService` (`S1V2-02-028`) auf `S1V2-02-033`s Datenbank-/Session-Verdrahtung von `main.py`.
- **Kein Gate für „nicht fertig eingerichtete" Haushalte** — `setup_completed_at` wird gespeichert und ist über `get_progress()` abfragbar, aber nichts verhindert aktuell, dass ein Owner mit noch unvollständigem Setup andere API-Routen nutzt (ohnehin irrelevant, solange `main.py` noch keine dieser Routen mit echter DB-Anbindung anbietet — siehe oben). Eine künftige Aufgabe, die echte API-Routen verdrahtet, müsste entscheiden, ob/wo ein solches Gate sinnvoll ist.
- Keine Möglichkeit, einen bereits angelegten Raum umzubenennen oder zu entfernen im Rahmen des Assistenten selbst — dafür existiert bereits `RoomService` (`S1V2-02-003`) als eigene, allgemeine Zuständigkeit.
