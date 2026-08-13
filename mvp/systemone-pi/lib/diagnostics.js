const os = require('os');

const ERROR_CATALOG = {
  HUE_REAL_MODE_DISABLED: { severity: 'info', action: 'Für Hardwaretests HUE_MODE=real explizit setzen.' },
  HUE_NOT_FOUND: { severity: 'warning', action: 'Netzwerk, Bridge-Stromversorgung und VLAN/SSDP prüfen.' },
  HUE_LINK_BUTTON_REQUIRED: { severity: 'warning', action: 'Link-Taste an der Bridge drücken und Kopplung erneut starten.' },
  HUE_TIMEOUT: { severity: 'warning', action: 'Bridge-Erreichbarkeit, IP und Netzwerksegment prüfen.' },
  HUE_NETWORK_ERROR: { severity: 'warning', action: 'Route, Firewall, VLAN und lokale Bridge-IP prüfen.' },
  HUE_HTTP_ERROR: { severity: 'warning', action: 'HTTP-Status und Bridge-Zustand prüfen.' },
  HUE_AUTH_ERROR: { severity: 'error', action: 'Lokale Hue-Anmeldung erneuern; alte Credentials nicht automatisch überschreiben.' },
  HUE_INVALID_BRIDGE_IP: { severity: 'error', action: 'Nur eine private lokale IPv4-Adresse als Hue-Ziel verwenden.' },
  HUE_INVALID_BRIDGE_RESPONSE: { severity: 'warning', action: 'Geräteidentität prüfen; kein unbekanntes LAN-Gerät als Bridge akzeptieren.' },
  HUE_DISCOVERY_RESPONSE_INVALID: { severity: 'warning', action: 'Ungültige SSDP-Antwort ignorieren und Discovery erneut ausführen.' },
  HUE_SSDP_ERROR: { severity: 'warning', action: 'Multicast/UDP 1900, Netzwerkinterface und Firewall prüfen.' },
  HUE_COMMAND_FAILED: { severity: 'warning', action: 'Gerätezustand neu synchronisieren und Befehl erneut senden.' },
  HUE_DEVICE_OFFLINE: { severity: 'warning', action: 'Lampe mit Strom versorgen und Reichweite/Bridge prüfen.' },
  HUE_SYNC_FAILED: { severity: 'warning', action: 'Reconnect-Zustand abwarten oder Diagnose ausführen.' },
  HUE_RECONNECT_SCHEDULED: { severity: 'warning', action: 'Backoff abwarten; wiederholte Fehler nicht durch manuelles Dauerklicken verstärken.' },
  PAIRING_SESSION_MISSING: { severity: 'warning', action: 'Neue lokale Pairing-Sitzung starten.' },
  PAIRING_SESSION_EXPIRED: { severity: 'warning', action: 'Neuen QR-Code erzeugen; alte Tokens nicht wiederverwenden.' },
  PAIRING_INVALID: { severity: 'error', action: 'Token und 6-stelligen Code verwerfen und Pairing neu starten.' },
  DEVICE_PROFILE_INVALID: { severity: 'warning', action: 'Nur ein registriertes SystemONE-Geräteprofil verwenden.' },
  DEVICE_NOT_FOUND: { severity: 'warning', action: 'Geräteliste neu laden und stabile Geräte-ID prüfen.' },
  ROOM_NAME_REQUIRED: { severity: 'warning', action: 'Gültigen Raumnamen angeben.' },
  BACKUP_INVALID: { severity: 'error', action: 'Backup-Version, Struktur und Herkunft vor Restore prüfen.' },
  CAMERA_MODULE_DISABLED: { severity: 'info', action: 'Modul nur bei bewusstem lokalen Bedarf aktivieren.' },
  CAMERA_OFFLINE: { severity: 'warning', action: 'Kamera-Stromversorgung, private LAN-IP und RTSP-Port prüfen.' },
  CAMERA_TIMEOUT: { severity: 'warning', action: 'Kameranetz, VLAN und lokale Erreichbarkeit prüfen.' },
  CAMERA_STREAM_NOT_READY: { severity: 'warning', action: 'Verbindungstest abwarten oder erneut ausführen.' },
  PIHOLE_OFFLINE: { severity: 'warning', action: 'Optionales Pi-hole prüfen; Smart-Home-Core arbeitet unabhängig weiter.' },
  PIHOLE_TIMEOUT: { severity: 'warning', action: 'Pi-hole-Netzwerk prüfen; Smart-Home-Funktionen sind nicht betroffen.' },
  PIHOLE_AUTH_FAILED: { severity: 'warning', action: 'Lokales API-Token außerhalb von Diagnose und Backup erneuern.' },
  GOVEE_HARDWARE_NOT_RELEASED: { severity: 'info', action: 'Bis zum dokumentierten Modelltest sichere Simulation verwenden.' },
  GOVEE_TIMEOUT: { severity: 'warning', action: 'Lokales LAN, VLAN und Govee-LAN-Control-Schalter prüfen.' },
  GOVEE_DEVICE_OFFLINE: { severity: 'warning', action: 'Stromversorgung und lokale WLAN-Erreichbarkeit prüfen.' },
  GOVEE_COMMAND_FAILED: { severity: 'warning', action: 'Gerätestatus lokal neu synchronisieren und erneut versuchen.' },
  STORAGE_READ_FAILED: { severity: 'error', action: 'Dateirechte, Datenträger und JSON-Dateien prüfen.' },
  STORAGE_WRITE_FAILED: { severity: 'error', action: 'Freien Speicherplatz und Dateirechte prüfen.' },
  INVALID_REQUEST: { severity: 'warning', action: 'Eingabedaten und JSON-Struktur prüfen.' },
  INTERNAL_ERROR: { severity: 'error', action: 'Diagnosebericht exportieren und Stacktrace lokal prüfen.' }
};

