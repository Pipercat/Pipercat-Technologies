# YouDo

YouDo ist die Aufgaben-, Planungs- und Organisationsanwendung innerhalb des SystemONE-Ökosystems.

## Funktionsumfang

- persönliche und gemeinsame Aufgaben
- wiederkehrende Aufgaben
- Projekte, Kategorien und Prioritäten
- Fälligkeiten und Verantwortliche
- Kalenderansicht
- Fortschritt und Status
- Smart-Home-Verknüpfungen
- Aufgabenerstellung durch Peet AI
- Darstellung auf Digital Screen
- Wartungsaufgaben für SystemONE

## Erstes Datenmodell

- User
- Household oder Organization
- Project
- Task
- RecurrenceRule
- Category
- Assignment
- Reminder
- IntegrationAction
- AuditEvent

## Mögliche API

- `GET /tasks`
- `POST /tasks`
- `PATCH /tasks/{id}`
- `POST /tasks/{id}/complete`
- `GET /projects`
- `GET /calendar`
- `POST /integrations/actions`

## MVP

1. Aufgaben und Projekte
2. Fälligkeiten, Prioritäten und Wiederholungen
3. Mehrbenutzerrollen
4. Kalenderansicht
5. Peet-AI-Integration
6. Digital-Screen-Widget

## Spätere Erweiterungen

- lokale Synchronisation zwischen Geräten
- Haushaltsvorlagen
- Automatisierungen bei Aufgabenerledigung
- Wartungspläne für Kundensysteme
- optionale externe Kalenderanbindung
