# AGENTS.md — Verbindliche Arbeitsanweisung für jede KI/Contributor

> Erledigt Notion-Aufgabe `S1V2-00-001 · KI-Arbeitsanweisung und Projektregeln verbindlich machen`
> (Quellen: DEC-2, DEC-4, DEC-7, DEC-17, DEC-37, DEC-38, DEC-196–205 im Notion-Entscheidungslog).

Dieses Dokument ist die verbindliche Betriebsanleitung für jede KI (und jeden menschlichen Contributor), die am Pipercat-Technologies-/SystemONE-Repository arbeitet. Es muss vor jeder inhaltlichen Arbeit gelesen und befolgt werden.

## 1. Fachliche Quelle

- Der aktive Entwicklungsplan ist die Notion-Datenbank **Aufgaben**, Ansicht **„Aktueller Entwicklungsplan“**, gefiltert auf `Plan-Generation = 2026-08 Neuaufbau`. Aufgaben-IDs im neuen Plan tragen das Präfix `S1V2-`.
- Ältere `S1-*`- und `BUILD-*`-Aufgaben (`Plan-Generation = Altbestand`) sind **kein** aktiver Plan mehr — nur Referenz/Historie.
- Fachliche Priorität bei Widersprüchen:
  1. neuere eindeutige Entscheidung im **Entscheidungslog**,
  2. aktueller Stand der Seite **„06 · Gründer-, Rechts- & Compliance-Fragen“**,
  3. aktive `S1V2-*`-Aufgabe,
  4. bestehender Repository-Code,
  5. ältere/archivierte Dokumentation (inkl. ADR-0001 und `ROADMAP.md`, soweit sie dem neueren Stack widersprechen).
- Bei einem echten, nicht auflösbaren Widerspruch zwischen zwei verbindlichen Quellen: nicht raten, keine Produktentscheidung erfinden. Blocker in der betroffenen Notion-Aufgabe dokumentieren und eine konkrete Rückfrage stellen. Status dabei auf `In progress` lassen, nicht auf `Done`.

## 2. Arbeitsweise

1. Aufgaben ausschließlich in aufsteigender `Reihenfolge` bearbeiten. Spätere Aufgaben nur vorziehen, wenn ihre Seite dies ausdrücklich erlaubt.
2. Vor Beginn: Voraussetzungen (`Abhängigkeiten`) und Definition of Done prüfen. Nicht erfüllte Voraussetzungen = stoppen, Blocker dokumentieren, Status nicht auf `Done` setzen.
3. Bestehenden funktionierenden Code zuerst verstehen und wiederverwenden. Keine unnötigen Rewrites, Frameworkwechsel oder Architekturänderungen ohne dokumentierte Notwendigkeit.
4. Nichts löschen, nur weil es nicht (mehr) zur Zielarchitektur passt — veraltete Bereiche markieren, nicht kommentarlos entfernen.
5. Bei jeder außerhalb des Aufgaben-Scopes gefundenen Auffälligkeit: dokumentieren; nur beheben, wenn die Behebung klein, risikoarm und für die aktuelle Aufgabe notwendig ist; sonst als Folgearbeit vermerken. Keine unkontrollierte Scope-Ausweitung.

## 3. Verbindlicher technischer Stack (DEC-4)

- **Clients:** Flutter.
- **Backend/API:** FastAPI.
- **Datenbank:** PostgreSQL.
- **Geräte-/Server-Betriebssystem:** Debian.
- **Container-Basis:** Docker Compose.
- **Geräte-/Smart-Home-Events:** MQTT.
- Redis, Celery, NATS oder vergleichbare zusätzliche Infrastruktur nur nach neu dokumentiertem, nachgewiesenem Bedarf.
- **Home Assistant** ist eine für den Endkunden vollständig **versteckte Pflicht-Integrationsschicht** unterhalb von Device Model/Capability Layer/Registry (`HomeAssistantAdapter → Home Assistant → Hue/Zigbee/Matter/Shelly`), nicht optional wie in ADR-0001 beschrieben.
- Pi/Mini bleiben bewusst schlank; Server/Rack dürfen zusätzliche Isolation, Container oder VMs nutzen, ohne den gemeinsamen SystemONE-Stack zu verändern.

