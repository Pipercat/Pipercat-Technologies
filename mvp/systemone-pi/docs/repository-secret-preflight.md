# SystemONE Pi – Repository-Secret-Preflight

`npm run secrets:check` liest ausschließlich mit Git versionierte Textdateien und blockiert bekannte Private-Key-, Anbieter-Token- und lange generische Credentialmuster. Treffer werden nur als Datei, Zeile und Regel ausgegeben; der erkannte Wert wird niemals wiederholt.

`npm run verify` führt diesen Preflight vor den Selftests aus. `.gitignore` sperrt Laufzeitdaten, Backups, echte Environment-Dateien, PEM-/Key- und PKCS#12-Dateien. Ausschließlich leere, dokumentierte `*.env.example`-Vorlagen dürfen versioniert werden.

## Bei einem Treffer

1. Commit/Push stoppen; Wert nicht in Ticket, Chat, Diagnose oder Screenshot kopieren.
2. Betroffenen Schlüssel beim Anbieter beziehungsweise lokalem Gerät sofort widerrufen oder rotieren.
3. Datei aus aktuellem Index und erforderlichenfalls aus der Git-Historie entfernen; dabei keine fremden Änderungen löschen.
4. Redigierte Vorfallnotiz mit Regel, Zeitraum, Rotation und Retest erfassen.
5. `npm run secrets:check`, `npm run verify` und gegebenenfalls externen Repository-Scan erneut ausführen.

Der lokale Musterabgleich ersetzt keinen serverseitigen GitHub-Secret-Scan, keine Historienanalyse und kein externes Security-Review. Frühere Commits und noch nicht bekannte Tokenformate benötigen separate Prüfung; das externe Security-Gate bleibt offen.
