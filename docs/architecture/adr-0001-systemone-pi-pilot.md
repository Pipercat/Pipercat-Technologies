# ADR-0001: SystemONE-Pi-Pilotarchitektur

- Status: angenommen
- Datum: 13. August 2026
- Geltungsbereich: geschlossener SystemONE-Pi-Pilot und Branch `mvp/systemone-pi-v0.1`

## Kontext

Die ältere Zielarchitektur und Roadmap nennen Home Assistant, FastAPI, PostgreSQL und Flutter als mögliche Plattformbausteine. Im Repository existiert inzwischen ein getesteter lokaler Pilot auf Node.js mit eigener Weboberfläche, dateibasierter atomarer Persistenz, normalisiertem Gerätemodell sowie Adapter-, Automations-, Backup- und Diagnoseschichten.

Eine parallele Neuentwicklung auf einem zweiten Stack würde den Pilot verzögern, Sicherheitsarbeit duplizieren und die bereits getesteten Fehlerpfade entwerten. Für den geschlossenen Pilot wird deshalb eine verbindliche Architektur benötigt.

## Entscheidung

Der SystemONE-Pi-Pilot bleibt bis zur Pilotfreigabe ein modularer Node.js-Monolith mit lokaler Weboberfläche.

- Laufzeit: Node.js 20 oder neuer.
- Bereitstellung: ein lokaler Dienst auf dem SystemONE Pi.
- Oberfläche: mobile SystemONE-App-UX als erste Produktoberfläche; die lokal ausgelieferte Webhülle dient zunächst nur als interaktive Entwicklungsvorschau. Eine eigenständige Desktop-Web-App folgt später. Herstellertechnik bleibt hinter Adaptern verborgen.
- API: lokale HTTP-JSON-API mit einheitlichem `success/data/error`-Antwortformat. TLS, Sessions, Rollen und CSRF-Schutz werden vor einem Pilot außerhalb der isolierten Entwicklungsumgebung ergänzt.
- Persistenz: lokale, atomar geschriebene und wiederherstellbare Zustandsdateien. PostgreSQL ist für den Pi-Pilot nicht erforderlich.
- Geräteintegration: normalisiertes Device Model, Capability-Layer, Registry und austauschbare Adapter. Philips Hue ist der erste freizugebende vertikale Hardwarepfad.
- Ereignisse: interne Registry-Ereignisse bleiben die Quelle; ein normalisierter lokaler Client-Ereignisstrom wird ergänzt. Herstellerdaten dürfen den öffentlichen Vertrag nicht verlassen.
- Backup und Diagnose: lokal, versioniert, validiert und secret-redigiert.
- Cloud: keine zentrale Control Plane und keine Abhängigkeit des lokalen Kernbetriebs von Pipercat-Diensten.

## Rolle von Home Assistant

Home Assistant ist kein unmittelbarer Bestandteil und keine sichtbare Abhängigkeit des geschlossenen Pi-Piloten. Der erste Hue-Pfad wird direkt über den SystemONE-Adapter umgesetzt.

Eine spätere Home-Assistant-Schicht ist nur als optionaler, vollständig verborgener Adapter zulässig. Sie darf weder das SystemONE-Gerätemodell umgehen noch für Start, Bedienung, Backup oder Wiederherstellung des lokalen Kerns erforderlich sein. Der Import bestehender Home-Assistant-Installationen bleibt außerhalb des MVP.

## Rolle von FastAPI, PostgreSQL und Flutter

- FastAPI und PostgreSQL sind mögliche spätere Bausteine für Server-, Rack- oder Control-Plane-Produkte, aber keine Voraussetzung des Pi-Piloten.
- Flutter bleibt die bevorzugte Technologie für die späteren nativen iOS-/Android-Clients. Jeder Client verwendet ausschließlich den stabilisierten SystemONE-API- und Event-Vertrag.
- Eine Migration wird erst nach dem geschlossenen Pilot anhand messbarer Anforderungen entschieden. Sie ist ein eigenes Vorhaben mit Migrations- und Rückfallplan.

## Architekturgrenzen

1. Weboberfläche und zukünftige Clients greifen nur auf die öffentliche SystemONE-API und normalisierte Ereignisse zu.
2. Adapter kapseln Discovery, Pairing, Gerätelisten, Aktionen und herstellerspezifische Credentials.
3. Capability-Layer und Registry validieren und normalisieren alle Geräteänderungen.
4. Automationen verwenden denselben Capability- und Adapterpfad wie manuelle Befehle.
5. Persistenz, Backup und Diagnose erhalten keine nicht freigegebenen Secrets oder internen Adapterdaten.
6. Externe Module wie Kamera, Pi-hole und YouDo werden deaktivierbar und getrennt vom lokalen Core entwickelt.

## Qualitäts- und Sicherheitsfolgen

- `HUE_MODE=simulation` bleibt der sichere Standard.
- Jede Änderung muss Syntaxprüfung, hardwarefreie Tests und risikogerechte Browser- oder Hardwaretests bestehen.
- Authentifizierung, Autorisierung, CSRF-Schutz, Rate Limits, TLS/Geräteidentität, signierte Updates und getestetes Rollback sind Release-Gates vor der Pilotfreigabe.
- Echte Hardwarekommunikation erfolgt nur nach ausdrücklicher Freigabe und mit dokumentierter Testmatrix.

## Konsequenzen

Positiv:

- Der bestehende, getestete Core kann schrittweise gehärtet werden.
- Es gibt nur einen Pilotpfad und einen öffentlichen Gerätevertrag.
- Hardware- und Security-Tests bleiben reproduzierbar.

Nachteile und Risiken:

- Der Monolith muss klare Modulgrenzen beibehalten.
- Dateibasierte Persistenz eignet sich nicht automatisch für spätere Mehrgeräte- oder Mandantenanforderungen.
- Mobile Clients folgen erst nach Stabilisierung des API- und Event-Vertrags.

## Erneute Bewertung

Die Entscheidung wird nach dem eigenen Haushaltspilot und vor einer externen Beta geprüft. Auslöser für eine frühere Neubewertung sind nachgewiesene Leistungsgrenzen, nicht beherrschbare Datenmigrationen oder Anforderungen, die innerhalb der beschriebenen Modulgrenzen nicht sicher umsetzbar sind.
