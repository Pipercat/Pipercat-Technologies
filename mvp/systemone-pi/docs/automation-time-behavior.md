# Lokales Zeit- und DST-Verhalten

Stand: 13.08.2026 · Bearbeitet von: Pipercat Technologies

- Automationen verwenden ausschließlich die lokale Zeitzone des SystemONE Pi. Die aktive IANA-Zeitzone ist über `/api/automations/scheduler` sichtbar.
- Eine Fälligkeit wird aus lokalem Datum, Stunde und Minute gebildet und pro Automation persistent gespeichert.
- Ein Neustart innerhalb derselben Minute führt die Automation nicht erneut aus.
- Beim Ende der Sommerzeit kommt eine lokale Uhrzeit (zum Beispiel 02:30) zweimal vor. SystemONE behandelt beide Vorkommen als dieselbe lokale Fälligkeit und führt sie nur einmal aus.
- Beim Beginn der Sommerzeit existieren übersprungene lokale Minuten nicht. Für diese Minuten erfolgt kein nachträgliches „Catch-up“, um unerwartete Aktionen zu vermeiden.
- Sonnenzeiten werden für den jeweiligen lokalen Tag aus lokal gespeicherten Koordinaten berechnet. Offset-Übergänge über Mitternacht berücksichtigen das vollständige Datum.
- Eine fehlgeschlagene Automation wird aus dem Laufstatus entfernt. Der Scheduler kann weitere Automationen ausführen; die fehlgeschlagene Ausführung kann über den sicheren Verlauf-Retry fortgesetzt werden.
