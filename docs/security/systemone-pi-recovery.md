# SystemONE Pi · Recovery-Konzept

Stand: 13. August 2026 · MVP-Spezifikation

## Sicherheitsziel

Ein QR-Sticker, ein Foto des Geräts oder Zugriff auf das lokale Netz reichen niemals zur Übernahme. Recovery verlangt gleichzeitig:

1. physischen Zugriff auf den SystemONE Pi und eine bewusst ausgelöste Hardware-Aktion;
2. den separaten, einmalig bei der Ersteinrichtung ausgegebenen Recovery-Code.

Der Code wird mit mindestens 80 Bit Zufall erzeugt. Lokal wird nur ein `scrypt`-Hash mit individuellem Salt und Dateirechten `0600` gespeichert. Nach fünf Fehlversuchen wird Recovery gesperrt. Ein erfolgreicher Code wird verbraucht und nach der Wiederherstellung ersetzt.

## Geplanter physischer Ablauf

1. Eigentümer hält die Recovery-Taste am eingeschalteten Pi zehn Sekunden gedrückt.
2. Die Statusanzeige signalisiert ein zeitlich begrenztes lokales Recovery-Fenster.
3. Die App verbindet sich im selben lokalen Netz und fordert den separaten Recovery-Code an.
4. Das System prüft Hardware-Signal und Code gemeinsam und in konstanter Zeit.
5. Alte Sessions werden widerrufen, ein neuer Owner wird lokal gekoppelt und ein neuer Recovery-Code wird einmalig angezeigt.

Bis eine echte Pi-Taste bzw. ein sicherer Hardware-Ersatz integriert und physisch getestet ist, bleibt die Recovery-API deaktiviert. Ein Software-Flag oder QR-Code allein darf die physische Bestätigung nicht ersetzen.

## Verlustszenarien

- **App/Telefon verloren:** Mit physischem Pi und Recovery-Code neuen Owner koppeln; alle alten Sessions widerrufen.
- **Recovery-Code verloren, Owner-Session vorhanden:** Nach erneuter lokaler Bestätigung einen neuen Code erzeugen und den alten invalidieren.
- **Telefon und Code verloren:** Nur Werksreset mit physischem Zugriff; keine Hintertür und kein Cloud-Support-Override.
- **Pi verloren oder gestohlen:** Keine Remote-Recovery. Datenträgerverschlüsselung ist vor dem externen Pilot ein separates Release-Gate.

## Werksreset

Der Werksreset benötigt eine dokumentierte lange Hardware-Aktion mit zweiter Bestätigung. Er löscht Sessions, Rollen, Integrations-Credentials, Recovery-Hash, Räume, Geräte, Automationen und lokale Backups. Die Software zeigt vorher klar an, dass die Aktion nicht rückgängig gemacht werden kann. Ein QR-Sticker löst niemals einen Reset aus.

## Datenabgrenzung

Recovery-Code und -Hash dürfen weder im API-State noch in Diagnose, Log, Telemetrie oder Backup erscheinen. Diagnosefelder mit `recovery`, `token`, `secret`, `credential`, `password` oder `username` werden rekursiv redigiert. Backup-Export besitzt eine Positivliste und übernimmt Recovery-Daten nicht.
