# SystemONE Pi – Pilotkunden-Checkliste

## A. Eignung und Einwilligung (vor Termin)

- [ ] Volljährige verantwortliche Person und lokale Kontaktmöglichkeit benannt.
- [ ] Pilotcharakter, experimentelle Integrationen und bekannte Grenzen verständlich erklärt.
- [ ] Freiwillige, widerrufbare Teilnahme ohne Pflicht zu Cloudkonto oder Telemetrie bestätigt.
- [ ] Einwilligung für konkret vereinbarte Supportdaten getrennt von Produktnutzung eingeholt.
- [ ] Keine Gesundheits-, Alarm-, Zugangskontroll- oder sonstige sicherheitskritische Nutzung geplant.
- [ ] Abbruch- und Rückbauwunsch ist jederzeit ohne Funktionsverlust vorhandener Geräte möglich.

## B. Haushalt, Netzwerk und Hardware

- [ ] Unterstützter Raspberry Pi, Netzteil, Datenträger und kabelgebundene Netzwerkoption erfasst.
- [ ] Routerzugang durch Pilotkunde möglich; kein fremdes/öffentliches WLAN.
- [ ] VLAN, Client-Isolation, Multicast/SSDP/mDNS und freie lokale IP dokumentiert.
- [ ] Exakte Bridge-/Gerätemodelle, Firmwarestände, Seriennummern (nur lokal) und Stromversorgung erfasst.
- [ ] Nur in der aktuellen Supportmatrix freigegebene Geräte für Kernabnahme ausgewählt.
- [ ] Experimentelle Govee/Hue-Modelle separat gekennzeichnet; Matter/Shelly/Zigbee nicht vorgezogen.

## C. Installation und Sicherheit

- [ ] Geräteidentität/TLS-Fingerprint vor Pairing verglichen.
- [ ] Owner per kurzlebigem QR-Code lokal gekoppelt; QR-Code danach verworfen.
- [ ] Recovery-Code getrennt und offline an Pilotkunden übergeben; Empfang bestätigt.
- [ ] Nicht benötigte Sessions widerrufen; Displayrolle besitzt nur Leserechte.
- [ ] Kamera, Pi-hole, YouDo und Fernwartung bleiben aus, sofern nicht separat vereinbart.
- [ ] Kein Port-Forwarding, Dauer-VPN, geteiltes Passwort oder unbeaufsichtigter Fernzugang eingerichtet.

## D. Kernabnahme am Installationstag

- [ ] Erststart und erste Lampe ohne Entwicklerhilfe abgeschlossen.
- [ ] Ein/Aus, Helligkeit, Offlinezustand und Reconnect praktisch geprüft.
- [ ] Mindestens eine lokale Automation erstellt und nachvollziehbar ausgelöst.
- [ ] App/PWA auf vereinbartem Mobilgerät geöffnet bzw. installiert.
- [ ] Internet getrennt: Core und lokale Automation funktionieren weiter.
- [ ] Neustart: Räume, Geräte, Automation und Sessionverhalten geprüft.
- [ ] Rotierendes Backup erstellt; Restore-Test zeigt Erfolg.
- [ ] Redigierter Diagnoseexport gemeinsam in der Vorschau kontrolliert.

## E. Backup, Recovery und Rückbau

- [ ] Verschlüsseltes externes Backupziel und Passphrase-Aufbewahrung vereinbart oder bewusst abgelehnt.
- [ ] Test-Restore mit nichtproduktiver Sicherung durchgeführt und Ergebnis protokolliert.
- [ ] Recovery-Ablauf erklärt, ohne echten einmaligen Code offenzulegen.
- [ ] Rückbauplan: SystemONE entfernen, ursprüngliche Bridge/App-Zugänge erhalten, lokale Sessions/Secrets löschen.
- [ ] Defektaustausch und Datenübernahme nur über geprüftes Backup vereinbart.

## F. Beobachtungszeitraum

- [ ] Start-/Enddatum, Ansprechpartner und zulässige Supportzeiten festgelegt.
- [ ] Erfolgskriterien: tägliche Kernsteuerung, Automationszuverlässigkeit, keine Daten-/Sicherheitsvorfälle.
- [ ] Ereignisprotokoll nutzt nur Datum, Fehlercode, betroffene Funktion und Maßnahme – keine Secrets/Privatinhalte.
- [ ] Wöchentlicher Backup-/Restore-Test und Update-/Rollbackstatus kontrolliert.
- [ ] Abweichungen nach Schwere klassifiziert: P0 Sicherheit/Datenverlust, P1 Kernfunktion, P2 Komfort, P3 Wunsch.

## G. Sofortige Abbruchkriterien

- [ ] Verdacht auf Secret-/Recovery-Code-Abfluss oder unautorisierte Session.
- [ ] Datenverlust, nicht rückrollbares Update oder wiederholte Speicherbeschädigung.
- [ ] Unkontrollierte Geräteaktion oder Beeinträchtigung sicherheitskritischer Systeme.
- [ ] Erforderliche Cloud-/Fernzugangsumgehung entgegen Pilotvereinbarung.
- [ ] Pilotkunde widerruft oder fühlt sich mit Betrieb/Datenschutz nicht sicher.

Bei Abbruch: Netzwerkzugang isolieren, Steuerbefehle stoppen, Zustand/Diagnose redigiert sichern, bestätigten A/B-Slot verwenden, Sessions widerrufen, ursprüngliche Herstellersteuerung wiederherstellen und Vorfall ohne Secrets dokumentieren.

## H. Abschluss

- [ ] Erfolgs- und Fehlerkriterien gemeinsam bewertet.
- [ ] Alle temporären Supportzugänge/Sessions widerrufen.
- [ ] Pilotdaten nach vereinbarter Frist gelöscht oder anonymisiert; Löschung bestätigt.
- [ ] Offene Hardwaregates und nicht unterstützte Funktionen erneut erklärt.
- [ ] Entscheidung dokumentiert: Weiterbetrieb, Nachbesserung, Verlängerung oder vollständiger Rückbau.

**Pilot-ID:** ______  **Start:** ______  **Ende:** ______  **SystemONE-Version:** ______

**Pilotkunde bestätigt:** ______  **Pipercat-Bearbeiter:** ______  **Datum:** ______
