# Pipercat Technologies

> **Ein System. Beliebige Hardware. Erweiterbare Module. Zentrale Verwaltung.**

Pipercat Technologies entwickelt modulare Smart-Home-, Homeserver-, Netzwerk- und KI-Systeme. Das Unternehmen befindet sich aktuell in der Konzept-, Entwicklungs- und Aufbauphase.

## Zentrale Dokumentation

- [**Pipercat Technologies · Master-Dokumentation 2026**](docs/PIPERCAT_MASTER_DOCUMENTATION.md) – konsolidierte Unternehmens-, Produkt-, Architektur-, Sicherheits-, Roadmap- und Compliance-Dokumentation

## Kernprodukte

- [SystemONE](docs/products/systemone.md) – zentrale Plattform für Provisionierung, Betrieb, Updates und lokale Systemverwaltung
- [Peet AI](docs/products/peet-ai.md) – lokale KI-Schicht für Sprache, LLMs, Wissensdatenbanken und Automatisierungen auf Server/Rack
- [YouDo](docs/products/youdo.md) – Aufgaben-, Planungs- und Organisationsanwendung als SystemONE-Modul
- [Digital Screen](docs/products/digital-screen.md) – konfigurierbare Anzeige- und Bedienoberfläche bzw. Design-/Interaktionsvorläufer
- [Digital Services](docs/products/digital-services.md) – Webentwicklung, Software, KI-Integrationen und Automatisierungen

## Hardwarelinien

- SystemONE Pi
- SystemONE Mini
- SystemONE Server
- SystemONE Rack

## Repository-Navigation

- [Master-Dokumentation](docs/PIPERCAT_MASTER_DOCUMENTATION.md)
- [Unternehmenskonzept](docs/company/overview.md)
- [Produktübersicht](docs/products/index.md)
- [SystemONE-Pi-MVP-Scope](docs/products/systemone-pi-mvp-scope.md)
- [Geräte- und Herstellermatrix](docs/products/systemone-compatibility-matrix.md)
- [Architektur](docs/architecture/overview.md)
- [Pilotarchitektur-Entscheidung](docs/architecture/adr-0001-systemone-pi-pilot.md)
- [Sicherheit und Datenschutz](docs/security/baseline.md)
- [SystemONE Pi Recovery-Konzept](docs/security/systemone-pi-recovery.md)
- [Preismodell](docs/pricing/pricing.md)
- [Roadmap](ROADMAP.md)
- [Rechtliche Arbeitsentwürfe](docs/legal/README.md)
- [Branding](branding/README.md)
- [Offene Gründerfragen](FOUNDER_QUESTIONS.md)
- [Implementierungsstatus](IMPLEMENTATION_STATUS.md)

## Quellenprinzip

Notion ist die operative Quelle für aktuelle Produktentscheidungen und Roadmap. GitHub bleibt die Quelle für Code, versionierte technische Dokumentation und Markenassets.

## Status

Der SystemONE-Pi-Core v0.4.0 wird auf dem Branch `mvp/systemone-pi-v0.1` als geschlossener, lokaler Pilot entwickelt. Die [Pilotarchitektur](docs/architecture/adr-0001-systemone-pi-pilot.md) ist verbindlich festgelegt. Zugriffsschutz, TLS/Geräteidentität, signierte Updates und das A/B-Rollback-Modell sind implementiert und hardwarefrei getestet (295/295 Selftests). Vor der Pilotfreigabe fehlt ausschließlich der praktische Nachweis auf echter Hardware bzw. mit echten Personen: reale Hue-Hardwarevalidierung, ein A/B-Stromausfalltest auf dem Ziel-Pi sowie ein externer Verständlichkeitstest der Bedienungsanleitung — siehe [Implementierungsstatus](IMPLEMENTATION_STATUS.md).

> Rechtlicher Hinweis: Dieses Repository enthält unverbindliche Arbeitsentwürfe und keine Rechts- oder Steuerberatung. Rechtliche Dokumente müssen vor Verwendung fachkundig geprüft werden.