class Diagnostics {
  constructor(limit = 200) { this.limit = limit; this.events = []; this.startedAt = new Date().toISOString(); }
  record(code, message, details = {}) {
    const catalog = ERROR_CATALOG[code] || ERROR_CATALOG.INTERNAL_ERROR;
    const event = { id: `${Date.now()}-${Math.random().toString(36).slice(2,8)}`, timestamp: new Date().toISOString(), code,
      severity: details.severity || catalog.severity, message, action: details.action || catalog.action, details: sanitize(details) };
    this.events.unshift(event); this.events = this.events.slice(0, this.limit); return event;
  }
  health(state, hue) {
    const freeMb = Math.round(os.freemem()/1024/1024);
    const reconnect = state.integrations?.hue?.reconnect || {};
    const checks = [
      check('runtime', true, `Node ${process.version}`),
      check('local-mode', state.system?.mode === 'local', state.system?.mode || 'unknown'),
      check('storage', true, 'Lokaler Speicher initialisiert'),
      check('hue-safe-mode', hue.mode !== 'real', hue.mode === 'real' ? 'REAL: Netzwerkzugriff erlaubt' : 'SIMULATION: kein Zugriff auf private Hue-Bridge'),
      check('hue-pairing', hue.mode !== 'real' || !state.integrations?.hue?.paired || Boolean(hue.username), 'Credential-Konsistenz'),
      check('reconnect-loop', (reconnect.attempt || 0) < 6, reconnect.state ? `${reconnect.state}, Versuch ${reconnect.attempt || 0}` : 'idle'),
      check('memory', freeMb > 100, `${freeMb} MB frei`)
    ];
    return { status: checks.every(item=>item.ok) ? 'ok' : 'degraded', startedAt:this.startedAt, timestamp:new Date().toISOString(), checks,
      recentErrors:this.events.filter(e=>e.severity==='error').slice(0,10), recentWarnings:this.events.filter(e=>e.severity==='warning').slice(0,10) };
  }
  report(state,hue) {
    return { generatedAt:new Date().toISOString(), system:{name:state.system?.name,version:state.system?.version,mode:state.system?.mode},
      runtime:{node:process.version,platform:process.platform,arch:process.arch,uptimeSeconds:Math.round(process.uptime())},
      hue:{mode:hue.mode,hasBridge:Boolean(hue.bridge),paired:Boolean(state.integrations?.hue?.paired),bridgeId:hue.bridge?.id||null},
      counts:{rooms:state.rooms?.length||0,devices:state.devices?.length||0}, health:this.health(state,hue), events:this.events };
  }
}
function check(name,ok,message){return {name,ok:Boolean(ok),message}}
function sanitize(value){if(Array.isArray(value))return value.map(sanitize);if(!value||typeof value!=='object')return value;const clone={};for(const [key,item] of Object.entries(value)){clone[key]=/password|username|token|secret|credential|recovery/i.test(key)?'[REDACTED]':sanitize(item)}return clone}
module.exports={Diagnostics,ERROR_CATALOG,sanitize};
