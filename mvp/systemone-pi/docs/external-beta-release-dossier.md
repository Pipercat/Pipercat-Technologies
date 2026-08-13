# SystemONE Pi – Freigabedossier externe Beta

Status: **Nicht freigegeben.** Dieses Dossier ist die verbindliche Go/No-Go-Akte für Aufgabe 48. `npm run release:audit` muss bis zum belegten Abschluss aller Gates mit Exitcode 1 enden.

## Freigabereihenfolge

1. Physischer Haushaltspilot 46 vollständig abschließen und Evidenz verlinken.
2. Familien-/Freundespilot 47 mit externen Testpersonen abschließen; offene P0/P1 schließen und erneut testen.
3. Ziel-Pi-, Hardware-, Backup-/Recovery- und Update-/Rollback-Evidenz in `release-evidence.json` nachtragen.
4. Externes Security-Review abschließen; Findings mit Schweregrad und Retest dokumentieren.
5. Rechts-/Steuerprüfung für Pilotvereinbarung, Haftung, Datenschutz, Rechnungs-/Leistungsmodell und Aufbewahrung dokumentieren. Fachliche Freigabe darf nicht durch eine technische Selbsteinschätzung ersetzt werden.
6. Benannte Unternehmensverantwortliche entscheiden anhand des grünen Audits über den Beta-Start.

## Pflichtunterlagen

- Pilotkunden-Checkliste und widerrufbare Einwilligung
- Installations-/Bedienungs-/Backup-/Recovery-Anleitung
- Geräte- und Firmwarematrix mit klarer Experimental-Kennzeichnung
- Supportzeiten, Kontaktweg, Schweregrade und Abbruch-/Rückbauprozess
- Update-, Signatur-, A/B-Rollback- und Backup-Restore-Nachweise
- Redigierter Diagnoseweg ohne Secrets oder private Inhalte
- Rechts-/Steuerfreigabe mit Datum, Prüferrolle und Dokumentverweis
- Go/No-Go-Protokoll mit Version, Datum, verantwortlicher Person und Rollbackentscheidung

## Startprotokoll

| Feld | Nachweis |
|---|---|
| Release/Commit | offen |
| Ziel-Pi und Image-Hash | offen |
| Audit `10/10` | offen |
| Security-Review | offen |
| Rechts-/Steuerfreigabe | offen |
| Pilot 46/47 | offen |
| Unternehmensfreigabe | offen |
| Start-/Abbruchdatum | offen |

## Harte No-Go-Regel

Kein Eintrag wird allein aufgrund vorhandener Implementierung auf `passed: true` gesetzt. Jeder Nachweis muss reproduzierbar, datiert und einer verantwortlichen Rolle zugeordnet sein. Ein offenes Gate, ein offenes P0/P1 oder ein fehlender Rückbauweg blockiert die externe Beta vollständig.