**Wichtiger Hinweis für jede KI:** Der aktuelle Repository-Code unter `mvp/systemone-pi/` (Branch `mvp/systemone-pi-v0.1`) ist ein vollständig eigenständiger **Node.js-Monolith ohne Datenbank, ohne MQTT, ohne Home-Assistant-Integration und ohne Flutter-Client**, entstanden unter der mittlerweile überholten `ADR-0001`. Er ist funktionierender, getesteter Code (295/295 Selftests) und darf nicht gelöscht oder ignoriert werden — er ist aber **nicht** der Zielstack aus DEC-4. Details und empfohlener Umgang: siehe [`docs/current-state.md`](docs/current-state.md).

## 4. Local-first

SystemONE ist local-first. Ein Kundensystem darf für seine Kernfunktionen nicht von SystemONE HQ, Cloud-Backup oder dauerhaftem Pipercat-Zugriff abhängig sein. SystemONE HQ ist die zentrale interne Firmenplattform von Pipercat Technologies, Kundensysteme bleiben technisch eigenständig.

## 5. Sicherheit

- Niemals Secrets in Git, Logs, Tickets oder allgemeiner Doku.
- Keine echten Kundendaten in Tests.
- Keine Umgehung von Berechtigungen; keine Deaktivierung von Sicherheitsprüfungen nur für einen erfolgreichen Test.
- Sicherheitskritische Funktionen benötigen Negativtests: unberechtigter Zugriff, falsche Rolle, manipulierte Eingaben, abgelaufene Sessions, fehlerhafte Signaturen, Replay-/Wiederverwendungsversuche, Fehler-/Recovery-Pfade.

## 6. Testpflicht

- Jede Code-Aufgabe benötigt passende Tests (Unit-, Integrations- und ggf. End-to-End-Tests sowie Fehler-/Berechtigungspfade).
- Kein `Done` bei fehlschlagenden Tests, bekannten Fehlern oder TODO-Platzhaltern für Pflichtfunktionen.
- „Code kompiliert“ bedeutet nicht automatisch `Done`.

## 6a. Notion-Statuspflege

Beim **Start** einer Aufgabe sofort `Status` auf `In progress` setzen (plus `Bearbeitet von`/`Bearbeitet am`) — nicht erst am Ende. Erst nach vollständigem Abschluss (Definition of Done erfüllt, siehe Abschnitt 8) auf `Done` setzen. So bleibt in Notion jederzeit sichtbar, woran gerade gearbeitet wird, auch wenn eine Aufgabe mehrere Arbeitsschritte/Turns braucht.

## 7. Dokumentationspflicht pro Aufgabe

Bei jeder bearbeiteten Notion-Aufgabe zwingend ergänzen: `Ergebnis`, `Geänderte Dateien`, `Architekturentscheidungen` (nur technische Detailentscheidungen innerhalb der bereits beschlossenen Architektur), `Migrationen`, `Tests`, `Sicherheitsprüfung`, `Bekannte Grenzen/offene Punkte`, `Rollback`, `Git` (Branch/Commit/PR) und eine kurze **Übergabe an nächste KI/Entwickler** (3–10 Sätze: Stand, nächste Schritte, Stolperfallen).

## 8. Statusregeln

- Nur auf `Done` setzen, wenn die Definition of Done tatsächlich erfüllt ist (Code baut/kompiliert, Tests grün, keine fehlenden Pflichtfunktionen, keine provisorischen TODOs für Pflichtfunktionen, Fehlerpfade und Security berücksichtigt, Dokumentation aktualisiert, Notion-Übergabe geschrieben).
- Bei Blockade: Status nicht auf `Done`, Blocker dokumentieren, keine erfundene Lösung einbauen.
- Keine Aufgabe darf eine spätere fachliche Entscheidung vorwegnehmen oder eine menschliche Gate-Aufgabe eigenmächtig als erfüllt markieren.

