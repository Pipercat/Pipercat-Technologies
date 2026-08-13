# Signiertes SystemONE-Updateformat

Stand: 13.08.2026 · Bearbeitet von: Pipercat Technologies

- Format: JSON-Hülle `systemone-update`, Manifest-Schema 1, Base64-Payload, SHA-256-Payloadhash und Ed25519-Signatur.
- Signiert werden das kanonisch sortierte Manifest und der Payloadhash. Manipulation an Manifest oder Payload macht das Paket ungültig.
- Der private Release-Schlüssel wird ausschließlich offline gehalten. Auf dem Pi liegt nur der über `UPDATE_PUBLIC_KEY` konfigurierte öffentliche Vertrauensschlüssel.
- Vor Freigabe werden Ziel `systemone-pi`, strikt höhere SemVer-Version und `minCoreVersion` geprüft.
- Funktionale Updates werden nach erfolgreicher Prüfung nicht automatisch installiert. Ein authentifizierter Owner/Administrator muss eine einmalige lokale Freigabe erzeugen.
- Online- und Offline-Transport verwenden dasselbe Paket und dieselbe Verifikation; der Transport selbst ist nicht vertrauenswürdig.
- Dieser Prototyp validiert und genehmigt Pakete. Atomare Installation und Rollback folgen in der nächsten Betriebseinheit.
