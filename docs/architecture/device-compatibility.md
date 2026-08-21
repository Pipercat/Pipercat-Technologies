# Kompatibilitätsmodell Certified/Compatible/Beta (Stand 21.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-026 · Kompatibilitätsmodell Certified/Compatible/Beta technisch umsetzen`.
> Quelle: `DEC-12`. Implementierung: `apps/customer-backend/app/device_compatibility.py`, `apps/customer-backend/app/main.py` (`GET /api/v1/device-compatibility`).

## Warum ein statisches, code-verwaltetes Register statt einer Datenbanktabelle

`apps/customer-backend` ist eine Ein-Instanz-pro-Haushalt-Anwendung (Local-First, `docs/product-manifest.md` §2) — jede Kundeninstanz hat ihre eigene, unabhängige PostgreSQL-Datenbank. „Der Sonoff Zigbee 3.0 USB Dongle Plus ist Certified" ist aber eine **produktweite**, nicht haushaltsspezifische Tatsache — dieselbe auf jeder einzelnen SystemONE-Installation. Eine Datenbanktabelle dafür müsste identisch in jeder einzelnen Kundeninstanz gepflegt werden, ohne dass ein Mechanismus existiert, sie zwischen Instanzen zu synchronisieren.

`app/product_class.py` (aus `S1V2-01-003`) löst genau dieses Problem bereits für die Produktklassen-/Feature-Matrix — eine reine Python-Registrierung, kein DB-Zugriff. `app/device_compatibility.py` folgt exakt demselben Muster.

## „Status kann nicht allein durch Endnutzer auf Certified gesetzt werden" — maximal erfüllt

Nicht nur berechtigungsgeprüft, sondern **strukturell unmöglich**: Es gibt keine API-Route, keine Datenbankzeile und keinen Laufzeit-Codepfad, über den ein Kunde einen Eintrag ändern könnte. Der einzige Weg, einen Eintrag hinzuzufügen oder zu ändern, ist eine Codeänderung an `app/device_compatibility.py` selbst — review-pflichtig und ausgeliefert wie jede andere SystemONE-Änderung. Das ist eine stärkere Garantie als ein Berechtigungscheck, den ein Kunde zumindest versuchen und abgelehnt bekommen könnte.

## „Certified nur nach realer definierter Testmatrix" — strukturell erzwungen

`DeviceCompatibilityProfile`s Pydantic-Validator lehnt `status=CERTIFIED` ohne `CompatibilityTestEvidence` ab, und lehnt `CompatibilityTestEvidence` mit auch nur einem fehlgeschlagenen Testfall ab. „Reale definierte Testmatrix" ist damit keine Konvention, sondern ein Konstruktorfehler, wenn sie fehlt oder nicht vollständig besteht — `CompatibilityTestEvidence(tested_by, tested_at, test_matrix: dict[str, bool])` macht das Testergebnis strukturiert und nachvollziehbar, nicht nur eine Behauptung.

## „Beta ausdrücklich mit Hinweis und ohne Gleichstellung"

`DeviceCompatibilityProfile.disclaimer` ist eine berechnete `@property`, kein speicherbares Feld — ein Beta-Eintrag kann seinen Warnhinweis nie versehentlich verlieren, und ein Certified/Compatible-Eintrag kann nie einen versehentlichen Hinweis tragen. Ein Konstruktor-Kwarg `disclaimer=...` wird von Pydantic stillschweigend ignoriert (Standard `extra="ignore"`) — der tatsächliche, statusabgeleitete Text ist immer das, was Aufrufer sehen.

## „UI/API zeigen Status nachvollziehbar" — der lesende Teil

`GET /api/v1/device-compatibility?manufacturer=...&model=...&integrationType=...` — keine Berechtigung nötig (öffentliche Produktinformation, keine Haushaltsdaten), liefert `{manufacturer, model, integrationType, capabilities, status, disclaimer}` oder `404 DEVICE_COMPATIBILITY_NOT_FOUND`. Ein manueller Abruf per Hersteller/Modell, **keine** automatische Annotation jedes Geräts in `GET /api/v1/devices` — siehe „Bekannte Grenzen" für die dafür nötige, hier bewusst nicht gebaute Korrelation.

