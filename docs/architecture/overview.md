# Zielarchitektur

> Für den aktuellen SystemONE-Pi-Pilot gilt verbindlich [ADR-0001](adr-0001-systemone-pi-pilot.md). Die folgende Control-Plane-Architektur beschreibt eine spätere Produktstufe und ist keine Abhängigkeit des lokalen Pi-MVP.

## Überblick

```mermaid
flowchart LR
  A[SystemONE Control Plane] --> B[Geräteidentität & Zertifikate]
  A --> C[Modulkatalog]
  A --> D[Update- und Freigabedienst]
  A --> E[Monitoring & Audit]
  B --> F[SystemONE Pi]
  B --> G[SystemONE Mini]
  B --> H[SystemONE Server]
  B --> I[SystemONE Rack]
  F --> J[Lokale Kundendaten]
  G --> J
  H --> J
  I --> J
  D --> K[Kundenfreigabe]
  K --> F
  K --> G
  K --> H
  K --> I
```

## Architekturprinzipien

- Kundendaten bleiben standardmäßig lokal.
- Die zentrale Ebene speichert nur notwendige Verwaltungsmetadaten.
- Jedes Gerät besitzt eine eindeutige Identität.
- Kommunikation erfolgt verschlüsselt und authentisiert.
- Module werden versioniert und reproduzierbar bereitgestellt.
- Updates benötigen Kundenfreigabe und erzeugen vorher ein Backup.
- Kritische Aktionen sind protokolliert und rückrollbar.

## Provisionierungsprozess

```mermaid
sequenceDiagram
  participant T as Techniker
  participant S as SystemONE
  participant D as Kundengerät
  participant K as Kunde
  T->>S: Kunde, Hardware und Module auswählen
  S->>D: Basisimage und Geräteidentität bereitstellen
  D->>S: Sichere Registrierung
  S->>K: Konfiguration zur Freigabe anzeigen
  K->>S: Installation bestätigen
  S->>D: Module und Konfiguration ausrollen
  D->>S: Status und Audit-Ereignis melden
```

## Updateprozess

```mermaid
sequenceDiagram
  participant R as Release-System
  participant S as SystemONE
  participant K as Kunde
  participant D as Gerät
  R->>S: Signiertes Update veröffentlichen
  S->>K: Änderungen und Risiken anzeigen
  K->>S: Update freigeben
  S->>D: Backup anfordern
  D->>S: Backup erfolgreich
  S->>D: Update installieren
  D->>S: Health Check
  alt Fehler
    S->>D: Rollback auslösen
  end
```

## Noch zu entscheiden

- konkrete Container- und VM-Plattform
- Queue- und Event-Technik
- zentrale versus dezentrale Agentenlogik
- Zertifikatsstelle und Schlüsselrotation
- Offline-Updatepfad
- Mandanten- und Rollenmodell

## Verbindlicher Pi-Pilot

- modularer Node.js-Monolith mit eigener lokaler Weboberfläche
- normalisiertes Gerätemodell und austauschbare Herstelleradapter
- dateibasierte, atomare lokale Persistenz für den geschlossenen Pilot
- keine zentrale Control Plane und kein sichtbares Home Assistant im MVP
- FastAPI/PostgreSQL nur als spätere Neubewertung; Flutter nur als möglicher Client nach Stabilisierung des API-/Event-Vertrags
