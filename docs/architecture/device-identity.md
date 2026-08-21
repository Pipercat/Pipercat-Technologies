# Geräteidentität, Seriennummer, signierte Lizenz und Setup-Secret (Stand 21.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-027 · Geräteidentität, Seriennummer, signierte Lizenz und Setup-Secret modellieren`.
> Quelle: „SystemONE-Pi-QR-/Lizenzentscheidungen" (Notion, Bereich 06). Implementierung: `apps/customer-backend/app/device_identity.py`, `apps/customer-backend/app/services/device_setup.py`, `scripts/sign_device_license.py`.

## Drei getrennte Bausteine für drei unterschiedliche Garantien

1. **`get_product_class()`** (aus `S1V2-01-003`, **unverändert**) — bleibt bei der bereits getesteten, einfachen `SYSTEMONE_PRODUCT_CLASS`-Umgebungsvariable. Kein Sicherheitsrisiko steht hier auf dem Spiel, das eine kryptografische Signatur bräuchte; eine Änderung hier hätte nur `tests/test_feature_matrix.py`s bereits bestehende, korrekte Abdeckung riskiert, ohne einen echten Mehrwert zu bieten.
2. **Signierte `DeviceIdentity`/`SignedDeviceLicense`** — kryptografisch, offline verifizierbar, für Fragen, bei denen es wirklich auf Fälschungssicherheit ankommt (Seriennummer, Geräteklasse als Teil einer manipulationssicheren Identität).
3. **`DeviceSetupSecretService`** — ein einmaliger/rotierbarer Wert, unabhängig von der sichtbaren Seriennummer, der die eigentliche Kopplung/Übernahme eines Geräts schützt.

## Signierte Lizenz: Ed25519, offline verifizierbar

`DeviceIdentity` (`device_id`, `serial_number`, `product_class`, `issued_at`) wird über `canonical_identity_bytes()` (sortierte JSON-Keys, feste Separatoren — deterministisch) mit Ed25519 signiert. `SignedDeviceLicense` bündelt Identität + Base64-Signatur. `verify_device_license()` braucht ausschließlich den **öffentlichen** Schlüssel — keine Netzwerkanfrage, keine HQ-Abhängigkeit (`docs/product-manifest.md` §2). `get_verified_device_identity()` liest Lizenzdatei-Pfad und öffentlichen Schlüssel aus Umgebungsvariablen (`SYSTEMONE_DEVICE_LICENSE_PATH`, `SYSTEMONE_DEVICE_PUBLIC_KEY`) — dasselbe Provisioning-Muster wie `SYSTEMONE_PRODUCT_CLASS`.

**Fail-closed**, exakt wie `ProductClassUnknownError`: eine fehlende Konfiguration (`DeviceLicenseNotConfiguredError`) und eine ungültige Signatur (`DeviceLicenseInvalidError`) sind zwei unterschiedliche, aber beide harte Fehler — nie ein stiller Fallback auf eine Standardidentität.

## „Private Signing Keys nur im kontrollierten Provisioning/HQ-Kontext, nie auf Kundenimage"

Strukturell, nicht nur organisatorisch garantiert: `apps/customer-backend/Dockerfile` kopiert ausschließlich `pyproject.toml` und `app/` aus seinem eigenen Build-Kontext (`apps/customer-backend`). `scripts/sign_device_license.py` liegt bewusst auf Repo-Root-Ebene, **außerhalb** dieses Build-Kontexts — es landet nachweislich nie im Kundenimage, unabhängig davon, was das Skript tut. Die eigentliche Signierfunktion (`sign_device_identity()`) lebt trotzdem in `app/device_identity.py` (damit Signieren und Verifizieren in derselben Testsuite abgedeckt sind) — das ist unbedenklich, weil die Funktion selbst keinen privaten Schlüssel enthält oder lädt, sondern ihn als Parameter entgegennimmt; das Kundenimage verschifft nur den *Code*, der signieren *könnte*, niemals ein tatsächliches Schlüsselmaterial.

`scripts/sign_device_license.py` bietet zwei Unterbefehle: `generate-keypair` (neues Ed25519-Schlüsselpaar) und `sign` (Identität + privater Schlüssel aus Datei → `SignedDeviceLicense`-JSON). Manuell Ende-zu-Ende verifiziert: `generate-keypair` → `sign` → der reale `GET /api/v1/device/identity`-Endpunkt akzeptiert das erzeugte Lizenz-JSON und liefert die korrekte Identität zurück (nicht nur über Test-Doubles bewiesen).

## Setup-Secret: einmalig, rotierbar, unabhängig von der Seriennummer

`DeviceSetupSecretService` (`app/services/device_setup.py`) generiert einen hochentropischen Zufallswert (`secrets.token_urlsafe(32)`), speichert **nur dessen SHA-256-Hash** (nie den Klartext) plus einen `consumed`-Status in einer kleinen JSON-Zustandsdatei. `claim()` markiert einen Wert bei erfolgreicher erster Nutzung dauerhaft als verbraucht — jeder weitere Versuch mit demselben Wert schlägt fehl, bis `rotate()` (= `generate()`) einen neuen ausgibt.