## 9. Git

- Kleine, logisch zusammenhängende Änderungen; verständliche Commit-Nachrichten; keine riesigen Misch-Commits.
- Keine generierten Dateien oder Secrets committen.
- Vor Commit Tests ausführen (`npm run verify` in `mvp/systemone-pi/`, siehe [`docs/current-state.md`](docs/current-state.md) für die aktuelle Baseline), Diff vor Abschluss selbst prüfen.
- Bestehenden funktionierenden Code nicht ohne nachvollziehbaren Grund überschreiben oder löschen. Keine destruktiven Git-Kommandos, die bestehende Arbeit verlieren könnten.
- Commits/Pushes nur nach expliziter Freigabe der verantwortlichen Person, sofern nicht anders angewiesen.

## 10. Kontinuierliche Übergabefähigkeit

Nach jeder Arbeitseinheit gilt die Testfrage: „Wenn ich jetzt sofort verschwinde: Kann eine andere KI oder ein Entwickler allein anhand von Git + Notion exakt verstehen, was getan wurde und wie es weitergeht?“ Wenn nein, ist die Dokumentation noch nicht ausreichend. Alles dauerhaft Relevante gehört ins Repository (Code, Tests, Doku) oder die passende Notion-Aufgabe — nicht nur in einen Gesprächskontext.

## Verweise

- [`docs/current-state.md`](docs/current-state.md) — Repository-Bestandsaufnahme (Notion-Aufgabe `S1V2-00-002`)
- [`docs/product-manifest.md`](docs/product-manifest.md) — verbindliches Projektmanifest (Notion-Aufgabe `S1V2-00-003`)
- [`docs/development-workflow.md`](docs/development-workflow.md) — Branch-/PR-Workflow, Lint/Test/Build-Kommandos, CI-Baseline (Notion-Aufgabe `S1V2-00-004`)
- [`docs/architecture/repo-structure.md`](docs/architecture/repo-structure.md) — Verzeichnisstruktur `apps/`/`services/`/`packages/`/`infrastructure/`, Importgrenzen (Notion-Aufgabe `S1V2-01-002`)
- [`docs/architecture/product-classes.md`](docs/architecture/product-classes.md) — Produktklassen-/Feature-Flag-Matrix Pi/Mini/Server/Rack (Notion-Aufgabe `S1V2-01-003`)
- [`docs/architecture/api-contract.md`](docs/architecture/api-contract.md) — API-v1-Envelope, Fehlerformat, Events, Pagination, Idempotency, Concurrency, Versionierung (Notion-Aufgabe `S1V2-01-004`)
- [`docs/architecture/observability.md`](docs/architecture/observability.md) — Health/Ready/Live, strukturierte Logs, Secret-Redaction, Metriken (Notion-Aufgabe `S1V2-01-005`) — **damit ist Phase „01 Fundament“ vollständig Done**
- [`docs/architecture/data-model.md`](docs/architecture/data-model.md) — PostgreSQL-Schema, Alembic-Migrationsstrategie, inkl. Sandbox-Hinweis zu Python 3.14 (Notion-Aufgabe `S1V2-02-001`)
- [`docs/architecture/adr-0002-home-assistant-backbone.md`](docs/architecture/adr-0002-home-assistant-backbone.md) — **verbindliche Zielarchitektur** (Notion-Aufgabe `S1V2-01-001`)
- [`docs/architecture/adr-0001-systemone-pi-pilot.md`](docs/architecture/adr-0001-systemone-pi-pilot.md) — historische Pilotarchitektur, teilweise ersetzt durch ADR-0002
- [`docs/architecture/overview.md`](docs/architecture/overview.md) — Kurzüberblick, verweist auf ADR-0002
- Notion: Aufgaben-Datenbank, Entscheidungslog, „06 · Gründer-, Rechts- & Compliance-Fragen“
