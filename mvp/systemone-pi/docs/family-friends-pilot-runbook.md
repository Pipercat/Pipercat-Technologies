# SystemONE Pi – Familien- und Freundespilot

Status: vorbereitet, noch nicht extern durchgeführt. Start erst nach vollständigem Abschluss des physischen Haushaltspiloten (Aufgabe 46).

## Ziel und Auswahl

Die Testperson braucht weder Home-Assistant- noch Entwicklerwissen. Sie erhält nur die freigegebene Bedienungsanleitung und die Pilotkunden-Checkliste. Eine zweite Pipercat-Person beobachtet, greift aber nur bei Sicherheitsrisiko, Abbruch oder ausdrücklicher Bitte ein. Gesundheits-, Alarm-, Zugangskontroll- und andere sicherheitskritische Anwendungen sind ausgeschlossen.

Pro Testperson wird eine zufällige **Pilot-ID** und ein nicht rückführbarer **Teilnehmer-Alias** verwendet. Namen, Gespräche, private Gerätewerte, WLAN-Zugangsdaten, Tokens, Bilder und Recovery-Codes gehören nicht in den Bericht.

## Ablauf pro Testperson

1. Einwilligung, Rückbau und jederzeitiger Abbruch anhand `pilot-customer-checklist.md` erklären.
2. Die Testperson öffnet bzw. installiert die lokale PWA und führt das Onboarding ohne Entwicklerhilfe aus.
3. Sie benennt einen Raum, steuert eine Lampe, erstellt eine lokale Automation und erklärt den Offlinebetrieb in eigenen Worten.
4. Internet wird kontrolliert getrennt; Kernsteuerung und Automation werden erneut geprüft.
5. Backupstatus, Restore-Hinweis und Recoveryweg werden von der Testperson gefunden und erklärt.
6. Zum Abschluss werden Sessions geprüft, offene Fragen klassifiziert und Weiterbetrieb oder Rückbau entschieden.

## Messung von Support und Abbruch

Jeder Eingriff wird nur als Anzahl und volle Minuten erfasst. Eine Rückfrage ohne Eingriff zählt als Supportkontakt. Ein Abbruch erhält `outcome: aborted` und einen redigierten Fehlercode. Freitext mit privaten Inhalten ist untersagt.

Fehlerklassen:

- **P0:** Sicherheit, Datenschutz, Datenverlust oder unkontrollierte Aktion – sofort abbrechen.
- **P1:** Onboarding oder Kernsteuerung nicht möglich – keine nächste Pilotstufe.
- **P2:** Bedienhürde mit sicherem Workaround – vor Beta priorisieren.
- **P3:** Komfort oder Wunsch – dokumentieren und bewerten.

## Maschinenlesbarer Abschlussbericht

Der Bericht wird lokal an `evaluatePilotReport()` aus `lib/pilot-report.js` übergeben. Minimalbeispiel:

```json
{
  "pilotId": "FF-001",
  "participantAlias": "Person-A",
  "startedAt": "2026-08-20T10:00:00+02:00",
  "endedAt": "2026-08-20T11:00:00+02:00",
  "outcome": "completed",
  "onboardingWithoutDeveloper": true,
  "priorHomeAssistantKnowledge": false,
  "supportMinutes": 5,
  "supportContacts": 1,
  "issues": [{"id":"FF-001-1","severity":"P2","code":"HELP_TEXT_UNCLEAR","status":"closed","action":"Hilfetext präzisiert"}]
}
```

## Freigaberegel

Eine einzelne Testperson gilt nur als bestanden, wenn sie ohne Vorwissen und ohne Entwicklerübernahme abschließt, Support vollständig erfasst wurde und kein P0/P1 offen ist. Die Familien-/Freundesstufe ist erst abgeschlossen, wenn alle vereinbarten Testpersonen bestanden haben und kritische Fehler geschlossen und erneut geprüft wurden. Simulation, interne Durchführung oder ein leerer Bericht ersetzen keine externe Abnahme.

**Offene Evidenz:** Pilot-IDs, Termine, Geräte-/Versionsmatrix, Supportminuten, Abbrüche, redigierte Fehlercodes, Retest-Ergebnis und unterschriebene Pilotkunden-Checklisten.
