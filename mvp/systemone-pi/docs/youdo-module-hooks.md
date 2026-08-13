# YouDo-Modul-Hooks

YouDo Kalender und YouDo Aufgaben/Projekte sind zwei unabhängige optionale Module. Ohne Aktivierungsvariable registriert der Server keine YouDo-Navigation oder Karten und der Smart-Home-Core startet unverändert. `YOUDO_CALENDAR_ENABLED=true` und `YOUDO_TASKS_ENABLED=true` aktivieren die Module einzeln.

Jedes Manifest deklariert ausschließlich ID, Name, Navigation und Dashboardkarten. Der Registry-Validator lehnt Module mit Cloud- oder KI-Pflicht ab. Die App liest `/api/modules` und erzeugt Navigation, Ansichten und Karten dynamisch; es gibt keine statische Core-Abhängigkeit zu YouDo.

Die Hooks definieren bewusst noch keine Kalender- oder Projektdatenhaltung. Spätere lokale Stores und Synchronisationsadapter müssen dieselben Rollen-, Backup-, Diagnose- und Secret-Grenzen erfüllen, ohne eine Pflicht zu externen Konten einzuführen.
