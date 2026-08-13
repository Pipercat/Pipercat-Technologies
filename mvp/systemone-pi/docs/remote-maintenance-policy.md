# Fernwartungs-, Update- und Rollbackmodell

## MVP-Entscheidung

SystemONE Pi besitzt im MVP **keinen dauerhaft offenen Fernzugang**. Es gibt weder eingehende Cloud-Ports noch unbeaufsichtigte Support-Sessions. Diagnoseexport und Updates funktionieren lokal; eine spätere Fernwartung muss als separate, standardmäßig deaktivierte Funktion implementiert und erneut sicherheitsgeprüft werden.

## Freigabekette

1. Der lokale Administrator prüft vorab die Kategorien eines redigierten Diagnosepakets und exportiert es freiwillig.
2. Ein Updatepaket wird lokal oder über einen ausgehenden, TLS-gesicherten Abruf bereitgestellt. Transportvertrauen ersetzt niemals die Ed25519-Signaturprüfung.
3. SystemONE prüft Zielplattform, Version, Mindest-Core-Version, SHA-256 und Signatur.
4. Ein funktionales Update benötigt eine einmalige, protokollierte lokale Adminfreigabe.
5. Das Paket wird ausschließlich in den inaktiven A/B-Slot geschrieben. Nutzdaten bleiben in der getrennten Datenpartition.
6. Nach dem Boot bestätigen Healthcheck und Migrationstest den Candidate. Fehler, Zeitüberschreitung oder Stromausfall vor Bestätigung aktivieren automatisch den vorherigen Slot.

## Rollen und Einwilligung

- Nur die Rolle `administrator` darf funktionale Updates freigeben oder eine künftige Fernwartung starten.
- Display- und Gastrollen erhalten weder Schreib- noch Supportrechte.
- Eine Supportfreigabe wäre kurzlebig, einzeln widerrufbar und an einen sichtbaren lokalen Status gebunden. Dauerzugänge und geteilte Passwörter sind ausgeschlossen.
- Jede Freigabe, Aktivierung, Healthmeldung, Ablehnung und jeder Rollbackgrund gehört in das begrenzte, redigierte lokale Audit-Log.

## Ausfall- und Angriffsregeln

- Ungültige, alte, fremde oder manipulierte Pakete werden vor dem Schreiben abgewiesen.
- Fehlendes Netz beeinträchtigt weder Automationen noch lokales Backup/Restore.
- Bei unklarem Bootzustand gewinnt Verfügbarkeit: konservatives Rollback auf den bestätigten Slot.
- Private Schlüssel und Geräte-Credentials verlassen das Gerät nicht. Diagnosepakete enthalten keine Namen, Automationsinhalte, Tokens, Passwörter oder Recovery-Codes.
- Ein manueller Notfallzugriff erfordert physischen Zugriff und den separaten, einmal verwendbaren Recovery-Code.

## Betriebsnachweis vor Pilotfreigabe

- Signatur-, Manipulations-, Versions- und Rollenfälle automatisiert testen.
- A/B-Health-, Migrations- und simulierten Stromausfall testen.
- Auf Raspberry-Pi-Zielhardware Update, Neustart, Datenintegrität und Stromunterbrechung praktisch prüfen.
- Widerruf, Audit-Limit, TLS-Geräteidentität, Backup und Restore-Test gemeinsam abnehmen.

Bis dieser Hardware-Nachweis vorliegt, bleibt Fernwartung deaktiviert und das A/B-Modell als softwareseitig validiert, aber hardwareseitig offen gekennzeichnet.
