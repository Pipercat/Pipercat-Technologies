# Repository-Bestandsaufnahme (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-00-002 · Bestehendes Repository vollständig inventarisieren und sicheren Ausgangspunkt festhalten`.
> Siehe [`AGENTS.md`](../AGENTS.md) für die verbindlichen Arbeitsregeln, die auf dieser Analyse aufbauen.

## 0. Zusammenfassung

Es gibt aktuell **zwei nicht kompatible „aktuelle Wahrheiten“**, die vor jeder weiteren Implementierung sauber getrennt werden müssen:

1. **Repository-Zustand** (Branch `mvp/systemone-pi-v0.1`): ein ausgereifter, aber bewusst eigenständiger **Node.js-Monolith** (`mvp/systemone-pi/`) nach `ADR-0001` (13.08.2026) — kein Home Assistant, kein MQTT, keine Datenbank, kein Flutter-Client, kein Docker. 295/295 hardwarefreie Selftests, produktionsnahe Sicherheitsarbeit (TLS, Sessions/Rollen/CSRF, signierte A/B-Updates, verschlüsselte Backups).
2. **Notion-Zustand** (Entscheidungslog `DEC-4`, Aufgabe `S1-03-001`, neuer 105-Punkte-Plan `2026-08 Neuaufbau`, alle 17.08.2026): ein **verbindlich festgelegter neuer Stack** — Flutter (Client), FastAPI (Backend/API), PostgreSQL, Debian, Docker Compose, MQTT — mit **Home Assistant als verpflichtender, für den Endkunden unsichtbarer Integrationsschicht** unterhalb von Device Model/Capability Layer/Registry. Alle 105 Aufgaben des neuen Plans stehen auf `Not started`.