## „Kopierter QR-Code allein reicht nicht zur Übernahme eines anderen Geräts"

Der für die Ersteinrichtung gescannte QR-Code trägt sowohl die sichtbare Seriennummer als auch den aktuellen, noch nicht verbrauchten Setup-Secret-Wert. Sobald der echte Besitzer das Gerät damit einmal beansprucht (`claim()` erfolgreich), ist genau dieser Wert für immer verbraucht — ein später fotografiertes/kopiertes QR-Bild (z. B. aus einem alten Auspack-Video) kann nie mehr erfolgreich sein, weil der gespeicherte Hash bereits zu einem verbrauchten Wert gehört. **Nicht gelöst** (und softwareseitig auch nicht lösbar): ein Wettlauf, bei dem jemand das QR-Bild fotografiert, **bevor** der echte Besitzer beansprucht — das ist eine physische/logistische Sicherheitsfrage (manipulationssichere Verpackung usw.), keine, die dieses Modul für sich beansprucht zu lösen.

## Tests

- `apps/customer-backend/tests/test_device_identity.py` (5 Tests): gültige Signatur verifiziert, falscher öffentlicher Schlüssel abgelehnt, nachträglich getauschte Seriennummer/Produktklasse abgelehnt (die Signatur deckt die gesamte Identität, nicht nur ein Begleit-Token), beschädigte Signatur abgelehnt.
- `apps/customer-backend/tests/test_device_setup.py` (8 Tests): frischer Secret ist hochentropisch, erste Beanspruchung erfolgreich, zweite mit demselben Wert scheitert, falscher Wert scheitert, Beanspruchung ohne je generierten Wert scheitert, Rotation entwertet den alten Wert, Rotation nach Beanspruchung erlaubt einen neuen Zyklus, zwei Service-Instanzen teilen keinen Zustand.
- `apps/customer-backend/tests/test_device_identity_api.py` (3 Tests): echte signierte Lizenz → 200 mit korrekter Identität, fehlende Konfiguration → 500 `DEVICE_LICENSE_NOT_CONFIGURED`, falscher Schlüssel → 500 `DEVICE_LICENSE_INVALID`.
- Zusätzlich manuell Ende-zu-Ende verifiziert (siehe oben): `scripts/sign_device_license.py generate-keypair` → `sign` → echter API-Aufruf, nicht nur Test-Doubles.

Gesamt `apps/customer-backend`: **329/329 bestanden** (313 aus `S1V2-01-003`–`S1V2-02-026` + 16 neue). `python3 scripts/check-import-boundaries.py`: keine Verletzung. `python3 scripts/check-secrets.py`: kein Fund. `docker compose config`: erfolgreich validiert (unverändert).

## Architekturentscheidungen

- `get_product_class()` bewusst unverändert gelassen — die signierte Lizenz ist eine additive, nicht ersetzende Fähigkeit (siehe oben).
- Signierfunktion in `app/device_identity.py` statt in einem separaten, ungetesteten Skript — Signieren und Verifizieren teilen sich dieselbe Testsuite; die Docker-Build-Kontext-Grenze allein reicht als Garantie gegen private Schlüssel auf dem Kundenimage.
- Setup-Secret dateibasiert (JSON-Zustandsdatei) statt Datenbanktabelle — der Kopplungsvorgang kann vor der Existenz eines `Household`-Datensatzes stattfinden; passt zum bereits etablierten Muster von `SYSTEMONE_PRODUCT_CLASS`/der Lizenzdatei selbst (Provisioning-Zeit-Konfiguration, nicht Haushaltsdaten).
- Neuer eigenständiger `GET /api/v1/device/identity`-Endpunkt statt Erweiterung eines bestehenden — Geräteidentität ist ein eigenständiges Konzept, keine Property eines Smart-Home-Geräts.

## Bekannte Grenzen

- **Kein vollständiger Erstkopplungs-/Onboarding-Flow** (Anlegen des ersten `Household`/Users beim Beanspruchen des Geräts) — diese Aufgabe liefert den Baustein (`DeviceSetupSecretService`), nicht den vollständigen Onboarding-Prozess, der ihn nutzen würde; das ist eine eigene, größere Aufgabe.
- **Physischer „Wer scannt zuerst"-Wettlauf nicht lösbar** (siehe oben) — bewusst als Grenze benannt, nicht verschwiegen.
- Kein API-Endpunkt für `DeviceSetupSecretService.claim()`/`rotate()` — bewusst nicht gebaut, solange der Onboarding-Flow, der ihn sinnvoll nutzen würde, selbst noch nicht existiert (derselbe „gebaut, aber ohne sinnvollen Aufrufer noch nicht verdrahtet"-Vorbehalt wie bei mehreren anderen Services dieser Session).
