# MQTT-Eventbus (Stand 17.08.2026)

> Erledigt Notion-Aufgabe `S1V2-02-004 · MQTT-Eventbus für interne Geräte- und Zustandsereignisse kapseln`.
> Quelle: `DEC-4`. Implementierung: `apps/customer-backend/app/events_mqtt.py`, aufbauend auf dem `EventBus`-Port aus `S1V2-01-004` (`app/events.py`).

## Topic-Konvention

`systemone/v1/events/{event_type}` — z. B. `systemone/v1/events/system.restart_requested`.

- **`v1`-Präfix:** eine spätere inkompatible Topic-Strukturänderung kann als `v2` parallel laufen, ohne bestehende Subscriber zu brechen (dieselbe Versionierungsphilosophie wie `/api/v1/*`, siehe `docs/architecture/api-contract.md`).
- **`{event_type}` statt Geräte-/Nutzer-ID im Topic:** Subscriber können gezielt per MQTT-Wildcard filtern (`systemone/v1/events/device.#`), ohne dass Topics selbst Geräte- oder Nutzeridentitäten preisgeben (`S1V2-02-004`: „keine unnötigen PII/Secrets in Topics"). Identifizierende Daten stehen ausschließlich im Payload, der den lokalen Broker nicht verlässt (kein externer/Cloud-MQTT).

## Payload-Versionierung

`DeviceStateEvent.schemaVersion` (aktuell `1`) ist jetzt Teil des Events selbst (`app/events.py`) — gilt für beide `EventBus`-Implementierungen (In-Memory und MQTT), nicht nur für MQTT-Nachrichten. Eine künftige inkompatible Payload-Änderung erhöht `schemaVersion`, alte Konsumenten können anhand des Felds erkennen, ob sie ein Payload verstehen.

## QoS/Retain

- **QoS 1 (at-least-once):** Zustandsänderungen sind wichtig genug für Zustellversuche, aber „genau einmal" ist unnötiger Aufwand für Ereignisse, die aus dem Domain Layer (`S1V2-02-002`) ohnehin reproduzierbar sind — Konsumenten müssen duplikat-tolerant sein (siehe unten), statt dass der Bus exakt-einmal-Zustellung garantiert.
- **`retain=False`:** Events sind keine „aktueller Zustand"-Schnappschüsse (dafür existiert bereits `GET /api/v1/devices`). Retained Messages würden einem neuen Subscriber veraltete Ereignisse als aktuell unterschieben.

## Publisher/Subscriber über interne Schnittstelle

`MqttEventBus` implementiert exakt denselben `EventBus`-Port wie `InMemoryEventBus` (`publish`, `recent`, jetzt zusätzlich `subscribe` — in `S1V2-01-004` ergänzt, da die reine In-Memory-Variante keine echte Live-Zustellung brauchte). Kein Aufrufer importiert `aiomqtt` außerhalb von `app/events_mqtt.py`.

## Reconnect / Duplicate Delivery / Offline

- **Reconnect:** ein Hintergrund-Task (`_run()`) hält die Verbindung; bei `aiomqtt.MqttError` (Verbindungsabbruch) wartet er `reconnect_delay` Sekunden und verbindet neu — läuft, bis `stop()` aufgerufen wird.
- **Offline-Publish:** Ist der Client gerade nicht verbunden (oder schlägt `publish` fehl), landet das Event in einem begrenzten In-Memory-Outbox (`maxlen=200`) statt verloren zu gehen oder den Aufrufer blockieren zu lassen. Bei Reconnect wird die Outbox zuerst geleert (`_flush_outbox()`), bevor neue Nachrichten verarbeitet werden. Eine sehr lange Störung verwirft die ältesten gepufferten Events (begrenzter Speicher) — das ist eine bewusste Entscheidung: Events sind Benachrichtigungen, kein Ersatz für dauerhafte Datenhaltung (die liegt in PostgreSQL, `S1V2-02-001`).
- **Duplicate Delivery:** jedes empfangene Event wird über seine stabile `id` gegen einen begrenzten „gesehene IDs"-Ring (`maxlen=1000`) geprüft; ein Duplikat (z. B. durch QoS-1-Redelivery nach einem Brokerneustart) wird geloggt und verworfen, bevor es an `recent()` oder registrierte Handler weitergereicht wird.

## Tests

`apps/customer-backend/tests/mqtt_conftest.py` startet einen **echten lokalen Mosquitto-Broker** als Subprozess auf einem Testport (kein Mock) und erlaubt gezieltes Stoppen/Neustarten mitten im Test. `tests/test_mqtt_eventbus.py` (siehe DoD):

- **Normalfall:** Event wird veröffentlicht, über die Subscription empfangen, taucht in `recent()` auf.
- **Duplicate Event:** dieselbe Event-`id` wird zweimal auf den Broker publiziert — nur ein Handler-Aufruf, `recent()` enthält es nur einmal.
- **Broker-Neustart/Netzverlust:** Broker wird während der laufenden Verbindung hart beendet, ein `publish()` in dieser Phase landet in der Outbox statt zu crashen; Broker wird neu gestartet; der Reconnect-Task verbindet sich automatisch neu und leert die Outbox; ein danach veröffentlichtes Event kommt normal an. **Systemzustand bleibt konsistent:** keine Exception propagiert nach außen, `recent()`/interner Zustand bleiben durchgehend abfragbar.

CI (`.github/workflows/systemone-core-neubau.yml`) installiert Mosquitto direkt auf dem Runner (`apt-get install -y mosquitto`) statt als Service-Container, weil der Test den Broker-Prozess selbst kontrollieren (stoppen/neu starten) muss — mit einem Docker-Service-Container aus dem Job heraus wäre das umständlicher.

## Bewusst nicht Teil dieser Aufgabe

- `app/main.py`s Standard-`event_bus` bleibt vorerst `InMemoryEventBus` — die Umstellung auf `MqttEventBus` inkl. FastAPI-Lifespan-Start/Stop ist eine Verdrahtungsentscheidung für eine spätere, dedizierte Infrastruktur-Aufgabe (analog dazu, dass `HomeAssistantAdapter` ebenfalls erst in `S1V2-02-016` tatsächlich in `device_service` eingesetzt wird, nicht schon jetzt in `S1V2-02-002`).
- Exponentielles Backoff für Reconnect (aktuell fester Delay) — bei Bedarf einfache Erweiterung, hier nicht vorgezogen.
