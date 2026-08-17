# Lokaler ONVIF-/RTSP-Kamera-Prototyp

Das optionale Kameramodul ist standardmäßig deaktiviert. `CAMERA_MODULE_ENABLED=true` schaltet es bewusst lokal frei; `CAMERA_MODE=real` erlaubt anschließend ausschließlich RTSP-Ziele an privaten IPv4-Adressen. Das System öffnet keine eingehenden Ports.

Zugangsdaten dürfen nicht Teil der RTSP-URL sein. Benutzername und Passwort werden separat angenommen, mit einem gerätelokalen AES-256-GCM-Schlüssel verschlüsselt und niemals über API, Diagnose oder UI zurückgegeben. Schlüssel- und Geheimnisdatei besitzen lokale `0600`-Rechte.

Der MVP speichert keine Aufnahmen und nutzt weder Cloud noch KI. Im Standard-Simulationsmodus erzeugt SystemONE ein lokales Livebild für UI- und Zustandsprüfungen. Reale RTSP-Wiedergabe verlangt auf Raspberry-Pi-Zielhardware noch das lokale Medien-Gateway; bis zu diesem Hardware-Nachweis liefert das System bewusst `CAMERA_STREAM_GATEWAY_REQUIRED` statt einen unsicheren direkten Browserstream.

Die UI unterscheidet „Noch nicht verbunden“, „Lädt“, „Offline“, „Zeitüberschreitung“ und „Live“. Der reale Hardwaretest mit konkretem ONVIF-/RTSP-Modell bleibt für die Pilotfreigabe gesondert offen.
