# SystemONE Customer App (Flutter)

Kunden-Client für SystemONE, laut `DEC-4` verbindlich Flutter. Kommuniziert ausschließlich über den SystemONE-API-v1-Vertrag (`packages/shared-contracts`) mit `apps/customer-backend` — nie direkt mit Home Assistant oder Herstellergeräten.

## Status

Standard-Flutter-Skeleton aus `S1V2-01-002` (`pubspec.yaml`, `lib/main.dart`, `test/widget_test.dart`, `analysis_options.yaml`).

**Bekannte Einschränkung:** In der KI-Sandbox, in der dieses Skeleton erstellt wurde, ist kein Flutter-/Dart-SDK installiert (`flutter`/`dart` nicht im `PATH`). `flutter pub get`, `flutter analyze` und `flutter test` konnten deshalb **nicht** ausgeführt/verifiziert werden. Die Dateien folgen der Standard-Flutter-Projektstruktur, sind aber bis zur ersten echten Ausführung auf einer Maschine mit Flutter-SDK als **unverifiziert** zu behandeln. Vor dem Beginn echter UI-Arbeit (Phase „06 Clients & Integrationen“) zwingend zuerst nachholen:

```bash
cd apps/customer-app
flutter pub get
flutter analyze
flutter test
```

## Entwicklung

```bash
cd apps/customer-app
flutter pub get
flutter run
```
