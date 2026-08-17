# Optionales Pi-hole-Modul

Das Modul ist standardmäßig vollständig deaktiviert. Es wird mit `PIHOLE_MODULE_ENABLED=true` lokal freigeschaltet; der Smart-Home-Core besitzt keine Abhängigkeit zum Pi-hole-Prozess und läuft bei Offline-, Timeout- oder Authentifizierungsfehlern unverändert weiter.

Für reale Nutzung werden `PIHOLE_MODE=real`, eine private lokale `PIHOLE_BASE_URL` und optional `PIHOLE_API_TOKEN` gesetzt. Öffentliche Ziele und Zugangsdaten in URLs werden abgewiesen. Das Token bleibt ausschließlich in der Prozessumgebung und wird niemals in State, Backup, Diagnose, Auditdetails oder Browserantworten übernommen.

Der MVP zeigt Erreichbarkeit, Blockingstatus sowie anonyme Anfragezähler und erlaubt nur die klar bestätigte Grundaktion „Blocking aktivieren/pausieren“. Der Standard-Simulationsmodus ermöglicht den vollständigen hardwarefreien UI- und Fehlernachweis.
