# Infrastructure

- `docker-compose/` — lokale Docker-Compose-Basis für ein Kundensystem (`customer-backend` + `postgres` + `mosquitto`). HQ-Deployment ist bewusst separat (kein gemeinsames Compose-File mit Kundensystemen, siehe local-first-Prinzip).

## Status

Skeleton aus `S1V2-01-002`. `docker compose config` erfolgreich validiert (gültiges YAML, korrekt aufgelöste Build-Kontexte/Ports/Volumes). Ein echter `docker compose up`-Smoke-Test (Container-Build, tatsächlicher Start) war in dieser Sandbox nicht möglich, da der Docker-Daemon hier nicht läuft — das ist eine Sandbox-Einschränkung, kein Repo-Problem. Nachzuholen, sobald `apps/customer-backend` echte PostgreSQL-/MQTT-Anbindung hat (`S1V2-02-001` ff.) und/oder auf einer Maschine mit laufendem Docker-Daemon.
