# SystemONE Pi: Definition of Done und Release-Gates

Stand: 13. August 2026

## Definition of Done je Arbeitspaket

Ein Arbeitspaket ist nur abgeschlossen, wenn:

- Implementierung beziehungsweise Dokumentation klein, nachvollziehbar und im vorgesehenen Scope ist.
- `npm run verify` erfolgreich ist.
- relevante Positiv-, Negativ- und Recovery-Fälle ergänzt sind.
- die betroffenen App-Flows risikogerecht sichtbar geprüft wurden.
- keine ungeplante reale Hardwarekommunikation erfolgt; Standard bleibt `HUE_MODE=simulation`.
- API-Antworten dem Vertrag `success/data/error` folgen.
- README, Architektur-, Betriebs- oder Supportdokumentation aktuell ist.
- ein abgegrenzter Commit mit verständlicher Nachricht existiert.
- Draft-PR und zugehörige Notion-Aufgabe Ergebnis und Nachweis enthalten.

## Pilot-Release-Gates

Alle Gates sind zwingend. Ein bestandener Syntax- oder Selftest ersetzt kein Hardware-, Security- oder Recovery-Gate.

| Gate | Pflichtnachweis | Aktueller Status |
|---|---|---|
| Automated | Syntax, Selftests, API-Smoke und CI grün | teilweise erfüllt |
| App | Smartphone-Kernpfade, Fehlerzustände, Tastatur/Touch und keine Konsolenfehler | teilweise erfüllt |
| Security | Authentifizierung, Rollen, CSRF, Rate Limits, TLS, Secret-Redaction und Review | offen |
| Hardware | freigegebene Hue-Modelle mit Discovery, Pairing, Steuerung, Neustart, IP-Wechsel, Offline/Reconnect | offen |
| Backup/Recovery | Backup, Restore, Neustart, beschädigte Daten und physische Recovery praktisch getestet | teilweise erfüllt |
| Update/Rollback | signiertes Offline/Online-Format, A/B-Aktualisierung und automatisches Rollback praktisch getestet | offen |
| Operations | Diagnoseexport, Audit, Installations-, Bedienungs- und Supportablauf | offen |
| Pilot | eigener Haushalt und anschließend Familie/Freunde mit priorisiertem Fehlerprotokoll | offen |

## Freigaberegeln

- `release:audit` muss am Ende erfolgreich sein.
- Jede Evidence-Referenz zeigt auf einen prüfbaren Commit, Testbericht oder ein Dokument.
- Hardware-Gates dürfen niemals durch Simulation als bestanden markiert werden.
- Externe Beta ist erst nach abgeschlossenem eigenem Haushalt- und Familien-/Freundespilot erlaubt.
- Offene kritische oder hohe Sicherheitsfehler blockieren die Freigabe.
- Ungeprüfte Geräte bleiben `unsupported` und erscheinen nicht im normalen Onboarding.

## Maschinenlesbarer Status

`mvp/systemone-pi/release-evidence.json` ist die kanonische Gate-Liste. `npm run release:audit` wertet sie aus und schlägt absichtlich fehl, solange ein Pflicht-Gate offen ist.
