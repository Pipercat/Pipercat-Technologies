# Kontrollierte Server-Startfehler

Stand: 13.08.2026 · Bearbeitet von: Pipercat Technologies

SystemONE behandelt Listen-/Bindfehler vor dem ersten erfolgreichen HTTP-Start ohne unhandled Node-Stacktrace:

- `SERVER_PORT_IN_USE` / Exitcode 69: konfigurierter Port ist bereits belegt,
- `SERVER_ADDRESS_UNAVAILABLE` / Exitcode 69: Bind-Adresse ist lokal nicht verfügbar,
- `SERVER_BIND_FORBIDDEN` / Exitcode 77: Prozess besitzt keine ausreichenden Rechte,
- `SERVER_LISTEN_FAILED` / Exitcode 1: sonstiger unerwarteter Listenfehler.

Die Meldung enthält ausschließlich Fehlerklasse, lokale Adresse beziehungsweise Port und eine Korrekturmaßnahme; Socketobjekte, Environmentwerte oder Secrets werden nicht ausgegeben. `RestartPreventExitStatus=69 77 78` verhindert bei Port-/Rechte-/Konfigurationsfehlern eine systemd-Neustartschleife. Nach Korrektur wird bewusst mit `systemctl restart systemone-pi` neu gestartet. Andere unerwartete Laufzeitfehler verbleiben unter `Restart=on-failure` und werden weiterhin neu gestartet.
