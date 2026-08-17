# HQ Frontend

Platzhalter für die interne SystemONE-HQ-Weboberfläche (Kunden-/Projektverwaltung, Provisioning, Support).

## Status

Nur Verzeichnis-Platzhalter aus `S1V2-01-002`. **Framework-Wahl ist bewusst noch offen** — `DEC-4` legt Flutter für Kunden-Clients und FastAPI/PostgreSQL/Docker Compose/MQTT für den gemeinsamen Stack fest, trifft aber keine Aussage zum konkreten HQ-Frontend-Framework (internes Admin-Tool, kein Kundenprodukt). Diese Entscheidung wird in der jeweiligen HQ-Frontend-Aufgabe (Phase „03 SystemONE HQ“) getroffen, nicht hier vorweggenommen, um keine ungefragte Technologieentscheidung außerhalb des bereits beschlossenen Stacks zu treffen.

## Grenzen (bereits jetzt verbindlich)

- Greift ausschließlich auf `apps/hq-backend` zu, nie direkt auf Kundensystem-Datenbanken.
- Kein Zugriff auf `apps/customer-backend`-interne Module.
