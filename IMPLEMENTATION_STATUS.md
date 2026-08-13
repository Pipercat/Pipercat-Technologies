# Implementierungsstatus

## SystemONE Pi Core v0.4.0

Der aktuelle MVP-Entwicklungsstand liegt auf `mvp/systemone-pi-v0.1`. Die Pilotarchitektur ist mit [ADR-0001](docs/architecture/adr-0001-systemone-pi-pilot.md) als lokaler modularer Node.js-Core festgelegt.

Belegt umgesetzt:

- normalisiertes Modell für fünf Geräteprofile
- Capability-Layer, Adapter-Abstraktion und Geräte-Registry
- hardware-sichere Hue-Simulation und Reconnect-Diagnose
- Backup Schema v2 mit Prüfsumme, Migration, Validierung und Restore-Rollback
- lokale Automation Engine, Scheduler und Sonnenzeiten
- atomare Persistenz und Recovery beschädigter Zustände
- Clear und Midnight sowie geführter simulierter Geräteassistent
- mobile Midnight-App-Vorschau mit Home, Räume, Geräte und Mehr
- zentrale App-Tokens, touchfreundliche Komponenten und responsiver Smartphone-Pfad
- 50 hardwarefreie Selftests

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

- detaillierte Moduldateien
- Security- und Privacy-Baseline
- Vertragsentwürfe
- GitHub-Workflows und Issue-Templates
- Logo-Assets
- konkrete Firmendaten
- Pilotkundenprozess
- API-Spezifikationen
- Finanz- und Margenkalkulation
- persistentes vollständiges Onboarding
- lokale Benutzer, Sessions, Rollen, CSRF-Schutz und Rate Limits
- TLS und lokale Geräteidentität
- echte Hue-Hardware- und Ausfallmatrix
- normalisierter Live-Ereignisstrom
- signierte Updates, A/B-Rollback und praktischer Recovery-Test
- Pilotinstallations- und Supportdokumentation

## Nächste empfohlene Schritte

1. Smartphone-App über relevante Größen stabilisieren.
2. Hue-Supportmatrix und Release-Gates festlegen.
3. persistentes Onboarding und lokale Rollen/Sessions umsetzen.
4. Hue-Hardwarepfad kontrolliert validieren.
5. Security-, Update-, Backup- und Rollback-Gates erfüllen.
6. Pilotkundenprozess dokumentieren und intern testen.
