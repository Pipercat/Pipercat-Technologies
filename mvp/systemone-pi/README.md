# SystemONE Pi Core v0.4.0

Local-first Core mit normalisiertem Device Model. Standardmäßig läuft alles in Simulation; das produktive Philips-Hue-System wird nicht angesprochen.

## Neu in v0.4.0

- herstellerunabhängiges Device Model mit `profile`, `availability`, `compatibility`, `capabilities` und `diagnostics`
- Capability-Layer mit profilbezogener Validierung und Wertebegrenzung
- gemeinsames Adapter-Interface für Discovery, Pairing, Geräteliste und Befehle
- Hue- und Simulation-Adapter liefern dasselbe normalisierte Modell
- zentrale Geräte-Registry mit Geräteereignissen
- API und Weboberfläche verwenden ausschließlich normalisierte Capabilities wie `power` und `brightness`
- automatische Migration vorhandener v0.3.1-Geräte beim Laden
- interne Adapterdaten werden nicht über Geräte-Endpunkte ausgegeben
- 17 hardwarefreie Selftests

## Backup Schema v2

- SHA-256 über kanonisch serialisierte Backup-Daten
- Schema- und Systemversion sowie Erstellzeitpunkt
- strikte Größen-, Raum-, Geräte- und Capability-Validierung vor Restore
- automatische Migration des bisherigen v1-Formats
- transaktionaler Restore mit Rollback des In-Memory- und Dateizustands
- explizite Allowlist: nur Räume, Simulationsgeräte und Theme; keine Hue-Geräte, Credentials oder Tokens
- Clear-UI für lokalen Download, Dateiauswahl und Restore
- serverseitige Vorabvalidierung mit Schema-, Inhalts- und Prüfsummenübersicht
- zweistufige Restore-Bestätigung nach erfolgreicher Validierung
- maximale Uploadgröße von 1 MB in der Oberfläche

## Automation Engine v1

- lokales Modell mit Geräte-Trigger, optionalen Bedingungen und Geräteaktionen
- typsichere Operatoren `equals`, `notEquals`, `above` und `below`
- drei einfache Vorlagen: Sensor schaltet Licht, Temperatur steuert Thermostat, Gerät ausschalten
- Aktivieren, Pausieren und Löschen über API und Clear-UI
- Aktionen laufen durch denselben Adapter- und Capability-Layer wie manuelle Befehle
- letzter Lauf und strukturierter Aktionsfehler bleiben sichtbar und persistent
- Schutz vor rekursiver Ausführung derselben Automation

## Robuste lokale Persistenz

- atomare Schreibvorgänge mit eindeutiger temporärer Datei und Rename
- `fsync` für Datei und – soweit vom Dateisystem unterstützt – Datenverzeichnis
- letzte gültige Version als `.bak`-Recovery-Datei
- automatische Wiederherstellung bei beschädigtem JSON
- strukturierte Diagnosen `STORAGE_RECOVERED`, `STORAGE_READ_FAILED` und `STORAGE_WRITE_FAILED`
- fehlgeschlagene Schreibvorgänge räumen ihre temporären Dateien auf

## Automation Scheduler v1

- tägliche lokale Uhrzeit-Trigger im Format `HH:MM`
- idempotente Ausführung: eine Regel läuft höchstens einmal pro Minute
- Scheduler arbeitet ohne Internet und ohne Cloud-Zeitdienst
- Sonnenauf-/Sonnenuntergang als injizierbare lokale Provider-Abstraktion vorbereitet
- Sonnenereignisse bleiben ohne konfigurierten Standortprovider sicher inaktiv
- Offset von bis zu zwölf Stunden vor oder nach einem Sonnenereignis
- lokales Hausmodell mit Name, Breiten- und Längengrad
- Sonnenzeiten werden direkt auf SystemONE Pi berechnet; keine Standortdaten verlassen das Gerät

## Notion-abgeglichenes Clear UI

