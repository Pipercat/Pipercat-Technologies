# Lokale API-Transportgrenzen

Stand: 13.08.2026 · Bearbeitet von: Pipercat Technologies

SystemONE begrenzt JSON-Anfragen bytegenau, bevor JSON geparst oder kryptografisch geprüft wird:

- Standardendpunkte: 256 KiB,
- Backup-Validierung und -Restore: 8 MiB,
- signierte Updateprüfung und -freigabe: rund 21,6 MiB für ein maximal 16 MiB großes, Base64-kodiertes Release-Archiv plus JSON-Hülle.

Ein deklarierter `Content-Length` oberhalb des Endpunktlimits wird vor dem Puffern abgewiesen. Bei chunked Transfer stoppt der Parser nach Überschreitung, entfernt seine Pufferlistener und drainiert den restlichen Request kontrolliert, damit kein unbegrenzt wachsender String im Prozess verbleibt. UTF-8 wird in Bytes statt JavaScript-Zeichen gezählt. Ungültiges JSON, fehlerhafte Längenfelder, Streamfehler und vorzeitig abgebrochene Anfragen erhalten getrennte Fehlercodes; Übergröße liefert HTTP 413 mit `REQUEST_BODY_TOO_LARGE`.

Die Transportgrenze ersetzt nicht die strengere Inhaltsprüfung: Updates durchlaufen anschließend Base64-, Payloadhash-, Ed25519-, Gzip/Tar-, Inventar- und Versionsprüfung. Backups werden anschließend vollständig gegen Format, Schema und Prüfsumme validiert.
