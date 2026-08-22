# Geschützter Kundenadmin-Bereich mit automatischer Wiedersperre (Stand 18.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-010 · Geschützten Kundenadmin-Bereich mit automatischer Wiedersperre umsetzen`.
> Quellen: `DEC-121`, `DEC-122`. Implementierung: `apps/customer-backend/app/auth/admin_area.py`.

## Zwei-Schichten-Modell

- **Basissession** (`S1V2-02-008`) deckt Alltagssteuerung ab — öffnet standardmäßig ohne erneute Passwortabfrage.
- **Admin-Bereich-Freischaltung** (diese Aufgabe) ist eine **zweite, getrennte** Freischaltung obenauf: eine gültige Session ist notwendig, aber nicht hinreichend für administrative Aktionen. Eine frische Session startet nachweislich **gesperrt** im Admin-Bereich (`test_a_fresh_session_is_locked_out_of_the_admin_area_by_default`).

## Erneute Freigabe: Passwort oder Biometrie

`AdminAreaService.unlock_admin_area()` akzeptiert entweder `password` (gegen den echten Argon2id-Hash aus `S1V2-02-008` geprüft) oder `biometric_assertion` (gegen einen `BiometricVerifier`-Port geprüft — `FakeBiometricVerifier` hier, echte plattformseitige Verifikation, z. B. WebAuthn/Passkey, ist ein späterer, dedizierter Baustein). **Ein vom Client mitgeschickter roher „ich bin freigeschaltet"-Wert wird nirgends akzeptiert** — nur eine erfolgreiche Verifikation setzt den Freischaltungszustand, der ausschließlich serverseitig gehalten wird (`_AdminAreaLockState`, keyed nach demselben Token-Hash wie `SessionStore`).

## Automatische Wiedersperre

- **Inaktivität:** `require_unlocked()` — der Aufruf, den jede administrative Aktion tätigen muss — prüft, ob seit der letzten Aktivität weniger als 5 Minuten vergangen sind, und **verlängert** das Fenster bei jedem erfolgreichen Aufruf (`touch`). Eine reine Statusabfrage (`is_unlocked()`) verlängert **nicht** — wichtig für Tests und für Clients, die nur prüfen wollen, ohne die Sperrzeit zu beeinflussen.
- **Hintergrund/Verlassen:** `lock(raw_token, reason=...)` — vom Client aufgerufen, wenn die App in den Hintergrund geht oder den Admin-Bereich verlässt; sperrt sofort, unabhängig von der Inaktivitätszeit.

## Schutz kann nicht deaktiviert werden

`require_unlocked()` hat **keinen** Parameter, keine Konfigurationsoption und keinen Rollen-Bypass, der die Prüfung umgehen könnte — die Anforderung „Schutz darf nicht deaktiviert werden" ist dadurch erfüllt, dass kein solcher Schalter existiert, nicht durch einen Standardwert, der versehentlich geändert werden könnte.

## Manipulierte Clients

Da der Freischaltungszustand ausschließlich serverseitig existiert, kann ein manipulierter Client nicht einfach „freigeschaltet" vorgeben:

- Admin-Aktion ohne jemals `unlock_admin_area()` aufgerufen zu haben → `AdminAreaLockedError`.
- Falsches Passwort → `StepUpAuthenticationError`, bleibt gesperrt.
- Erfundene/nicht registrierte Biometrie-Assertion → `StepUpAuthenticationError`.
- Biometrie-Assertion eines **anderen** Nutzers wiederverwendet → `StepUpAuthenticationError` (Assertion ist an eine `user_id` gebunden).
- Widerrufene Session → kann den Admin-Bereich nicht freischalten.

Jeder Versuch (erfolgreich, fehlgeschlagen, blockiert, gesperrt) wird auditiert (`admin_area.unlocked`/`stepup_failed`/`blocked_while_locked`/`locked`).

## Tests (Definition of Done)

`apps/customer-backend/tests/test_admin_area.py` (13 Tests) — Backend-/Service-Ebene (noch keine Flutter-App/API-Routen vorhanden, an die äquivalente Tests angehängt werden könnten; die hier geprüfte Durchsetzungslogik ist exakt das, was diese Schichten später unverändert aufrufen):

- Standardmäßig gesperrt; erfolgreiche Freischaltung per Passwort/Biometrie.
- Manipulierte Clients: falsches Passwort, erfundene/fremde Biometrie-Assertion, kein Nachweis übergeben, widerrufene Session, Admin-Aktion ganz ohne Freischaltung.
- Zeitablauf: Sperre nach 5 Minuten Inaktivität; fortlaufende Aktivität verlängert das Fenster korrekt.
- Hintergrund: sofortige Sperre unabhängig von Inaktivitätszeit.
- Erneute Freigabe nach einer Hintergrundsperre funktioniert wieder.

Gesamt `apps/customer-backend`: **126/126 Tests bestanden**.

## Bewusst nicht Teil dieser Aufgabe

- Echte Biometrie-Verifikation (WebAuthn/Passkey oder plattformspezifisch) — nur der Port + Fake, echte Implementierung ist ein späterer Baustein.
- Flutter-seitige Auslösung von `lock()` bei App-Hintergrund (`AppLifecycleState`) und API-Routen für Unlock/Lock — folgen dem etablierten Muster dünner Router/Client-Integration, sobald diese Schichten entstehen.
- Konfigurierbarkeit der 5-Minuten-Frist — bewusst als Konstante mit Override-Parameter für Tests, kein Kunden-einstellbarer Wert (würde dem „Schutz kann nicht deaktiviert werden"-Prinzip potenziell widersprechen, wenn beliebig verlängerbar).
