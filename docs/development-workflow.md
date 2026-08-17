# Entwicklungsworkflow, Branch-Regeln und CI-Baseline (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-00-004 · Entwicklungsworkflow, Branch-Regeln und CI-Baseline festlegen`.
> Siehe auch [`AGENTS.md`](../AGENTS.md) (Arbeitsregeln) und [`current-state.md`](current-state.md) (IST-Zustand).

## 1. Branches

- **Aktiver Entwicklungsbranch:** `mvp/systemone-pi-v0.1` (Default für den laufenden `2026-08 Neuaufbau`-Plan, bis eine Aufgabe ausdrücklich einen neuen Ziel-Branch für die restrukturierte Codebasis festlegt — voraussichtlich im Rahmen von `S1V2-01-002`).
- **`main`** ist der produktive/öffentliche Branch. **Keine direkten Änderungen an `main`** ohne dokumentierten Grund und Freigabe der verantwortlichen Person.
- **Feature-Arbeit:** kleine, thematisch geschlossene Branches von `mvp/systemone-pi-v0.1` (bzw. später vom jeweils aktuellen Ziel-Branch) abzweigen, per Pull Request zurückführen. Kein direkter Push großer Mischänderungen ohne Review-Möglichkeit.
- **Commits:** klein, logisch zusammenhängend, verständliche Nachricht (Kontext: was/warum). Kein `--force`/`--no-verify` ohne explizite Anweisung der verantwortlichen Person.
- **Push:** Commits werden lokal erstellt; **Push nach `origin` erfolgt nur nach expliziter Freigabe** der verantwortlichen Person für den jeweiligen Stand (siehe `AGENTS.md`, Abschnitt 9). Fehlende oder unklare GitHub-Schreibrechte (z. B. wie in Notion-Aufgabe `S1-03-001` dokumentiert) sind als echter Blocker in der jeweiligen Notion-Aufgabe festzuhalten, nicht zu umgehen (kein Force-Push, kein Anlegen von Zweit-Repos als Workaround).

## 2. Lint-/Test-/Build-Kommandos

### 2.1 Bestehend: `mvp/systemone-pi/` (Node.js-Pilot)

Alle Kommandos werden **im Verzeichnis `mvp/systemone-pi/`** ausgeführt:

| Zweck | Kommando | Prüft |
|---|---|---|
| Syntax-Check | `npm run check` | `server.js` + alle `lib/*.js`/`web/*.js`/`scripts/*.js` |
| Secret-Scan (Arbeitsverzeichnis) | `npm run secrets:check` | aktuell versionierte Dateien auf Secret-Muster |
| Secret-Scan (Git-Historie) | `npm run secrets:history` | alle Blobs über alle Refs — siehe Hinweis in Abschnitt 4 |
| Tests | `npm test` | 295 hardwarefreie Selftests (`scripts/selftest.js`) |
| Gesamtprüfung | `npm run verify` | `check && secrets:check && secrets:history && test`, das ist der CI-Maßstab |
| Release-Bundle bauen/prüfen | `npm run release:build` / `npm run release:verify` | deterministisches Release-Artefakt |

Es gibt aktuell keinen separaten Lint-/Format-Schritt (kein ESLint/Prettier im Repo) — `node --check` deckt nur Syntax ab. Ob ein Linter für den bestehenden Node-Code nachgerüstet wird, ist keine Entscheidung dieser Aufgabe (kein Scope-Creep) und bleibt offen.

### 2.2 Zukünftig: neue Apps/Services (FastAPI, Flutter, Infrastruktur)

Sobald im Rahmen von `S1V2-01-002` ff. neue Verzeichnisse (`apps/`, `services/`, `packages/` o. ä.) entstehen, gilt für **jede neue App/jeden neuen Service** verbindlich:

- Eigene, im jeweiligen Verzeichnis lauffähige Standardkommandos für **Lint, Format-Check, Unit-Tests, (falls zutreffend) Integrationstests und Build**, mit denselben Namen/Konventionen wie im jeweiligen Ökosystem üblich (z. B. Python/FastAPI: `ruff`/`black --check`, `pytest`; Flutter: `flutter analyze`, `flutter test`, `flutter build`).
- Kein neuer Code ohne passenden CI-Job für diese Kommandos — eine Aufgabe, die eine neue App/einen neuen Service einführt, ist erst dann „Done“, wenn auch ihr CI-Gate steht (Testpflicht aus `AGENTS.md`).
- PostgreSQL-Migrationen (ab `S1V2-02-001`) müssen automatisiert gegen eine Testdatenbank ausgeführt und verifiziert werden, bevor eine Migrations-Aufgabe als „Done“ gilt.
- Docker-Compose-/Infrastrukturdateien (ab `S1V2-01-002` ff.) werden mindestens syntaktisch validiert (`docker compose config`) und, sobald sinnvoll möglich, gegen einen Smoke-Test-Start geprüft.

## 3. CI-Baseline