- getrennte Kundenansichten für Übersicht, Räume & Geräte, Automationen, Backup und Diagnose
- Übersichtskarten für bereite Geräte, Störungen, aktive Automationen und lokale Sicherung
- produktnahe Statussprache statt technischer Integrationsbegriffe
- Offline-Karten mit Ursache, Handlungsempfehlung und Wiederholen-Aktion
- responsive Kartenraster und touchfreundliche Bedienelemente
- gemeinsame Design-Tokens als Grundlage für Clear, Midnight, Compact und Living
- persistente Theme-Auswahl mit produktivem Clear und Midnight
- Midnight mit dunkelblauem Verlauf, transparenten Rahmen und Display-Kontrast
- Compact ist als informationsdichte Variante verfügbar; Living nutzt dieselben Funktionen in einer weichen, kontraststarken Wohnraumgestaltung
- mobile schwebende Navigation für Home, Räume, Abläufe und Mehr

## Geführter Geräteassistent

- vier verständliche Schritte: Integration, Gerätetyp, Raum/Name und Funktionstest
- Simulation ist im Entwicklungsmodus die empfohlene und einzige aktive Integration
- Hue bleibt bei `HUE_MODE=simulation` sichtbar erklärt, aber nicht auswählbar
- Geräteprofil und Raum werden serverseitig validiert
- Abschluss erstellt automatisch die normalisierte Gerätekarte

## Erweiterte Geräteprofile

- Licht: Leistung, Helligkeit, Farbtemperatur und vorbereitete Hex-Farbe
- Schalter: Leistung und Energie
- Sensor: normalisierter Sensortyp und Batteriestand
- Thermostat: Modus, Heizzustand, Luftfeuchtigkeit und Batterie
- Rollladen: Position, Neigung, Batterie sowie Öffnen/Stop/Schließen
- lokale Geräteinformationen für Firmware, Seriennummer und Hardwareversion
- gerätespezifische Karten, Batterieanzeige und Warnung bei höchstens 20 Prozent

## Sicherheitsregel

```bash
npm start
```

startet im Simulationsmodus. Echte Hue-Kommunikation wird ausschließlich bewusst freigeschaltet:

```bash
HUE_MODE=real npm start
```

## Aus v0.3.1 übernommen

- Reconnect-Zustandsmaschine mit `idle`, `connected`, `backoff` und `reconnecting`
- exponentieller Retry-Backoff mit Jitter statt aggressiver Endlosschleifen
- manueller Reconnect-Endpunkt und sichtbarer Reconnect-Status
- deutlich erweiterte Diagnosematrix für Netzwerk, SSDP, Bridge, Auth, Geräte, Pairing, Backup und Speicher
- echter lokal erzeugter QR-Code für Admin-Pairing
- 5 Minuten gültiger Token plus 6-stelliger Bestätigungscode
- lokaler QR-Scan-Simulator, damit der Pairing-Flow ohne mobile App vollständig testbar ist
- kryptografische lokale Owner-Session als `HttpOnly`-/`SameSite=Strict`-Cookie nach erfolgreichem Pairing
- zentrale Rollenrechte für Eigentümer, Administrator, Mitglied, Gast und Wanddisplay
- Schutz aller schreibenden APIs nach dem ersten Admin-Pairing sowie widerrufbare, persistent gehashte Sessions
- separates Wanddisplay mit eigener `dashboard:read`-Session, freigegebener Datenprojektion und 10-Sekunden-Aktualisierung
- einfacher Dashboard-Editor für Reihenfolge, Sichtbarkeit, Kartengröße und Schnellzugriff mit Live-Vorschau und Standard-Reset
- vereinheitlichte Skeleton-, Lade-, Leer-, Offline-, Fehler- und Retry-Zustände mit Live-Region, Tastaturfokus, groben Touchzielen und reduzierter Bewegung
- geführter Setup-Assistent mit sechs Prüfschritten
- 10 hardwarefreie Selftests

## Bereits enthalten

- Hue-Simulation für Discovery, Pairing, Schalten und Dimmen
- simulierbare Fehler: `not-found`, `link-button`, `timeout`, `auth`, `offline`, `command`
- Geräteprofile Licht, Schalter/Steckdose, Sensor, Thermostat und Rollladen/Jalousie
- persistente Räume und Simulationsgeräte
- lokale Backup-/Restore-Grundlage ohne Secrets
- echte Hue-Integration weiterhin hinter `HUE_MODE=real`

## Start

```bash
cd mvp/systemone-pi
npm install
npm run check
npm test
npm run verify
npm start
```

Browser: `http://localhost:4170`