## Register aktuell leer — ehrlicher Ausgangszustand

`DEVICE_COMPATIBILITY_REGISTRY` enthält aktuell **keinen einzigen** `CERTIFIED`-Eintrag. Keine der Hardware-Validierungen, von denen ein echter Certified-Status abhängen würde (`S1V2-02-022` Zigbee, `-023` Matter, `-024` Shelly, `-025` Hue — alle noch ohne Hardware-Nachweis, siehe deren eigene `docs/architecture/*.md`), hat tatsächlich stattgefunden. Ein leeres Register ist der ehrliche Ausgangszustand, keine Lücke, die mit erfundenen Einträgen kaschiert werden sollte.

## Tests

`apps/customer-backend/tests/test_device_compatibility.py` (14 Tests): Certified ohne Testnachweis abgelehnt, Certified mit fehlgeschlagenem Testfall abgelehnt, Certified mit vollständig bestandener Matrix akzeptiert, Compatible/Beta brauchen keinen Testnachweis, Beta trägt immer den Disclaimer, Certified/Compatible nie, Disclaimer ist nicht überschreibbar, Registry-Lookup groß-/kleinschreibungs- und leerzeichenunabhängig.

`apps/customer-backend/tests/test_device_compatibility_api.py`: 404 für unregistriertes Gerät, korrekte Antwort für registriertes Gerät, groß-/kleinschreibungsunabhängiger Abruf, Beta-Antwort enthält Disclaimer.

Gesamt `apps/customer-backend`: **313/313 bestanden** (299 aus `S1V2-01-003`–`S1V2-02-023` + 14 neue). `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund. `docker compose config`: erfolgreich validiert (unverändert von dieser Aufgabe).

## Architekturentscheidungen

- Statisches, code-verwaltetes Register statt Datenbanktabelle — siehe oben, folgt `app/product_class.py`s bereits etabliertem Muster für produktweite (nicht haushaltsspezifische) Klassifikationsdaten.
- Keine Berechtigungsprüfung/`Actor`-Maschinerie — bewusst, da die stärkste verfügbare Garantie ("kein Codepfad existiert") bereits ohne sie erreicht ist; eine Berechtigungsprüfung wäre hier reine Zusatzkomplexität ohne zusätzlichen Sicherheitsgewinn.
- `disclaimer` als berechnete Property statt gespeichertes Feld — verhindert strukturell jede Inkonsistenz zwischen Status und Warnhinweis.
- Neuer, eigenständiger Lese-Endpunkt statt Erweiterung von `GET /api/v1/devices` — vermeidet die (deutlich aufwändigere) Live-Korrelation zwischen SystemONE-`device_id` und Hersteller/Modell, die eine automatische Annotation jedes Geräts bräuchte (siehe „Bekannte Grenzen").

## Bekannte Grenzen

- **Keine automatische Annotation von `GET /api/v1/devices`** mit dem Kompatibilitätsstatus — dafür müsste jedes zurückgegebene Gerät mit seinem Hersteller/Modell aus Home Assistants Geräte-Registry (`manufacturer`/`model`-Felder, bereits gegen `home-assistant/core`-Quellcode verifiziert wie in `docs/architecture/matter-integration.md`) korreliert werden — ein zusätzlicher Netzwerk-Roundtrip pro `list_devices()`-Aufruf, der den bestehenden, häufig abgefragten Live-Pfad spürbar verändern würde. Bewusst nicht Teil dieser Aufgabe; der neue Endpunkt deckt „API zeigt Status nachvollziehbar" bereits ab, nur nicht automatisch inline.
- **Register ohne Certified-Einträge** (siehe oben) — hängt vollständig von den noch ausstehenden Hardware-Validierungen `S1V2-02-022` bis `-025` ab.
- **Kein dynamischer/telemetriebasierter Meldeweg** (z. B. Kundeninstanzen, die Testergebnisse an HQ zurückmelden) — diese Aufgabe implementiert die Klassifikationslogik selbst, nicht einen verteilten Erfassungsprozess. Falls das später gewünscht ist, ist das eine eigene, größere Erweiterung.
