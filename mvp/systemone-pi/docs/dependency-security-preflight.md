# SystemONE Pi – Dependency-Security-Preflight

**Stand:** 13.08.2026

**Bearbeiter:** Pipercat Technologies

**Scope:** Produktionsabhängigkeiten des lokalen Node.js-MVP

## Reproduzierbarer Nachweis

```bash
npm ci
npm audit --omit=dev
npm ls --omit=dev --all
```

Ergebnis am Prüftag: **0 bekannte Schwachstellen** (`info`, `low`, `moderate`, `high`, `critical` jeweils 0) bei 30 gemeldeten Produktionsabhängigkeiten. Direkte Produktionsabhängigkeit ist `qrcode@1.5.4`; transitive Pakete werden durch `package-lock.json` festgeschrieben.

## Freigaberegel

- `npm ci` muss aus dem versionierten Lockfile erfolgreich sein.
- Ein `high`- oder `critical`-Finding blockiert Pilot und Beta bis Fix oder dokumentierter, fachlich freigegebener Risikobehandlung.
- Moderate Findings werden vor jeder Pilotstufe bewertet und mit betroffener Laufzeitfläche dokumentiert.
- Abhängigkeiten werden nicht allein für eine höhere Versionsnummer aktualisiert; relevante Tests und QR-Onboarding müssen nach jeder Änderung erneut laufen.

## Klare Grenze

Dieser automatisierte Registry-Abgleich prüft nur veröffentlichte bekannte Paketmeldungen. Er ersetzt weder Quellcodeanalyse, Konfigurationsprüfung, Ziel-Pi-Härtung, Penetrationstest noch das in `release-evidence.json` geforderte **externe Security-Review**. Das Security-Gate bleibt deshalb `passed: false`.