- **`.github/workflows/systemone-pi-mvp.yml`** — läuft auf `pull_request`/`push`, beschränkt auf `paths: mvp/systemone-pi/**`. Schritte: `checkout` → `setup-node@v4` (Node 20, npm-Cache über `package-lock.json`) → `npm ci --ignore-scripts` → `npm run verify`. Schlägt bei Syntax-, Secret-, Test- oder Build-Fehlern fehl (exit code ≠ 0 propagiert).
- **`.github/workflows/systemone-core-neubau.yml`** (seit `S1V2-01-002`) — läuft auf `pull_request`/`push`, beschränkt auf `paths: apps/**`, `services/**`, `packages/**`, `infrastructure/**`, `scripts/check-import-boundaries.py`. Sechs Jobs: `customer-backend`, `hq-backend`, `home-assistant-adapter` (je `pip install -e ".[dev]" && pytest -q`), `customer-app` (Flutter: `subosito/flutter-action@v2` → `flutter pub get/analyze/test` — **Konfiguration folgt Standardmuster, aber in der KI-Sandbox nicht lokal verifizierbar**, siehe `apps/customer-app/README.md`), `docker-compose-config` (`docker compose config`) und `import-boundaries` (`scripts/check-import-boundaries.py`).
- **Erweiterungsregel:** Jede weitere neue App/jeder neue Service (Abschnitt 2.2) bekommt einen eigenen Job in `systemone-core-neubau.yml` (oder einen neuen Workflow, falls thematisch sinnvoll getrennt) nach demselben Muster. Ein neuer CI-Job wird **im selben PR** eingeführt, der die neue App/den neuen Service anlegt — nicht nachträglich.
- **Kein grüner Merge ohne grüne CI.** Ein rot laufender Pflicht-Check (Lint, Test, Migration, Build) blockiert den Merge; das gilt für jeden Job in beiden Workflow-Dateien identisch.

## 4. Betriebshinweis: `git cat-file --batch` in KI-Sandbox-Umgebungen

Beim Ausführen von `npm run verify` in dieser (und ggf. anderen) KI-Coding-Sandbox-Umgebungen kann der Schritt `secrets:history` (`scripts/secret-history-preflight.js`, nutzt `git cat-file --batch`/`--batch-check` über eine Pipe) hängen bleiben, obwohl das Repository klein ist (siehe `current-state.md`, Abschnitt 5, für die Reproduktion). Das ist bislang ausschließlich in dieser Art Sandbox beobachtet, nicht in reale GitHub-Actions-Läufen. **Vorgehen für KI-Agenten in einer Sandbox:** `npm run check`, `npm run secrets:check` und `npm test` einzeln ausführen (funktioniert zuverlässig) und `secrets:history` entweder auslassen und den Befund dokumentieren, oder — falls die Sandbox es erlaubt — mit großzügigem Timeout separat versuchen. Kein Grund, den Schritt aus der CI-Definition selbst zu entfernen; er bleibt für reale CI-Läufer aktiv.

## 5. Secrets

- Secrets ausschließlich über Environment-Variablen bzw. einen späteren Secret Store, niemals im Code, in Logs, Tickets oder allgemeiner Dokumentation (siehe `AGENTS.md`, Abschnitt 5).
- Bestehendes Muster im Node-Code: `deploy/systemd/systemone.env.example` als dokumentiertes, secret-freies Beispiel; echte Werte nur in einer nicht versionierten `systemone.env`. Dasselbe Muster (Beispieldatei versioniert, echte Werte nicht) gilt für alle zukünftigen Apps/Services.
- `npm run secrets:check` / `secrets:history` (Abschnitt 4) sind die bestehenden automatisierten Schutzmechanismen gegen versehentlich committete Secrets und bleiben für neue Verzeichnisse sinngemäß zu ergänzen bzw. auf das Gesamtrepository auszuweiten, sobald neue Ökosysteme hinzukommen.

## 6. Abhängigkeiten

- Bestehend: `mvp/systemone-pi/package-lock.json` ist versioniert, CI nutzt `npm ci` (reproduzierbar). Selftest `„Versioniertes Lockfile stimmt mit direkter Paketdefinition überein“` prüft das bereits automatisiert.
- Für neue Ökosysteme gilt dasselbe Prinzip verbindlich: Python/FastAPI mit gepinntem, versioniertem Lockfile (z. B. `uv.lock`/`poetry.lock`), Flutter mit versioniertem `pubspec.lock`, Docker-Images mit gepinnten Tags/Digests wo sinnvoll. Keine ungepinnten `latest`-Abhängigkeiten in Produktions-/CI-Pfaden.

## Definition-of-Done-Nachweis

Ein neuer Agent kann mit den in Abschnitt 2.1 gelisteten Befehlen den kompletten aktuellen Stand (`mvp/systemone-pi/`) eigenständig prüfen; die bestehende CI (Abschnitt 3) schlägt bei Lint-/Test-/Buildfehlern fehl. Für noch nicht existierende Apps/Services ist die verbindliche Erweiterungsregel (Abschnitt 2.2/3) statt einer bereits lauffähigen Prüfung hinterlegt, da diese Teile erst ab `S1V2-01-002` entstehen.