## Fehler simulieren

```bash
HUE_SIM_FAULT=not-found npm start
HUE_SIM_FAULT=link-button npm start
HUE_SIM_FAULT=timeout npm start
HUE_SIM_FAULT=auth npm start
HUE_SIM_FAULT=offline npm start
HUE_SIM_FAULT=command npm start
```

## API v0.4.0

- `GET /api/health`
- `GET /api/diagnostics`
- `GET /api/setup`
- `GET /api/onboarding`
- `POST /api/onboarding/advance`
- `POST /api/onboarding/reset`
- `GET /api/i18n`
- `GET /api/i18n/messages`
- `PATCH /api/settings/locale`
- `GET /api/state`
- `GET /api/profiles`
- `GET /api/compatibility`
- `GET /api/rooms`
- `POST /api/rooms`
- `GET /api/devices`
- `POST /api/devices/simulate`
- `PATCH /api/devices/:id`
- `GET /api/integrations/hue/discover`
- `POST /api/integrations/hue/pair`
- `POST /api/integrations/hue/sync`
- `POST /api/integrations/hue/reconnect`
- `POST /api/onboarding/pair-admin/session`
- `POST /api/onboarding/pair-admin/complete`
- `GET /api/backup`
- `POST /api/backup/restore`
- `POST /api/backup/validate`
- `GET /api/automations`
- `GET /api/automations/templates`
- `POST /api/automations`
- `POST /api/automations/from-template`
- `PATCH /api/automations/:id`
- `DELETE /api/automations/:id`
- `GET /api/automations/scheduler`
- `GET /api/home`
- `PATCH /api/home`
- `GET /api/themes`
- `PATCH /api/settings/theme`
- `POST /api/admin/display-sessions`
- `POST /api/display/session`
- `GET /api/display`
- `GET /api/dashboard`
- `PATCH /api/dashboard`
- `POST /api/dashboard/reset`
- `GET /api/device-onboarding/integrations`
- `GET /api/device-onboarding/discover?integration=simulation`
- `POST /api/device-onboarding/complete`
- `GET /api/events/devices` (lokaler SSE-Strom; normalisierte Geräteereignisse)

## Aktuelle Core-Selftests

