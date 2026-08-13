# Release-Bundle und Provenienz

Stand: 13.08.2026 · Bearbeitet von: Pipercat Technologies

`npm run release:build` erzeugt aus einem sauberen, vollständig committen MVP-Arbeitsbaum ein deterministisches Archiv unter `dist/`. Der Build bricht bei lokalen Änderungen ab, damit Quell-Commit und Inhalt nicht auseinanderlaufen.

Zum Ergebnis gehören:

- `systemone-pi-<Version>-<Commit>.tar.gz` als unveränderlicher Slot-Inhalt,
- eine gleichnamige `.sha256`-Datei zur Transportprüfung,
- ein lesbares `.manifest.json` mit Schema, Ziel, Version, vollständigem Git-Commit, Commit-Zeitpunkt sowie Pfad, Modus, Größe und SHA-256 jeder versionierten Datei,
- dasselbe Manifest als `RELEASE-MANIFEST.json` im Archiv.

Nur reguläre, mit Git versionierte Dateien unter `mvp/systemone-pi` werden aufgenommen. `node_modules`, `dist`, Laufzeitdaten, Backups, Environment-Dateien und Schlüssel sind dadurch ausgeschlossen; der Secret-Preflight bleibt zusätzlich verpflichtend. Pfade mit Traversal, absolute Pfade, Symlinks und nicht portable überlange Namen werden abgewiesen.

Vor dem Schreiben in den inaktiven A/B-Slot werden die externe Archivprüfsumme und danach alle Dateihashes des eingebetteten Manifests geprüft. Der vollständige `sourceCommit` wird gemeinsam mit aktivem Slot und gestarteter Version protokolliert. Das Bundle ersetzt nicht die Ed25519-Signatur: Für Pilot und Beta muss das Archiv zusätzlich als Payload des signierten SystemONE-Updateformats verteilt und lokal freigegeben werden.

Nach dem Entpacken wird `npm ci --omit=dev --ignore-scripts` und anschließend `npm run release:verify` ausgeführt. Dieser installierbare Prüfbefehl kontrolliert Syntax, Funktionstests und jede Manifestdatei ohne ein `.git`-Verzeichnis oder Dateien außerhalb des MVP-Bundles vorauszusetzen. Repository-externe CI-Verträge werden ausschließlich im vorherigen Quelllauf geprüft. `npm run verify` bleibt der stärkere Quellrepository-Preflight mit aktuellem und historischem Secret-Scan und muss bereits vor `release:build` erfolgreich sein; er ist bewusst nicht der Slot-Prüfbefehl.
