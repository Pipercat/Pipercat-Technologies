# Peet AI

Peet AI ist die intelligente Schicht von SystemONE. Sie verbindet Sprache, Large Language Models, lokale Wissensdatenbanken, Smart Home, YouDo und Digital Screen.

## Funktionen

- Sprache und Text verstehen
- lokale oder externe Modelle auswählen
- Dokumente und Wissensbestände durchsuchen
- Aufgaben in YouDo erzeugen
- Digital Screen steuern
- Smart-Home- und Serveraktionen auslösen
- Informationen zusammenfassen
- Aktionen vor Ausführung prüfen und protokollieren

## Sicherheitsprinzipien

- kritische Aktionen benötigen Nutzerbestätigung
- Least Privilege für Tools und Datenquellen
- Mandantentrennung
- Audit-Logs
- Schutz vor Prompt Injection
- Kostenlimits bei externen Modellen
- lokale Verarbeitung als bevorzugte Option

## MVP

1. Chatoberfläche
2. Modell-Routing
3. lokale Wissensdatenbank mit RAG
4. kontrollierte Tool-Aufrufe
5. YouDo-Integration
6. Home-Assistant-Integration
7. Audit-Log und Bestätigungsdialoge

## Offene Entscheidungen

- erste unterstützte lokale Modelle
- externe Modellanbieter
- Sprachpipeline
- Hardwareanforderungen
- Rechte- und Freigabemodell
