# Lokale HTTPS- und Geräteidentität

Stand: 13.08.2026 · Bearbeitet von: Pipercat Technologies

## Lebenszyklus

1. Auf dem Ziel-Pi `npm run tls:provision` ausführen. Privater RSA-3072-Schlüssel und Metadaten werden lokal mit Modus `0600` erzeugt.
2. Den angezeigten SHA-256-Fingerabdruck über einen zweiten, vertrauenswürdigen Kanal vergleichen.
3. Zertifikat `data/tls/systemone-device.crt` einmalig auf dem Admin-Gerät als lokale Vertrauensanker-Datei installieren. Der private Schlüssel wird niemals exportiert.
4. Pilotserver mit `TLS_KEY_PATH=.../systemone-device.key TLS_CERT_PATH=.../systemone-device.crt npm start` betreiben. Cookies erhalten dann zusätzlich `Secure`.
5. Vor Ablauf `npm run tls:renew` ausführen, neuen Fingerabdruck prüfen und Zertifikat im Browser ersetzen.
6. Bei Verlust oder Gerätewechsel `npm run tls:revoke` ausführen, Session widerrufen und eine neue Identitätsgeneration provisionieren.

## Browser-Onboarding

- Nur `https://systemone.local:<port>` beziehungsweise den freigegebenen lokalen Namen verwenden.
- Zertifikatswarnungen nicht blind übergehen: Hostname und Fingerabdruck müssen zum lokalen Prüfprotokoll passen.
- Alte Zertifikate nach Erneuerung/Widerruf aus dem Browser-/Betriebssystem-Truststore entfernen.
- Ein Widerruf ist lokal testbar und blockiert den TLS-Start, bis eine neue Identität provisioniert wurde.
