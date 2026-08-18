# Home-Assistant-Lifecycle-Management und Endnutzer-Abstraktion (Stand 18.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-021 · Home-Assistant-Lifecycle-Management und vollständige Endnutzer-Abstraktion umsetzen`.
> Quelle: `DEC-7`. Implementierung: `infrastructure/docker-compose/docker-compose.yml`, `apps/customer-backend/app/services/{ha_supervisor,ha_provisioning}.py`.

## Vier unabhängige Bausteine für ein Prinzip, das schon feststand

`product-manifest.md` §2 legt bereits fest: „Home Assistant ist für den Endkunden **vollständig unsichtbar** — Kunden verwenden ausschließlich die SystemONE-App bzw. lokale Weboberfläche, nie eine Home-Assistant-Oberfläche direkt." Diese Aufgabe erfindet dieses Prinzip nicht neu, sie **operationalisiert** es — vier bisher fehlende, voneinander unabhängige Teile:

1. **Kein erreichbarer HA-Port für den Kunden** (`docker-compose.yml`): der neue `home-assistant`-Service hat bewusst **kein** `ports:`-Mapping — anders als `postgres`/`mosquitto`/`customer-backend`. Selbst ein technisch versierter Kunde, der eine HA-URL erraten oder aus einem Log extrahieren würde, hätte keinen Host-Port, den er öffnen könnte; `home-assistant:8123` existiert ausschließlich im internen Compose-Netzwerk.
2. **Keine rohe HA-Fehler-/Datenvokabular im Kunden-API** — bereits durch `TranslatingHomeAssistantAdapter` aus `S1V2-02-019` gelöst, hier unverändert wiederverwendet.
3. **SystemONE, nicht der Kunde (und nicht Docker selbst), startet/stoppt/prüft HA** — neu: `HomeAssistantSupervisor`.
4. **Technische Details nur für Diagnose, nie für normale UX** — neu: `HomeAssistantSupervisor.export_diagnostics()`.

## `HomeAssistantSupervisor` (`app/services/ha_supervisor.py`)

Drei Methoden, die genau die drei im Task-Titel genannten Verben abbilden:

- **`start()`/`stop()`**: `docker compose -f <file> up -d home-assistant` / `... stop home-assistant`, über eine injizierbare `ContainerCommandRunner`-Protocol-Schnittstelle (kein echter Docker-Daemon in Tests nötig). Bewusst **kein** `restart:`-Policy im Compose-Service selbst — SystemONE entscheidet aktiv, wann HA laufen soll, nicht Dockers eigene Neustart-Heuristik.
- **`container_status()`**: `docker compose ps --status running --format {{.Name}} home-assistant` — leere Ausgabe heißt gestoppt, ein Name heißt laufend, ein fehlgeschlagener Aufruf selbst (Docker-Daemon down) ist ein eigener dritter Zustand (`UNKNOWN`), nicht fälschlich „gestoppt".
- **`health_check()`**: „Container läuft" ist notwendig, aber nicht hinreichend — Home Assistant kann noch hochfahren, unerreichbar sein, oder das gespeicherte Token ablehnen. Ruft `adapter_factory()` (siehe unten); liefert dieser `None`, ist das `NOT_CONFIGURED` (ein normaler, erwarteter Zustand vor der ersten Einrichtung, kein Fehler). Sonst wird `HomeAssistantAdapter.list_devices()` als Sonde verwendet — kein neuer Low-Level-HTTP-Code, sondern Wiederverwendung des bereits getesteten Adapters — und `HomeAssistantAuthError`/`HomeAssistantConnectionError`/`TransientDeviceError` (aus `S1V2-02-016`) werden auf `AUTH_REJECTED`/`UNREACHABLE` gemappt.

## `build_home_assistant_adapter()` (`app/services/ha_provisioning.py`)

