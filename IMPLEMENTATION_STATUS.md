# Implementierungsstatus

## SystemONE Pi Core v0.4.0 · Stand 16.08.2026

Der aktuelle MVP-Entwicklungsstand liegt auf `mvp/systemone-pi-v0.1`. Die Pilotarchitektur ist mit [ADR-0001](docs/architecture/adr-0001-systemone-pi-pilot.md) als lokaler modularer Node.js-Core festgelegt. **295/295 hardwarefreie Selftests bestanden** (`npm test`), `npm run check` erfolgreich.

Belegt umgesetzt:

- normalisiertes Modell für fünf Geräteprofile, Capability-Layer, Adapter-Abstraktion und Geräte-Registry
- hardware-sichere Hue-Simulation, Reconnect-Diagnose und lokaler Live-Ereignisstrom für Gerätezustände
- Backup Schema v2 mit Prüfsumme, Migration, Validierung, Restore-Rollback, Rotation und geschütztem USB-/NAS-Export
- lokale Automation Engine, Scheduler, Sonnenzeiten, Verlauf/Wiederholen und Neustart-/Zeitwechsel-Robustheit
- atomare Persistenz und Recovery beschädigter Zustände
- vier geplante Themes (Clear und Midnight fertig; Compact/Living als eigene Aufgaben umgesetzt), adaptive Layouts, Kiosk-/Wanddisplay-Profil, Dashboard-Bearbeitungsmodus, vereinheitlichte UI-Zustände/Barrierefreiheit
- vollständiges persistentes Erststart-Onboarding: Sprache/i18n, Theme-Vorschau, Haus/Standort/Räume, gehärtetes Admin-QR-Pairing, lokale Sessions/Rollen, physische Owner-Recovery
- lokale Web-Sicherheitsbasis mit Sessions/Rollen/CSRF/Rate-Limiting; **schreibende Endpunkte (Backup-Export, Diagnose, Admin-Re-Pairing) verlangen jetzt eine gültige lokale Session**
- TLS-Pflicht mit Gültigkeits-, Rechte- und Widerrufsprüfung; kein HTTP-Fallback, fail-closed bei ungültigem Material
- signierte Update-Bundles mit vollständiger Datei-/Hash-/Größenprüfung, Replay-Schutz und redigiertem öffentlichem Slot-Status
- A/B-Release-Slots inkl. systemd-Integration, geordnetem Shutdown und Neustartschleifen-Schutz (Zustandsautomat hardwarefrei getestet; realer Stromausfalltest auf Ziel-Pi offen)
- reproduzierbare, deterministische Release-Bundles inkl. CI-Absicherung (`npm ci`, Secret-Scan über volle Git-Historie)
- sicherer Diagnoseexport mit Vorschau und zentraler Secret-Redaction
- lokale ONVIF-/RTSP-Kamera-Liveansicht, Pi-hole-Modul, YouDo-Hooks und Govee-Adapter (jeweils simulationsbasiert/prototypisch)
- stabiler API-/Event-Vertrag für mobile Clients; installierbare lokale PWA mit gehärtetem Caching/CSP
- Installations-, Bedienungs-, Backup- und Recovery-Anleitung (`docs/systemone-user-guide.md`) sowie Pilotkunden-Checkliste

## Dokumentationsbasis v0.1

Erstellt wurden erste belastbare Dokumente für:

- Haupt-README und Navigation
- Unternehmenskonzept
- Produktübersicht
- SystemONE
- Peet AI
- YouDo
- Digital Screen
- Digital Services
- Zielarchitektur mit Mermaid-Diagrammen
- Preisstrategie
- rechtlicher Arbeitsbereich
- Roadmap
- Branding-Grundlagen
- offene Gründerfragen

## Getroffene Annahmen

- Das Unternehmen befindet sich in der Konzept- und Aufbauphase.
- Start als Einzelunternehmen beziehungsweise Kleingewerbe ist vorgesehen.
- Kundendaten sollen standardmäßig lokal bleiben.
- Updates und Fernwartung sollen eine transparente Kundenfreigabe erfordern.
- SystemONE ist die zentrale Plattform; Peet AI, YouDo und Digital Screen sind integrierte Produktfamilien.

## Noch offen vor Pilotfreigabe

Der Code-/Dokumentationsstand ist für die folgenden Punkte vorbereitet; offen ist ausschließlich der **praktische Nachweis auf echter Hardware bzw. mit echten Personen**, der nicht durch Simulation ersetzt werden darf:

- reale Hue-Bridge- und Lampenvalidierung inkl. Ausfall-/Reconnect-Matrix im Ziel-LAN (`docs/hue-support-matrix.md`)
- praktischer A/B-Update-, Stromausfall- und Rollback-Test auf dem Ziel-Pi (`docs/ab-update-rollback.md`)
- externer Verständlichkeitstest der Anleitung mit einer technikunerfahrenen Person (`docs/systemone-user-guide.md`)
- Eigener-Haushalt-Pilot auf realer Zielhardware (`mvp/systemone-pi/docs/household-pilot-runbook.md`)
- Familien-/Freundespilot (`mvp/systemone-pi/docs/family-friends-pilot-runbook.md`)
- externe Beta erst nach erfüllten Freigabekriterien
- unternehmensseitig weiterhin offen: Rechtsform, Finanz-/Margenkalkulation, Vertragsentwürfe, konkrete Firmendaten (unabhängig vom Repo-Critical-Path)

## Nächste empfohlene Schritte

1. Reale Hue Bridge im Ziel-LAN anschließen und das zehnschrittige Hardwareprotokoll aus `docs/hue-support-matrix.md` durchlaufen.
2. A/B-Update inkl. Stromausfall/Rollback nach `docs/ab-update-rollback.md` auf einem echten Pi durchspielen.
3. Eine technikunerfahrene Person die Sechs-Ziele-Prüfung aus `docs/systemone-user-guide.md` durchführen lassen und Ergebnisse einarbeiten.
4. Eigenen-Haushalt-Pilot nach `mvp/systemone-pi/docs/household-pilot-runbook.md` durchführen.
5. Familien-/Freundespilot durchführen, Findings priorisieren.
6. Danach: Freigabekriterien final prüfen und externe Beta starten.