1. kein Zugriff auf eine echte Bridge im Simulationsmodus
2. Bridge nicht gefunden
3. Link-Button fehlt
4. Timeout
5. Auth-Fehler
6. Offline-Gerät
7. Befehlsfehler
8. Persistenz
9. Reconnect wechselt in Backoff
10. erfolgreicher Reconnect setzt Backoff zurück
11. Capability-Normalisierung
12. Abweisung profilfremder Capabilities
13. Migration alter Geräte
14. Redaktion interner Adapterdaten
15. Registry-Ereignisse
16. normalisierte Simulation
17. normalisierte Hue-Simulation
18. gültige Backup-v2-Prüfsumme
19. Erkennung manipulierter Backups
20. Migration von Backup v1
21. Ausschluss von Hue-Geräten und Secrets
22. typsichere Automationsvergleiche
23. Erzeugung aus Vorlage
24. Abweisung unpassender Geräteprofile
25. lokale Geräteaktion
26. deaktivierte Automation
27. diagnostizierbarer Aktionsfehler
28. letzte gültige Storage-Sicherung
29. Recovery beschädigter Zustandsdatei
30. Diagnose nicht behebbarer Lesefehler
31. Zeitvorlage
32. Abweisung ungültiger Uhrzeit
33. einmalige Ausführung pro Minute
34. Ignorieren nicht fälliger Zeit
35. Sonnenereignis mit lokalem Provider
36. sicher inaktives Sonnenereignis ohne Provider
37. Standortvalidierung
38. lokale Sonnenzeitberechnung
39. validierte Backup-Zusammenfassung
40. Abweisung manipulierter Backup-Zusammenfassung
41. verfügbare Clear-/Midnight-Themes
42. Sperre unfertiger Themes
43. hardware-sichere Integrationsauswahl
44. Validierung des Geräteassistenten
45. Farbe und Farbtemperatur
46. Sensortyp und Batterie
47. Thermostat-Heizzustand
48. Schalter-Leistungswert
49. Rollladen-Aktionen
50. lokale Geräteinformationen
51. vollständige Kompatibilitätsklassen
52. Hue bleibt bis zur Hardwarefreigabe experimentell
53. ungeprüfte Hersteller bleiben aus dem Pilot
54. Release-Audit erkennt offene Pflicht-Gates
55. Release-Audit lehnt unvollständige Evidence ab
56. Legacy-Onboarding wird versioniert migriert
57. Onboarding erzwingt geordnete Übergänge
58. Onboarding wird nach Neustart wiederaufgenommen
59. Locale-Auswahl validiert und normalisiert
60. i18n-Katalog besitzt deutschen Fallback
61–66. Lebensdauer, Parallelblock, Einmalverwendung, Fehlversuche und Secret-Redaktion des Admin-Pairings
67–72. Rollenmatrix, Secret-freie Sessions, Ablauf, Widerruf, Rechteprüfung und Neustart-Persistenz
73–77. Physische Recovery-Pflicht, Einmalcode, Fehlversuchssperre sowie Diagnose- und Backup-Redaktion
78. Compact-Theme hält responsive Dichte und mindestens 44-Pixel-Touchziele ein
79. Living-Theme hält WCAG-AA-Textkontrast und mindestens 44-Pixel-Touchziele ein
80–81. Wanddisplay-Datenprojektion enthält nur freigegebene Inhalte und die Display-Rolle kann niemals schreiben
82–85. Dashboard-Layout validiert Reihenfolge und Größe, verhindert leere/duplizierte Zustände und migriert sicher auf Standard
86–89. Dokumentbasis, asynchrone Live-Status, Dialog-/Feldnamen sowie Fokus-, Touch-, Kontrast- und Motion-Regeln
90–92. Stabile Geräteerkennung, Erkennung bereits hinzugefügter Kandidaten und Schutz vor doppelter Aufnahme
93–98. Reconnect-Backoff, Erholung ohne Neustart, Zugang nach Adapterneustart, Paketverlust, Bridge-Wechsel und nutzerfreundliche Hue-Fehlermatrix
99–101. Redigierter SSE-Gerätevertrag, Resync-Sequenz und langsames Fallback-Polling
102–104. Strikte Kompatibilitätsklasse, bewusste Experimental-Aktivierung und verständliche Support-/Cloudhinweise
105–107. Deterministische Aktionsketten, geführte Feld-/Operatorauswahl und verständliche Bedingungsvalidierung
108–110. Sonnenereignis-/Offsetvalidierung, lokaler Tageswechsel und cloudfreie UI-Erklärung
111–114. Verlaufsrotation, partieller idempotenter Retry, Einmalwiederholung und Fehlerredaktion

## Release-Audit

```bash
npm run release:audit
```

Der Befehl schlägt bis zur echten Pilotfreigabe bewusst fehl und listet die offenen Pflicht-Gates aus `release-evidence.json` auf.

## Noch nicht produktionsreif

Vor Kundeneinsatz fehlen weiterhin TLS/Reverse-Proxy-Härtung, Geräteidentitäten/Zertifikate, signierte Updates, umfassende API-Rate-Limits, zusätzliche Origin-/CSRF-Prüfungen, vollständige Backup-Migrationen und ein Security-Review. Lokale Rollen, ablaufende Sessions, Pairing-Rate-Limit und `SameSite=Strict`-Cookies sind als MVP-Basis vorhanden. Der echte Hue-Hardwaretest bleibt bewusst für einen späteren Pilot zurückgestellt.

Die aktuelle, bewusst konservative Hue-Freigabe sowie das wiederholbare Hardwareprotokoll stehen in [`docs/hue-support-matrix.md`](docs/hue-support-matrix.md). Kein reales Hue-Modell wird vor einem protokollierten Hardwarelauf als Certified ausgewiesen.

## Danach

- Backup Schema v2 mit SHA-256, Validierung, Migration und atomarem Restore
- Zeit-/Sonnenereignisse und erweitertes Bedingungsmodell ergänzen
- YouDo-Modul-Hooks ergänzen
- anschließend weitere SystemONE-Module in denselben Simulations-/Diagnoserahmen integrieren

PEET, Pipercat-Control-Plane, Fernzugriff, Pipercat-Push und Kameraaufzeichnung/-KI bleiben außerhalb dieses Pi-MVPs.
