# SystemONE-Produktmanifest (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-00-003 · Verbindliches Projektmanifest aus allen aktuellen Anforderungen erstellen`.
> Verbindliche Kurzquelle für jede KI/jeden Contributor — bei Detailfragen gilt weiterhin die Quellenhierarchie aus [`AGENTS.md`](../AGENTS.md#1-fachliche-quelle) (Entscheidungslog > Seite „06“ > aktive `S1V2-*`-Aufgabe > Repo-Code > Altdoku). Quellen: Notion-Entscheidungslog `DEC-1–205`, Seite „06 · Gründer-, Rechts- & Compliance-Fragen“, „02 · Produkte & Angebote“, „SystemONE · Produktfamilie & Geschäftsmodell“.
>
> **Altbegriffe:** „SystemONE Master“ / „Pipercat-Master“ sind ausschließlich historische Bezeichnungen für das, was heute **SystemONE HQ** heißt. Diese Altbegriffe dürfen nicht mehr als aktueller Sollzustand verwendet werden, nur als Migrationshinweis in bestehender Alt-Doku.

## 1. Produktfamilie: Pi / Mini / Server / Rack

Eine gemeinsame, modulare Local-first-Plattform. Alle Modelle verwenden dieselbe SystemONE-API, dieselbe Benutzer-/Berechtigungslogik und dasselbe Domänenmodell, unterscheiden sich nur im Deployment-Profil (Hardwareklasse, aktivierte Module).

| Modell | Smart Home | Pi-hole | NAS | Kameraspeicher | Lokale KI |
|---|---|---|---|---|---|
| SystemONE Pi | Ja | Ja | Nein | Begrenzt | Nein |
| SystemONE Mini | Ja | Ja | Ja | Ja | Nein |
| SystemONE Server | Ja | Ja | Ja | Ja | Ja |
| SystemONE Rack | Ja | Ja | Ja | Ja | Ja, stark erweiterbar |

- **SystemONE Pi** ist das Einstiegsprodukt und der aktuelle Entwicklungsfokus (Raspberry Pi 5, 8 GB RAM, Sonoff Zigbee 3.0 Dongle, eigenes PETG-Gehäuse).
- **Mini** (Ryzen 5/Core i5, 16 GB RAM, ≥2 interne NAS-Plätze), **Server** (Ryzen 9/Core i9, 64 GB DDR5, dedizierte GPU, ZFS-Datenpool) und **Rack** (19″-Standrack, Server-Basis + Netzwerk-/USV-Infrastruktur) folgen später mit zusätzlicher Isolation/Containern/VMs, ohne den gemeinsamen SystemONE-Stack zu verändern.
- Nur neue, von SystemONE eingerichtete Systeme im Pi-MVP — kein Import bestehender Fremdinstallationen.
- Kontrollierte Geräte-Kompatibilitätsliste (Certified/Compatible/Beta); zusätzliche HA-Integrationen nur im aktivierten Beta-Modus.

## 2. Local-first (verbindlich)

SystemONE-Kundensysteme sind für ihre Kernfunktionen **niemals** von SystemONE HQ, Cloud-Backup oder dauerhaftem Pipercat-Zugriff abhängig. Fernzugriff ist standardmäßig deaktiviert und wird pro Zugriff aktiv vom Kunden freigegeben (siehe Abschnitt 6). Kundendaten bleiben standardmäßig lokal auf dem Kundensystem.

## 3. Verbindlicher technischer Stack (DEC-4)

Flutter (Client) → FastAPI (Backend/API) → Domain/Device Model → **HomeAssistantAdapter** (einzige produktive Integrationsgrenze) → Home Assistant → Hue/Zigbee/Matter/Shelly-Geräte. PostgreSQL für Fach-/Konfigurationsdaten, MQTT für Geräte-/Smart-Home-Events, Debian als Geräte-/Server-Betriebssystem, Docker Compose als gemeinsame Container-Basis. Redis/Celery/NATS nur nach neu dokumentiertem Bedarf. Details siehe [`AGENTS.md`](../AGENTS.md#3-verbindlicher-technischer-stack-dec-4) und [`current-state.md`](current-state.md) (Abgleich mit dem bestehenden Node.js-Code).

Home Assistant ist für den Endkunden **vollständig unsichtbar** — Kunden verwenden ausschließlich die SystemONE-App bzw. lokale Weboberfläche, nie eine Home-Assistant-Oberfläche direkt.

## 4. Kundenrollen, Kundenadmin, Haushalts-PIN

- **Rollenmodell:** Owner/Kundenadmin und weitere Haushaltsrollen mit granularen Rechten (Vorbild im bestehenden Code: `owner`, `administrator`, `member`, `guest`, `display` — im neuen Stack fachlich neu zu spezifizieren, siehe `S1V2-02-009`).
- **Kundenadmin-Bereich:** dauerhaft geschützt, mit automatischer Wiedersperre nach Inaktivität (`S1V2-02-010`).
- **Zwei Schutzstufen:** Admin-Passwort **und** ein 4–8-stelliger **Haushalts-PIN**. Der PIN wird für geschützte Alltagsaktionen pro Aktion neu verlangt; Biometrie kann den PIN auf unterstützten Clients ersetzen, nicht das Admin-Passwort (`S1V2-02-011`, `S1V2-02-012`).
- **App-Sicherheit:** direkte Bedienung für Alltagsfunktionen, optionale App-Startsperre; der Kundenadmin-Bereich bleibt unabhängig davon dauerhaft eigens geschützt.

## 5. Audit-/Log-Schutz

Ein manipulationsgeschützter, persistenter Audit-Log-Kern ist Pflicht (`S1V2-02-014`) — im Gegensatz zum bestehenden In-Memory-Audit-Log im Node.js-Code (siehe `current-state.md`, Abschnitt 6.1). Sicherheitswarnungen: gleichartige Meldungen werden gebündelt, kritische Meldungen bleiben separat sichtbar.

## 6. Updates, Backup, Remote

- **Updates:** werden dem Kunden angezeigt und **ausschließlich nach ausdrücklicher Zustimmung** installiert; signierte Update-Bundles, Backup vor Update, getesteter Rollback (A/B-Slots). Keine ungefragten automatischen Updates.
- **Backup:** lokal Pflicht, versioniert, validiert, secret-redigiert. **SystemONE Cloud Backup** ist ein späteres, optionales Abo für alle Geräteklassen: Ende-zu-Ende-Verschlüsselung bereits auf dem Kundengerät, Ablage als Offsite-Kopie auf Pipercat-eigener Infrastruktur, Entschlüsselungsschlüssel ausschließlich beim Kunden.
- **Remote-Zugriff/Fernwartung:** standardmäßig **deaktiviert**; nur bei Bedarf und nach ausdrücklicher, pro Zugriff aktiver Freigabe des Kunden aktivierbar. Übergangsweise über SystemONE HQ vermittelt, **später direkter WireGuard-Weg ohne Pipercat-Relay** zwischen autorisiertem Pipercat-Supportgerät und Kundensystem, mit kurzlebigen/pro-Zugriff abgeleiteten Schlüsseln (`S1V2-05-015`).

## 7. SystemONE HQ

Zentrale interne Firmenplattform von Pipercat Technologies (Altbegriffe: „SystemONE Master“/„Pipercat-Master“ — nicht mehr verwenden). Modularer interner Aufbau mit u. a.:

- **Flash-/Provisioning-Funktion:** neue SystemONE-Geräte vorbereiten, flashen, konfigurieren, für Kundeninstallationen bereitstellen; Provisioning-Schlüssel nur im HQ, keine automatische Überschreibung angeschlossener Datenträger ohne eindeutige Bestätigung.
- **Zentrale Kunden- und Systemverwaltung:** Kunden, ihre SystemONE-Systeme, Konfigurationen, Geräte, Supportfälle und relevante technische Informationen.
- **Website-Integration, Updates, Remote-Zugriffsvermittlung, Backup-Verwaltung** und interne Betriebsfunktionen als eigene Module.
- Kundensysteme bleiben davon technisch eigenständig (siehe Abschnitt 2) — HQ verwaltet, ist aber keine Laufzeitabhängigkeit des Kundenkerns.

## 8. Website-Konfigurator

Der Website-Konfigurator ist ein **Eingangspunkt für Kundenprojekte, kein Checkout**. Kunden stellen ihr gewünschtes System (Pi/Mini/Server/Rack + Optionen) zusammen oder nutzen ein Kontaktformular; jede Anfrage wird zu einem Projektvorgang in SystemONE HQ (Lead → Angebotsworkflow), nicht zu einer Direktbestellung.

## 9. Pilot- und Launch-Gates

**Pilotreihenfolge** (jede Stufe erst nach Behebung kritischer Fehler der vorherigen):
1. Eigener Haushalt als „System 0“
2. Familie (Hardware/Software/Einrichtung kostenlos)
3. Freunde (Hardware zum Selbstkostenpreis, Software stark vergünstigt)
4. Erweiterte geschlossene Beta
5. Reguläre Kunden zum Vollpreis

**Launch-Gate:** Verkauf startet erst, wenn Pilot, Recht (Verträge/Rechtsprüfung) und praktisch getestete Betriebsprozesse (Support, Update, Backup/Recovery) erfüllt sind — keines dieser Kriterien darf einzeln übersprungen werden, „Code fertig“ allein löst keinen Verkauf aus. Zum Verkaufsstart dürfen keine bekannten offenen sicherheitsrelevanten Fehler bestehen.

## 10. Geräteidentität

Jedes Komplettgerät besitzt eine lokal prüfbare, kryptografisch signierte Gerätelizenz ohne regelmäßige Online-Aktivierungspflicht. Der geräteseitige QR-Code für die Erstkopplung ist eindeutig einem Gerät zugeordnet und wird gegen dessen Identität/Lizenz geprüft, damit ein kopierter QR-Code kein anderes Gerät koppeln kann.

## 11. Nicht widersprüchlich zu behandeln

Dieses Manifest ersetzt widersprüchliche Altannahmen aus `ROADMAP.md` („Priorisiertes MVP“), `docs/architecture/adr-0001-systemone-pi-pilot.md` und `docs/architecture/overview.md`, soweit sie dem hier beschriebenen Stack/HA-Pflichtschicht widersprechen. Diese Dateien werden nicht gelöscht, sondern im Rahmen von `S1V2-01-001` als teilweise ersetzt markiert bzw. durch ein neues `ADR-0002` ergänzt.
