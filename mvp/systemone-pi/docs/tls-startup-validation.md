# Fail-closed TLS-Startvalidierung

Stand: 13.08.2026 · Bearbeitet von: Pipercat Technologies

Wenn TLS aktiviert ist, initialisiert SystemONE den HTTPS-Server erst nach erfolgreicher Prüfung der lokalen Identitätsmetadaten, des Widerrufstatus, des privaten Schlüssels, des Zertifikats und ihrer kryptografischen Kompatibilität. Vorhandene Dateipfade allein gelten nicht als ausreichender Nachweis.

- Widerrufene Identität: `TLS_IDENTITY_REVOKED`.
- Beschädigtes, unlesbares oder nicht zusammenpassendes Schlüssel-/Zertifikatsmaterial sowie defekte Metadaten: `TLS_MATERIAL_INVALID`.
- Beide Fehler enden fail-closed mit `EX_CONFIG`/Exitcode 78; HTTP wird niemals ersatzweise aktiviert.
- Die Ausgabe nennt weder Dateipfade noch OpenSSL-Details, Schlüsselmaterial, Environmentwerte oder Stacktraces.
- `RestartPreventExitStatus=69 77 78` verhindert eine Neustartschleife. Nach Reparatur oder bewusster Erneuerung wird `systemctl restart systemone-pi` ausgeführt.

Ein gültiger HTTPS-Start muss danach `/api/v1/health` über TLS beantworten und kann mit `npm run tls:status` beziehungsweise der lokalen Systemidentitätsansicht kontrolliert werden.