Das ist **kein ungeklärter Widerspruch**, der eine Rückfrage erfordert — die Entscheidung für den neuen Stack ist in Notion eindeutig und aktueller als `ADR-0001` (siehe [Quellenhierarchie in `AGENTS.md`](../AGENTS.md#1-fachliche-quelle)). Es ist aber ein **vollständiger Technologiewechsel**, der im Repository selbst noch nirgends nachvollzogen ist: Es existiert kein `ADR-0002`, keine FastAPI-/Flutter-/PostgreSQL-/Docker-Datei im Repo, und die im Notion-Task `S1-03-001` beschriebene, angeblich bereits lokal committete Architekturentscheidung (Commit `8e7325b` auf Branch `claude/github-repo-access-a4pcqt`) existiert **nicht** auf GitHub und **nicht** in diesem Arbeitsverzeichnis (verifiziert: Branch existiert weder lokal noch remote, `docs/architecture/adr-0002-*` existiert nicht). Diese Arbeit ist bislang ausschließlich als Notion-Aufgabentext dokumentiert, nicht als Code/Doku im Repository.

**Empfehlung für den weiteren Fahrplan:** Der bestehende Node.js-Code wird nicht gelöscht (er ist funktionierender, getesteter Referenzcode für Domänenlogik, Sicherheitsmuster und Testfälle), aber er ist **nicht** die Grundlage, auf der die neuen `S1V2-*`-Aufgaben aufbauen. Ab `S1V2-01-002` („Repository in klar getrennte Apps, Services und gemeinsame Pakete strukturieren“) entsteht voraussichtlich eine neue Verzeichnisstruktur (z. B. `apps/`, `services/`, `packages/`) parallel zu `mvp/systemone-pi/`. Einzelne Muster (Rollen-/Session-Modell, Audit-Log-Felder, Backup-Verschlüsselung, Update-/Rollback-State-Machine, Security-Header/CSRF-Ansatz) sollten als **Vorlage migriert**, nicht 1:1 als Node.js-Code übernommen werden.

## 1. Projektstruktur (Ist-Zustand)

```
Pipercat-Technologies/
├── README.md, ROADMAP.md, IMPLEMENTATION_STATUS.md, FOUNDER_QUESTIONS.md, AGENTS.md
├── branding/README.md
├── docs/
│   ├── architecture/   (adr-0001-systemone-pi-pilot.md, overview.md — beide teilweise überholt)
│   ├── company/, products/, pricing/, legal/, security/, release/
│   └── current-state.md   (dieses Dokument)
├── .github/workflows/systemone-pi-mvp.yml   (einziger CI-Workflow)
└── mvp/systemone-pi/    ← der eigentliche, lauffähige Code
    ├── package.json (name: systemone-pi-mvp, version 0.4.0, Node >=20, einzige Dependency: qrcode)
    ├── server.js, lib/ (49 Dateien), web/ (vanilla-JS PWA, kein Framework), scripts/ (10 Dateien inkl. selftest.js)
    ├── deploy/systemd/ (systemone-pi.service, systemone.env.example)
    ├── docs/ (29 produktnahe Doku-Dateien)
    ├── data/, data-live/, data-live-camera/ (laufzeit, .gitignored)
    ├── data.stale-20260816-105100/, data.stale-20260816-130242/ (siehe 6.3)
    └── dist/ (lokale Build-Artefakte, .gitignored, nicht versioniert)
```

Kein Flutter-Code (`pubspec.yaml`/`*.dart`: 0 Treffer), kein Python-/FastAPI-Code (`requirements.txt`/`*.py`: 0 Treffer), kein `Dockerfile`/`docker-compose.yml` (0 Treffer), kein PostgreSQL, kein MQTT (`mqtt`: 0 Treffer) irgendwo im Repository.

## 2. Backend/Runtime (Ist)

- **Laufzeit:** einzelner Node.js-Prozess, `server.js`, gestartet via `node server.js`; kein Express/Fastify/Koa — nutzt Node-Bordmittel `http`/`https`/`tls` (`lib/tls-server.js`, `lib/http-routing.js`, `lib/request-body.js`).
- **Persistenz:** dateibasiert, JSON, atomares Schreiben (temp+rename), `.bak`-Wiederherstellung, fsync — `lib/storage.js` (`LocalStorage`). Keine SQL-Datenbank.
- **Geräteintegration:** normalisiertes Device Model + Capability-Layer + Registry + austauschbare Adapter (`lib/adapter.js` als abstrakte Basis). Implementierte Adapter: Hue (`lib/hue.js`, `HUE_MODE=simulation|real`, Standard `simulation`), Govee (`lib/govee.js`, `real`-Modus wirft bewusst `GOVEE_HARDWARE_NOT_RELEASED`), interner `simulation.js`-Adapter. **Kein HomeAssistantAdapter vorhanden.**
- **Module:** Kamera/ONVIF (`lib/camera-module.js`, Simulation liefert generiertes SVG-Platzhalterbild, echter RTSP-Pfad wirft `CAMERA_STREAM_GATEWAY_REQUIRED`), Pi-hole (`lib/pihole-module.js`, Simulation liefert Fixture-Werte), YouDo-Hooks (`lib/module-registry.js`, `createYouDoModules()` — Navigations-/Card-Manifest-Hooks hinter Feature-Flags, keine vollständige Kalender-/Aufgabenfunktion).
- **Automation:** `lib/automations.js`, `lib/scheduler.js`, `lib/solar.js` — lokale Trigger/Bedingungen/Aktionen, Sonnenzeiten, Verlauf.

## 3. Auth, Security, Audit (Ist)

- **Sessions/Rollen:** `lib/local-sessions.js` (`LocalSessionStore`) — Rollen `owner`, `administrator`, `member`, `guest`, `display` mit granularen Permission-Sets, SHA-256-gehashte Tokens, 12 h TTL.
- **Admin-Pairing:** `lib/admin-pairing.js` — QR-basiert, 5 Min TTL, 6-stelliger Code, Rate-Limit nach 5 Fehlversuchen.
- **Web-Security:** `lib/web-security.js` — Security-Header (CSP, X-Frame-Options), Host-Allowlist (localhost/`.local`/RFC1918), CSRF-Schutz für schreibende Requests (`validateWriteRequest`), Bootstrap-Schreibsperre vor Admin-Pairing (`assertBootstrapWrite`), `RateLimiter`.
- **Owner-Recovery:** `lib/recovery-code.js`, `lib/recovery-manager.js`.
- **TLS:** `lib/tls-identity.js`, `lib/tls-server.js` — TLS-Pflicht, kein HTTP-Fallback, fail-closed bei ungültigem Material.
- **Audit-Log:** `lib/audit-log.js` — In-Memory-Ringpuffer (Limit 500), redigiert Secrets/Tokens in Pfaden, Actor nur als ID+Rolle. **Keine Persistenz auf Platte** — bei Prozessneustart geht der Audit-Verlauf verloren. Das ist eine reale Lücke gegenüber der neuen Aufgabe `S1V2-02-014 · Manipulationsgeschützten Audit-Log-Kern implementieren`, die einen persistenten, manipulationsgeschützten Audit-Kern verlangt.
- **Backup:** `lib/backup.js` + `lib/backup-manager.js` — AES-256-GCM, scrypt-KDF, Rotation (Anzahl/Alter), eingeschränkte Exportziele (`SYSTEMONE_EXPORT_ROOTS`), `testRestore()`.
- **Updates/Rollback:** `lib/update-package.js` (signierte Bundles, SemVer, Hash-Prüfung, Replay-Schutz, Admin-Freigabe) + `lib/update-slots.js` (A/B-State-Machine, Health-Check-Deadline, automatischer Rollback, Recovery nach Stromausfall mitten im Boot).

Diese Sicherheitsmuster sind qualitativ hochwertig und sollten als **Referenz** in die neue FastAPI-/PostgreSQL-Implementierung übernommen werden (Konzepte, nicht 1:1 Code).

## 4. CI/CD (Ist)

`.github/workflows/systemone-pi-mvp.yml`: einziger Workflow, getriggert auf `pull_request`/`push` mit `paths: mvp/systemone-pi/**`. Schritte: `actions/checkout` → `actions/setup-node@v4` (Node 20, npm-Cache über `package-lock.json`) → `npm ci --ignore-scripts` → `npm run verify`. `verify` = `check && secrets:check && secrets:history && test`. Kein Deployment-Schritt, kein Docker-Build, keine Postgres-Migration in CI (folgerichtig, da es diese Komponenten im Repo noch nicht gibt).

## 5. Testbaseline

- **Testwerkzeug:** ein einziger, abhängigkeitsfreier Custom-Test-Runner, `mvp/systemone-pi/scripts/selftest.js` (122.814 Bytes, 295 `await test(...)`-Aufrufe). Kein Jest/Mocha.
- **Befehl:** `npm test` → `node scripts/selftest.js`; `npm run verify` → Syntax-Check aller `lib/`/`web/`/`scripts/`-Dateien + Secret-Preflight + Secret-History-Scan (volle Git-Historie) + `npm test`.
- **Ausgeführt am 17.08.2026** in `mvp/systemone-pi/`:
  - `npm run check` → **bestanden** (Syntax-Check `server.js` + alle `lib/*.js`/`web/*.js`/`scripts/*.js`).
  - `npm run secrets:check` → **bestanden** („103 versionierte Dateien, keine Secretmuster“).
  - `npm run secrets:history` (`scripts/secret-history-preflight.js`, scannt alle Git-Blobs über alle Refs via `git cat-file --batch`) → **in dieser Sandbox/Arbeitsumgebung hängengeblieben und nach ca. 10 Minuten manuell abgebrochen**. Reproduziert: bereits ein isoliertes `git rev-list --objects --all | git cat-file --batch-check=...` hängt in dieser Shell-Umgebung, obwohl `git count-objects` nur ~1.400 kleine Objekte meldet und ein einfaches `git rev-list --objects --all` selbst unter 0,2 s läuft. Das deutet auf eine Besonderheit der stdin/stdout-Pipe-Behandlung von `git cat-file --batch(-check)` in diesem Sandbox-Bash-Tool hin, nicht auf ein Problem des Scripts oder Repos selbst — der zugehörige Selftest `„Historien-Script nutzt Git-Refs Batchzugriff und Größenlimit“` ist Teil der unten grün gelaufenen 295 Tests und die GitHub-Actions-CI (andere Laufzeitumgebung) führt laut `.github/workflows/systemone-pi-mvp.yml` denselben Schritt regulär als Teil von `npm run verify` aus. **Zu prüfen/offen:** ob dieses Sandbox-Verhalten auch reale Zielumgebungen (Pi-Systemd-Dienst, spätere CI-Läufer) betreffen könnte — für diese Aufgabe kein Blocker, da es sich um ein lokales KI-Werkzeugverhalten und nicht um einen Repo-Fehler handelt.
  - `npm test` (`node scripts/selftest.js`, isoliert von `secrets:history` ausgeführt) → **295/295 Tests bestanden**, deckungsgleich mit der Angabe in `IMPLEMENTATION_STATUS.md`.
- Es gibt kein separates `test/`-Verzeichnis, keine Integrationstest-Suite gegen eine echte Datenbank (da keine existiert), keine E2E-Browsertests (nur dokumentierte manuelle Pilot-Runbooks unter `mvp/systemone-pi/docs/`).

## 6. Technische Schulden / Auffälligkeiten

### 6.1 Fehlender persistenter Audit-Log
`lib/audit-log.js` ist rein In-Memory. Für ein Sicherheitsprodukt mit „manipulationsgeschütztem Audit-Log“ als explizitem Ziel (`S1V2-02-014`) ist das im neuen Stack zwingend nachzuziehen (z. B. append-only PostgreSQL-Tabelle mit Hash-Chain).

### 6.2 Unklare `.gitignore`-Lücke
`mvp/systemone-pi/.gitignore` ignoriert `data/`, `data-live/`, `data-live-camera/`, aber **kein** Muster für `data.stale-*`. Dadurch tauchen die beiden unten genannten Verzeichnisse als untracked Dateien in `git status` auf.

### 6.3 Stale lokale Laufzeitdaten (untracked, enthalten sensible Daten)
- `mvp/systemone-pi/data.stale-20260816-105100/`
- `mvp/systemone-pi/data.stale-20260816-130242/`

Beide enthalten `.camera-key`, `sessions.json` (Sessiontokens), `state.json`, teils `recovery-record.json` — offensichtlich Snapshots aus lokalen Testläufen (`pilot:dry-run` o. ä.), keine Produktivdaten. **Nicht committen.** Empfehlung: lokal löschen oder mit `.gitignore`-Muster `data.stale-*` dauerhaft ausschließen, sobald die verantwortliche Person das bestätigt (nicht eigenmächtig gelöscht, siehe Sicherheitshinweis: könnten in-progress lokale Diagnosearbeit sein).

### 6.4 Unversionierte, wiederholte lokale Build-Artefakte
`mvp/systemone-pi/dist/` enthält 6 Sätze `systemone-pi-0.4.0-*.tar.gz(.sha256)/.manifest.json` (~1 MB) aus wiederholten lokalen `npm run release:build`-Läufen. Korrekt `.gitignore`d, aber lokal nicht aufgeräumt — kein Repository-Risiko, nur Datenträger-Hygiene.

### 6.5 Nicht auf GitHub vorhandene Architekturentscheidung
Notion-Aufgabe `S1-03-001` behauptet einen lokalen Commit `8e7325b` auf Branch `claude/github-repo-access-a4pcqt` mit `ADR-0002` (Home-Assistant-Backbone). Dieser Branch/Commit ist **weder lokal noch auf `origin`** vorhanden (geprüft per `git fetch --prune` + `git branch -a`). Die Arbeit existiert nach aktuellem Stand nur als Notion-Aufgabentext, nicht im Code. `ADR-0002` muss im Rahmen von `S1V2-01-001` neu geschrieben werden.

### 6.6 Bewusste Simulationsgrenzen (dokumentiert, kein verstecktes Risiko)
Hue, Govee, Kamera/ONVIF und Pi-hole laufen alle standardmäßig im `simulation`-Modus; reale Hardwarepfade sind teils im Code aktiv blockiert (`GOVEE_HARDWARE_NOT_RELEASED`, `CAMERA_STREAM_GATEWAY_REQUIRED`). Das ist laut `IMPLEMENTATION_STATUS.md` und den jeweiligen `docs/*.md`-Dateien bewusst so vorgesehen (echte Hardwarevalidierung ist im alten Pilotplan ein offener, separater Schritt) — im neuen Plan wird dieser gesamte Pfad ohnehin durch `HomeAssistantAdapter`-Aufgaben (`S1V2-02-016` ff.) ersetzt.

### 6.7 Keine offenen `TODO`/`FIXME`-Marker
`lib/`, `docs/`, `scripts/`, `web/` enthalten keine `TODO`/`FIXME`/`XXX`-Kommentare. „Nicht implementiert“ kommt nur als bewusste Abstract-Method-Guards in `lib/adapter.js` vor. Guter Ausgangszustand für sauberen Cutover.

## 7. Home Assistant / MQTT / Flutter / FastAPI / PostgreSQL / Docker — explizit: nichts vorhanden

Grep- und Find-Suchen über das gesamte Repository (Code + Doku) bestätigen für alle sechs Kernbausteine des neuen Stacks: **0 Implementierungstreffer**, nur Erwähnungen in Doku/ADR, die den jeweiligen Baustein für den *alten* Pilotplan explizit ausschließen (`ADR-0001`: „Home Assistant ist kein unmittelbarer Bestandteil…“, „PostgreSQL ist für den Pi-Pilot nicht erforderlich“; `ROADMAP.md`: „Eine Home-Assistant-, FastAPI- oder PostgreSQL-Migration ist kein paralleler Pilotpfad“; `docs/architecture/overview.md`: „FastAPI/PostgreSQL nur als spätere Neubewertung; Flutter nur als möglicher Client“).

## 8. Empfohlene Behandlung bestehenden Codes

| Bereich | Empfehlung | Begründung |
|---|---|---|
| `mvp/systemone-pi/lib/local-sessions.js`, `web-security.js`, `admin-pairing.js`, `recovery-*.js` | **Als Vorlage migrieren** | Rollenmodell/CSRF/Rate-Limiting/Pairing-Konzepte direkt auf FastAPI-Äquivalente übertragbar |
| `lib/backup-manager.js`, `lib/update-package.js`, `lib/update-slots.js` | **Als Vorlage migrieren** | Verschlüsselungs-/Rotations-/A-B-Rollback-Logik ist stackunabhängig wertvoll, muss aber auf PostgreSQL/Docker-Umgebung übertragen werden |
| `lib/device-model.js`, `capabilities.js`, `device-registry.js`, `adapter.js` | **Konzeptionell erhalten, technisch ersetzen** | Domänenmodell bleibt sinnvoll, muss aber `HomeAssistantAdapter` als einzige produktive Integrationsgrenze bekommen (`S1V2-02-016`) statt Direktadapter |
| `lib/hue.js`, `govee.js`, `camera-module.js`, `pihole-module.js`, `module-registry.js` (YouDo) | **Als Referenz behalten, nicht direkt weiterführen** | Werden im neuen Plan durch HA-vermittelte Integrationen bzw. eigene `S1V2-06-*`-Aufgaben ersetzt |
| `web/` (vanilla-JS-PWA) | **Behalten als Übergangs-UI, kein neuer Ausbau** | Ersetzt durch Flutter-Client; bis dahin ggf. weiter nutzbar für lokale Vorschau |
| `scripts/selftest.js` (295 Tests) | **Als Testfall-Fundus behalten** | Viele Testfälle (Security-Negativtests, Recovery-Pfade) sind fachlich wiederverwendbar, auch wenn die Implementierung wechselt |
| `deploy/systemd/*` | **Als Referenz behalten** | Muss um Docker-Compose-/Debian-Deployment ergänzt bzw. abgelöst werden, sobald `S1V2-01-*`/Deployment-Aufgaben greifen |
| `docs/architecture/adr-0001-*.md`, `overview.md`, `ROADMAP.md` (Abschnitt „Priorisiertes MVP“) | **Als überholt kennzeichnen, nicht löschen** | Wird durch neue Architekturdokumentation aus `S1V2-01-001` ersetzt; bleibt als historische Begründung sichtbar |
| `mvp/systemone-pi/data.stale-*/` | **Lokal bereinigen** (siehe 6.3) | Keine Repository-relevanten Daten, aber sensibel (Sessiontokens) |

## 9. Offene Punkte für die nächste Aufgabe

- `S1V2-00-003` (Projektmanifest) muss den in Abschnitt 0/3 beschriebenen Technologiewechsel explizit als Migrationskontext benennen, nicht nur den Zielzustand.
- `S1V2-01-001` (Zielarchitektur final dokumentieren) muss `ADR-0001` offiziell als teilweise ersetzt markieren und ein neues `ADR-0002` (Home-Assistant-Backbone, analog zum in Notion beschriebenen, aber nie gepushten Commit) im Repository nachziehen.
- Kein technischer Blocker identifiziert, der eine Rückfrage an die verantwortliche Person vor Beginn von `S1V2-00-003` erfordert.
