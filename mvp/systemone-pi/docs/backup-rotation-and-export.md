# Rotierende Backups und externer Export

SystemONE legt standardmäßig täglich ein atomares Backup unter dem lokalen Datenverzeichnis ab und prüft es direkt vollständig, ohne den laufenden Zustand zu verändern. `BACKUP_RETENTION_COUNT` (Standard 7), `BACKUP_RETENTION_DAYS` (Standard 30) und `BACKUP_INTERVAL_MS` konfigurieren Rotation und Intervall.

USB- oder NAS-Verzeichnisse müssen vor dem Start explizit über die plattformabhängig mit `path.delimiter` getrennte Variable `SYSTEMONE_EXPORT_ROOTS` freigegeben werden. Beliebige Client-Pfade und Pfadwechsel werden abgewiesen. Optional verschlüsselt SystemONE Exporte mit AES-256-GCM, zufälligem Salt/IV und scrypt-Schlüsselableitung; Passphrasen benötigen mindestens zwölf Zeichen.

Der vollständige JSON-Export über `GET /api/backup` ist vor dem ersten Admin-Pairing gesperrt und benötigt danach bei jedem Abruf eine gültige lokale Session mit `system:read`. Dadurch können Räume, Gerätenamen und Einstellungen weder von einem ungekoppelten Gerät noch von einem abgelaufenen Browserkontext exportiert werden.

Jede lokale Sicherung durchläuft unmittelbar `validateBackup`, Prüfsummenprüfung und Zusammenfassung. Fehler erscheinen mit einem stabilen Code und einer verständlichen Meldung in Diagnose und App. Ein Restore wird nur über den bestehenden, separat bestätigten Restore-Ablauf ausgeführt.
