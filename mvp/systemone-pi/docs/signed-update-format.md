# Signiertes SystemONE-Updateformat

Stand: 13.08.2026 · Bearbeitet von: Pipercat Technologies

- Format: JSON-Hülle `systemone-update`, Manifest-Schema 1, Base64-Payload, SHA-256-Payloadhash und Ed25519-Signatur.
- Signiert werden das kanonisch sortierte Manifest und der Payloadhash. Manipulation an Manifest oder Payload macht das Paket ungültig.
- Der private Release-Schlüssel wird ausschließlich offline gehalten. Auf dem Pi liegt nur der über `UPDATE_PUBLIC_KEY` konfigurierte öffentliche Vertrauensschlüssel.
- Vor Freigabe werden Ziel `systemone-pi`, strikt höhere SemVer-Version und `minCoreVersion` geprüft.
- Funktionale Updates werden nach erfolgreicher Prüfung nicht automatisch installiert. Ein authentifizierter Owner/Administrator muss eine einmalige lokale Freigabe erzeugen.
- Die Freigabe-ID und der Payloadhash werden beim Staging atomar und persistent als verbraucht gespeichert. Dieselbe Freigabe (`UPDATE_APPROVAL_REPLAY`) oder dasselbe signierte Paket mit neuer Freigabe (`UPDATE_PAYLOAD_REPLAY`) kann auch nach Prozessneustart nicht erneut angenommen werden. Ein bereits gestagter/candidate Slot oder ausstehender Boot-Healthcheck blockiert parallele Zyklen.
- Online- und Offline-Transport verwenden dasselbe Paket und dieselbe Verifikation; der Transport selbst ist nicht vertrauenswürdig.
- Der Payload ist das mit `npm run release:build` erzeugte, inventarisierte Release-Bundle. Archivprüfsumme, eingebettetes Dateimanifest und `sourceCommit` verbinden die Signatur mit dem tatsächlich installierten Slot-Inhalt.
- Nach gültiger Ed25519-Signatur wird der Payload als begrenztes Gzip/Tar geöffnet. Header-Prüfsummen, reguläre Dateitypen, sichere Pfade, eindeutige Einträge, Abschlussblöcke, fehlende Folgedaten und vollständige Hash-/Modus-/Größeninventur werden geprüft. Beliebiger signierter Text, Zusatzdateien oder Archive mit versteckten Folgedaten werden abgewiesen.
- Version und Ziel des eingebetteten Release-Manifests müssen exakt dem signierten Update-Manifest entsprechen. Die lokale Vorschau zeigt vor der Freigabe Quell-Commit und Anzahl vollständig geprüfter Dateien.
- Atomare Installation und Rollback folgen dem dokumentierten A/B-Zustandsautomaten; der reale Ziel-Pi-Nachweis bleibt ein separates Freigabegate.
