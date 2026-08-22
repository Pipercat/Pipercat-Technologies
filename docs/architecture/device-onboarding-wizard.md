# Geräteassistent für Discovery, Pairing, Raum und Namen (Stand 22.08.2026)

> Erledigt den **Zigbee+Matter-Anteil** der Notion-Aufgabe `S1V2-02-031 · Geräteassistent für Discovery, Pairing, Raum und Namen bauen` — siehe „Bekannte Grenzen" für Hue, das nicht Teil dieser Umsetzung ist.
> Quellen: `DEC-6`, `DEC-12`. Implementierung: `apps/customer-backend/app/services/device_onboarding.py`, `apps/customer-backend/app/services/device_registration.py` (erweitert).

## Wichtiger Hinweis vorab: DoD nicht vollständig erfüllbar

Die Definition of Done verlangt explizit: *„Mindestens Hue und Zigbee laufen über denselben SystemONE-Flow."* Home Assistants Hue-Integration paart Geräte über einen **physischen Tastendruck an der Bridge**, orchestriert über HAs generisches `config_flow`-Mechanismus (`async_step_link` in `homeassistant/components/hue/config_flow.py`, gegen den echten Quellcode verifiziert) — **kein** einfacher Service-/WebSocket-Befehlsaufruf wie bei ZHA (`zha.permit`) oder Matter (`matter/commission`). Eine echte Hue-Pairing-Anbindung bräuchte einen generischen `config_entries/flow`-WebSocket-Client (create/step/configure) — ein deutlich größeres, eigenständiges Vorhaben, das hier bewusst nicht im selben Aufwasch mit begonnen wurde, um keine ungetestete, wahrscheinlich fehlerhafte Vermutung über ein komplexes, mehrstufiges Protokoll als „fertig" auszugeben. Diese Aufgabe bleibt deshalb auf „In progress", bis entweder Hue eigens umgesetzt oder eine Person mit echter Hue-Hardware den vollständigen Nachweis erbringt.

## Was tatsächlich einheitlich ist — und was nicht

Das **Starten** einer Pairing-Sitzung ist genuin integrationsspezifisch: Zigbee braucht eine Permit-Join-Dauer, Matter einen Pairing-Code oder eine Netzwerk-PIN, Hue einen physischen Tastendruck. Der Assistent versteckt diesen Unterschied nicht künstlich. Was aber bereits **identisch** ist — ohne dass diese Aufgabe daran etwas ändern musste — ist alles **nach** dem Start: `ZigbeePairingService` (`S1V2-02-022`) und `MatterCommissioningService` (`S1V2-02-023`) haben beide exakt dieselbe Methode `discover_new_devices(*, known_before: set[str]) -> list[DomainDevice]`, mit identischem Namen und identischer Signatur — reiner Zufall der bisherigen, unabhängigen Umsetzung, hier zum ersten Mal als **das** gemeinsame `DevicePairingPort`-Protocol benannt und genutzt.

`DeviceOnboardingWizardService.discover_devices()` ruft diese eine Methode über eine Protocol-Referenz auf — derselbe Code läuft nachweislich für Zigbee und für Matter (siehe Tests unten), ohne Fallunterscheidung.

## „SystemONE-Profil prüfen ... Beta/unsupported klar kennzeichnen"

`evaluate_compatibility()` ist ein dünner, expliziter Wrapper um `app.device_compatibility.lookup_compatibility()` (`S1V2-02-026`) — `None` bedeutet „kein Profil registriert" und muss von der aufrufenden Oberfläche als unklassifiziert/Beta behandelt werden, nie als stillschweigendes „wohl Certified/Compatible".

## „Testaktion anbieten" — bewusst kein neuer Code

Sobald ein Gerät registriert und mit Raum/Name versehen ist, ist „ausprobieren" exakt `DeviceCommandService.send_command()` (`S1V2-02-019`) — bereits mit Berechtigungs-/PIN-Prüfung und Audit. Diese Logik für die Ersteinrichtung zu duplizieren wäre genau die verfrühte Abstraktion, die dieses Repo an anderer Stelle bereits vermeidet.

## „Raum und verständlichen Namen setzen"

`DeviceRegistrationService` (`S1V2-02-003`/`-017`) um `assign_room_and_name()` erweitert — aktualisiert die bereits über `register_device()` angelegte, persistierte `Device`-Zeile in-place (dasselbe „keine neuen Geräteobjekte bei Umbenennung/Raumwechsel"-Prinzip wie `S1V2-02-017`s Import-Update-Pfad), erzeugt nie eine zweite Zeile.

## Tests

- `apps/customer-backend/tests/test_device_onboarding.py` (3 Tests): `discover_devices()` liefert für einen `ZigbeePairingService` **und** einen `MatterCommissioningService` — mit demselben Aufrufcode — korrekt die jeweils neu hinzugekommenen Geräte; `evaluate_compatibility()` liefert `None` für unregistrierte Kombinationen bzw. das echte Profil inkl. Disclaimer für registrierte.
- `apps/customer-backend/tests/test_device_registration_service.py` (2 neue Tests): `assign_room_and_name()` aktualisiert die bestehende Zeile (keine neue), Berechtigungsprüfung greift.

Gesamt `apps/customer-backend`: **376/376 bestanden** (371 aus `S1V2-01-003`–`S1V2-02-030` + 5 neue). `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund.

## Architekturentscheidungen

- `DevicePairingPort` benennt eine bereits zufällig identische, existierende Methode auf zwei unabhängig gebauten Services — keine neue Abstraktion, die beide Services hätte ändern müssen.
- Kein neuer Code für „Testaktion" — bewusste Wiederverwendung von `DeviceCommandService`.
- Hue bewusst nicht in derselben Aufgabe versucht (siehe Hinweis oben) — ein generischer `config_entries/flow`-Client ist ein eigenständiges, deutlich größeres Vorhaben, das ohne echte Hue-Hardware zur Verifikation ein hohes Risiko unentdeckter Fehler in einem mehrstufigen, zustandsbehafteten Protokoll trüge.

## Bekannte Grenzen

- **Hue nicht umgesetzt** (siehe Hinweis oben) — DoD dieser Aufgabe daher nicht vollständig erfüllt. Eine künftige Aufgabe müsste HAs `config_entries/flow`-WebSocket-Protokoll generisch client-seitig implementieren (create flow → `async_step_link` erkennen → auf Tastendruck warten/pollen → Ergebnis), dann gegen echte Hue-Hardware verifizieren.
- Kein API-Endpunkt — dieselbe „gebaut, aber unverdrahtet"-Konvention wie mehrere andere Services dieser Session; wartet auf `S1V2-02-033`s Datenbank-/Session-Verdrahtung von `main.py`.
- `evaluate_compatibility()` braucht Hersteller/Modell als explizite Parameter — die automatische Ableitung aus einem `DomainDevice` ist bereits in `S1V2-02-026`s „Bekannte Grenzen" als offene Korrelationsarbeit benannt, hier nicht erneut versucht.
