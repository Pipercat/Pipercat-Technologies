# ADR-001: Installierbare Local-First-PWA als erster Mobile Client

**Status:** Angenommen · 2026-08-13

## Entscheidung

Der erste mobile SystemONE-Client ist die vorhandene responsive Web-App als installierbare Progressive Web App. Sie läuft auf iOS, Android und Desktop gegen den lokalen API-v1-Vertrag. Flutter wurde für den Pilot zurückgestellt: Eine zusätzliche Runtime und zweite UI-Implementierung würden QR-Pairing, Gerätebedienung und Barrierefreiheit duplizieren, ohne für den Local-First-Pilot einen nachgewiesenen Vorteil zu bringen.

Die PWA besitzt Manifest, Standalone-Darstellung, App-Icon, Installationsaktion und einen Service Worker. Dieser cached ausschließlich die statische App-Shell; API-, Session-, Geräte- und andere private Antworten werden niemals offline gespeichert. Ohne erreichbaren SystemONE Pi zeigt die Shell den Verbindungsfehler, führt aber keine veralteten Steuerbefehle aus.

## Lokaler Funktionsumfang

- QR-Pairing und zwölfstündige lokale Rollen-Session
- Räume und Kernsteuerung über `/api/v1/*`
- SSE-Livezustände mit Reconnect/Resync
- Kein Pipercat-Konto, App Store, Pushdienst oder Cloudkonto erforderlich

## Folgen

Native Swift-/Kotlin-Clients können später denselben Vertrag nutzen, falls Pilotmessungen Hintergrundbetrieb, Widgets oder Plattformintegration rechtfertigen. Ein Wechsel verändert weder Core noch Geräteadapter. TLS-Geräteidentität und der praktische iOS-/Android-Installationslauf auf Zielgeräten bleiben Pilotgates.