Schließt eine bereits in `docs/architecture/home-assistant-adapter.md` und `docs/architecture/secrets-management.md` explizit als offen benannte Lücke: `SecretStore` (`S1V2-02-013`) konnte ein HA-Langzeittoken schon immer speichern, aber nichts las es je zurück, um daraus einen funktionierenden Adapter zu bauen. `SecretStore.has_secret()` (bereits für genau diesen Zweck dokumentiert: „für Status-/Health-Checks, die wissen müssen, *ob* Zugangsdaten konfiguriert sind") entscheidet `None` vs. echter Adapter — „noch nicht eingerichtet" ist ein normaler Zustand, kein Fehler, der Local-First (`product-manifest.md` §2: SystemONE muss ohne erreichbares HA starten können) respektiert.

`build_translating_home_assistant_adapter()` liefert zusätzlich die `DeviceService`-fertige, fehlerübersetzte Form aus `S1V2-02-019` — für eine künftige Aufgabe, die `app/main.py`s `SimulationDeviceAdapter`-Verdrahtung tatsächlich umstellt (siehe „Bewusst nicht Teil dieser Aufgabe").

## Diagnose vs. normale UX

`HomeAssistantSupervisor.export_diagnostics()` liefert `{"containerStatus": ..., "health": ...}` — reine interne/Support-Datenstruktur, an **keine** kundenseitige API-Route angebunden. Das ist keine Verkürzung, sondern folgt exakt dem bereits in `app/diagnostics.py` (`S1V2-02-013`) etablierten Präzedenzfall: `export_household_integrations()` existiert seit jener Aufgabe ebenfalls ohne Router-Anbindung. Eine tatsächliche Support-/Admin-Oberfläche für diese Daten ist eine eigene, spätere Aufgabe — hier zählt, dass die Daten technisch korrekt und vollständig verfügbar sind, ohne je den Kunden-API-Pfad zu berühren.

## Tests (Definition of Done)

- **`test_ha_supervisor.py`** (14 Tests, gefakter `ContainerCommandRunner`/Adapter — kein echter Docker/HA nötig): Start/Stop inkl. Fehlerfall, alle drei Container-Status, alle vier Health-Zustände, Diagnose-Export. Ein einzelner zusätzlicher Test (`@requires_docker`, übersprungen wenn `docker` nicht installiert ist) ruft die echte `docker compose config --services`-CLI gegen die reale Compose-Datei auf (seiteneffektfrei) und bestätigt, dass `home-assistant` darin auftaucht — die einzige Stelle, die tatsächlich shell-out testet.
- **`test_ha_provisioning.py`** (5 Tests, echtes PostgreSQL wie `test_secret_store.py`): kein Token → `None`, Token vorhanden → funktionierender Adapter mit exakt dem gespeicherten Token/`base_url`, `TranslatingHomeAssistantAdapter`-Variante ebenso.

Gesamt `apps/customer-backend`: **261/261 bestanden** (242 aus `S1V2-01-003`–`S1V2-02-020` + 19 neue). `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund. `docker compose config`: erfolgreich validiert — bestätigt insbesondere, dass `home-assistant` als einziger Service neben den bereits vorhandenen **kein** `ports:`-Mapping hat.

## Architekturentscheidungen

- Container-Steuerung über die `docker compose`-CLI (per injizierbarem `ContainerCommandRunner`), nicht über eine Docker-SDK-Abhängigkeit — passt zum bereits etablierten Muster, dass dieses Repo Compose-Korrektheit ohnehin über die CLI prüft (`docker compose config` als bestehendes Gate), und vermeidet eine neue, schwergewichtige Python-Abhängigkeit für eine Aufgabe, die im Kern drei Subprozessaufrufe braucht.
- `health_check()` nutzt den bereits existierenden `HomeAssistantAdapter` als Sonde statt eigenem HTTP-Code — Wiederverwendung statt Duplikation, und automatisch konsistent mit jeder künftigen Änderung an `HomeAssistantClient`s eigenem Verbindungsverhalten.
- Kein `restart:`-Policy auf dem Compose-Service — SystemONE (über `HomeAssistantSupervisor`) ist die einzige Instanz, die HA startet/stoppt, nicht Docker selbst.

## Bewusst nicht Teil dieser Aufgabe

- **`app/main.py`-Verdrahtung**: `HomeAssistantSupervisor`/`build_home_assistant_adapter()` sind vollständig gebaut und getestet, aber nicht in `main.py`s Startup eingebunden — dieselbe bereits mehrfach getroffene Entscheidung (`MqttEventBus`, `HomeAssistantEventIngestionService`): lokale FastAPI-Instanzen müssen ohne erreichbares HA starten können (Local-First), die tatsächliche Lifespan-Verdrahtung (inkl. automatischem `start()` beim App-Start, wenn ein Token konfiguriert ist) ist eine eigene, spätere Infrastrukturaufgabe.
- **Automatisiertes Erst-Onboarding** (HA-Erstinstallation, Admin-Nutzer anlegen, Langzeittoken erzeugen und in `SecretStore` speichern) — `ha_conftest.py` demonstriert bereits, wie das programmatisch geht (für Tests), aber ein produktionstaugliches, von SystemONE gesteuertes Erst-Setup ist nicht Teil dieser Aufgabe.
- **„Updates/Backups von HA müssen später durch SystemONE kontrolliert werden"** — laut Aufgabentext explizit ein *späterer* Schritt ("müssen später"), nicht Teil dieser DoD. Das persistente `ha-config`-Volume ist die dafür nötige Grundlage (Zustand übersteht Container-Neustarts/-Updates), tatsächliche Update-/Backup-Automatisierung folgt als eigene Aufgabe.
- **Support-/Admin-Oberfläche für `export_diagnostics()`** — die Funktion liefert korrekte Daten, ein tatsächlicher Endpunkt/eine UI dafür ist nicht Teil dieser Aufgabe (folgt demselben Muster wie `app/diagnostics.py`s bereits unverdrahtete `export_household_integrations()`).
