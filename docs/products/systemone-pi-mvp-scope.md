# SystemONE Pi: MVP-Scope und Freigabestufen

Stand: 13. August 2026

## Produktentscheidung

Die SystemONE-App wird zuerst als Smartphone-Erlebnis gestaltet. Die aktuell vom Node.js-Core ausgelieferte Oberfläche dient als interaktive, mobile App-Vorschau und als Entwicklungshülle für die lokale API. Eine eigenständige Desktop-Web-App wird erst später gestaltet.

## Stufe A: geschlossener Pilot

Ziel ist ein sicherer Test im eigenen Haushalt und anschließend im Familien- oder Freundeskreis.

Verbindlich enthalten:

- mobile Midnight-App-UX mit Home, Räume, Geräte und Mehr
- lokaler Erststart ohne Pipercat-Konto
- Admin-Pairing, lokale Benutzer, Sessions und Rollen
- fünf normalisierte Geräteprofile
- ein vollständig getesteter Philips-Hue-Vertikalpfad
- verständliche Offline-, Fehler- und Wiederholen-Zustände
- einfache lokale Automationsvorlagen
- lokales Backup, Restore und Recovery
- TLS, lokale Geräteidentität, signiertes Update und getestetes Rollback
- Installations-, Bedienungs- und Pilot-Supportdokumentation

Freigabe erst, wenn Security-, Hardware-, Backup-, Update- und Recovery-Gates praktisch bestanden sind.

## Stufe B: finaler Produkt-MVP

Nach erfolgreichem geschlossenem Pilot:

- gleichwertiger iOS- und Android-Client auf stabilem API-/Event-Vertrag
- Clear, Midnight, Compact und Living mit denselben Komponenten
- Tablet- und Wanddisplayprofile
- lokale Kamera-Liveansicht ohne Aufzeichnung
- optionales Pi-hole-Modul
- unabhängig aktivierbare YouDo-Kalender- und Aufgabenmodule
- freigegebene lokale Govee-Modelle

## Stufe C: späterer Ausbau

- eigenständige Desktop-Web-App
- Matter-, Shelly- und Zigbee-Pfade nach eigener Testmatrix
- weitere Hersteller, Wallboxen und erweiterte Module
- Kameraaufzeichnung und lokale Bildanalyse
- PEET und Sprachsteuerung
- Pipercat-Control-Plane und Flottenverwaltung
- garantierter Fernzugriff bei CGNAT
- Import bestehender Home-Assistant-Installationen
- Kundenzahlungen und öffentlicher App-Store-Launch

## Nicht Bestandteil des geschlossenen Piloten

- sichtbare Home-Assistant-Oberflächen oder technische Entitätsnamen
- YAML- oder Experten-Automationseditor
- verpflichtende Pipercat-Cloud
- Kameraaufzeichnung
- ungeprüfte Hardwareintegrationen
- Desktop-Web-App als eigener Design- und Produktpfad

## Reihenfolge

1. Mobile App-Designsystem und Kernnavigation fertigstellen.
2. Persistentes, sicheres Onboarding umsetzen.
3. Hue-Vertikalpfad und Live-Ereignisse freigeben.
4. Security, Update, Backup und Recovery als Pilot-Gates erfüllen.
5. Geschlossenen Pilot durchführen.
6. Native iOS-/Android-Clients und Produktmodule ergänzen.
7. Desktop-Web-App separat gestalten.
