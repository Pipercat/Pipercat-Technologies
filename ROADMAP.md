# Roadmap

## 30 Tage

- Unternehmens- und Produktdokumentation vervollständigen
- Gewerbeanmeldung vorbereiten
- Markenname, Domain und Grunddesign prüfen
- SystemONE-Pilotarchitektur gemäß ADR-0001 beibehalten und Modulgrenzen prüfen
- ersten Raspberry-Pi-Prototyp definieren

## 90 Tage

- SystemONE Pi als reproduzierbaren Prototyp aufbauen
- Hue-Vertikalpfad, sichere lokale Administration und Wiederherstellung abschließen
- Pi-hole als optionales Modul prototypisieren
- Updatefreigabe und Backup vor Änderungen testen
- ersten Pilotkundenprozess dokumentieren
- YouDo- und Digital-Screen-MVP zuschneiden

## 6 Monate

- erste Testinstallationen betreiben
- Provisionierung teilweise automatisieren
- SystemONE-Dashboard als MVP entwickeln
- SystemONE Care als Servicepaket definieren
- technische und rechtliche Dokumente fachkundig prüfen lassen

## 1 Jahr

- standardisierte SystemONE-Pi- und Mini-Angebote
- Modulbibliothek für Home, Network, Storage und Backup
- YouDo MVP und erstes Digital-Screen-Dashboard
- Peet-AI-Prototyp mit kontrollierten Tool-Aufrufen
- wiederkehrende Wartungsverträge

## 3 Jahre

- stabile Plattform für mehrere Kundensysteme
- standardisierte Serverlinie
- kleines Installations- und Supportteam
- Geschäftskundenangebote
- belastbare Sicherheits-, Release- und Supportprozesse

## 5 Jahre

- SystemONE Server und Rack als projektierte Produktlinien
- Partner- und Installationsmodell prüfen
- Peet AI, YouDo und Digital Screen als integrierte Produktfamilie
- professioneller Vertrieb und Kundenservice

## 10 Jahre

- etabliertes modulares Infrastruktur-Ökosystem
- skalierbare Plattform- und Lizenzmodelle
- Partnernetzwerk
- eigene standardisierte Hardwareoptionen
- Ausbau für anspruchsvolle Privatkunden und Unternehmen

## Priorisiertes MVP

Die technische Reihenfolge für den Pi-Pilot folgt [ADR-0001](docs/architecture/adr-0001-systemone-pi-pilot.md). Eine Home-Assistant-, FastAPI- oder PostgreSQL-Migration ist kein paralleler Pilotpfad.

1. sichere Geräteidentität
2. Kunden- und Geräteverwaltung
3. Modulprofile
4. updatefähiger SystemONE-Pi-Prototyp
5. Kundenfreigabe für Updates
6. Backup und Rollback
7. Audit-Logs
8. sicherer Supportzugang
9. Pilotkundendokumentation
