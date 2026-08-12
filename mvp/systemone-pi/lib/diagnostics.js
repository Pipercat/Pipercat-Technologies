const os = require('os');

const ERROR_CATALOG = {
  HUE_REAL_MODE_DISABLED: { severity: 'info', action: 'Für Hardwaretests HUE_MODE=real explizit setzen.' },
  HUE_NOT_FOUND: { severity: 'warning', action: 'Netzwerk, Bridge-Stromversorgung und VLAN/mDNS/SSDP prüfen.' },
  HUE_LINK_BUTTON_REQUIRED: { severity: 'warning', action: 'Link-Taste an der Bridge drücken und Kopplung erneut starten.' },
  HUE_TIMEOUT: { severity: 'warning', action: 'Bridge-Erreichbarkeit, IP und Netzwerksegment prüfen.' },
  HUE_HTTP_ERROR: { severity: 'warning', action: 'HTTP-Status und Bridge-Zustand prüfen.' },
  HUE_AUTH_ERROR: { severity: 'error', action: 'Lokale Hue-Anmeldung erneuern; alte Credentials nicht automatisch überschreiben.' },
  HUE_COMMAND_FAILED: { severity: 'warning', action: 'Gerätezustand neu synchronisieren und Befehl erneut senden.' },
  HUE_DEVICE_OFFLINE: { severity: 'warning', action: 'Lampe mit Strom versorgen und Reichweite/Bridge prüfen.' },
  STORAGE_READ_FAILED: { severity: 'error', action: 'Dateirechte, Datenträger und JSON-Dateien prüfen.' },
  STORAGE_WRITE_FAILED: { severity: 'error', action: 'Freien Speicherplatz und Dateirechte prüfen.' },
  INVALID_REQUEST: { severity: 'warning', action: 'Eingabedaten prüfen.' },
  INTERNAL_ERROR: { severity: 'error', action: 'Diagnosebericht exportieren und Stacktrace lokal prüfen.' }
};

class Diagnostics {
  constructor(limit = 200) {
    this.limit = limit;
    this.events = [];
    this.startedAt = new Date().toISOString();
  }

  record(code, message, details = {}) {
    const catalog = ERROR_CATALOG[code] || ERROR_CATALOG.INTERNAL_ERROR;
    const event = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      timestamp: new Date().toISOString(),
      code,
      severity: details.severity || catalog.severity,
      message,
      action: details.action || catalog.action,
      details: sanitize(details)
    };
    this.events.unshift(event);
    this.events = this.events.slice(0, this.limit);
    return event;
  }

  health(state, hue) {
    const freeMb = Math.round(os.freemem() / 1024 / 1024);
    const checks = [
      check('runtime', true, `Node ${process.version}`),
      check('local-mode', state.system?.mode === 'local', state.system?.mode || 'unknown'),
      check('storage', true, 'Lokaler Speicher initialisiert'),
      check('hue-safe-mode', hue.mode !== 'real', hue.mode === 'real' ? 'REAL: Netzwerkzugriff erlaubt' : 'SIMULATION: kein Zugriff auf private Hue-Bridge'),
      check('hue-pairing', hue.mode !== 'real' || !state.integrations?.hue?.paired || Boolean(hue.username), 'Credential-Konsistenz'),
      check('memory', freeMb > 100, `${freeMb} MB frei`)
    ];
    return {
      status: checks.every(item => item.ok) ? 'ok' : 'degraded',
      startedAt: this.startedAt,
      timestamp: new Date().toISOString(),
      checks,
      recentErrors: this.events.filter(event => event.severity === 'error').slice(0, 10),
      recentWarnings: this.events.filter(event => event.severity === 'warning').slice(0, 10)
    };
  }

  report(state, hue) {
    return {
      generatedAt: new Date().toISOString(),
      system: { name: state.system?.name, version: state.system?.version, mode: state.system?.mode },
      runtime: { node: process.version, platform: process.platform, arch: process.arch, uptimeSeconds: Math.round(process.uptime()) },
      hue: { mode: hue.mode, hasBridge: Boolean(hue.bridge), paired: Boolean(state.integrations?.hue?.paired), bridgeId: hue.bridge?.id || null },
      counts: { rooms: state.rooms?.length || 0, devices: state.devices?.length || 0 },
      health: this.health(state, hue),
      events: this.events
    };
  }
}

function check(name, ok, message) { return { name, ok: Boolean(ok), message }; }

function sanitize(value) {
  const clone = { ...value };
  for (const key of Object.keys(clone)) {
    if (/password|username|token|secret|credential/i.test(key)) clone[key] = '[REDACTED]';
  }
  return clone;
}

module.exports = { Diagnostics, ERROR_CATALOG };
