const dgram = require('dgram');
const { DeviceAdapter } = require('./adapter');
const { createDevice } = require('./device-model');
const { validateCapabilities } = require('./capabilities');

function isPrivateIpv4(host) {
  const match = String(host || '').match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!match) return false;
  const octets = match.slice(1).map(Number);
  if (octets.some(n => n < 0 || n > 255)) return false;
  const [a, b] = octets;
  return a === 10 || a === 127 || (a === 192 && b === 168) || (a === 172 && b >= 16 && b <= 31) || (a === 169 && b === 254);
}

function typedError(code, message, details = {}) {
  return Object.assign(new Error(message), { code, details });
}

async function requestWithTimeout(url, options = {}, timeoutMs = 3000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (error) {
    if (error?.name === 'AbortError') throw typedError('HUE_TIMEOUT', `Hue-Anfrage nach ${timeoutMs} ms abgebrochen.`, { url: redactUrl(url), timeoutMs });
    throw typedError('HUE_NETWORK_ERROR', 'Hue-Bridge ist im lokalen Netzwerk nicht erreichbar.', { cause: error.message });
  } finally {
    clearTimeout(timer);
  }
}

function redactUrl(url) {
  return String(url).replace(/\/api\/[^/]+\//, '/api/[REDACTED]/');
}

class HueAdapter extends DeviceAdapter {
  constructor({ storage, demoDevices = [], diagnostics }) {
    super('hue');
    this.storage = storage;
    this.demoDevices = demoDevices;
    this.diagnostics = diagnostics;
    this.secrets = storage.loadSecrets();
    this.mode = process.env.HUE_MODE === 'real' ? 'real' : 'simulation';
    this.bridge = this.mode === 'real' ? (this.secrets.hueBridge || null) : null;
    this.username = this.mode === 'real' ? (this.secrets.hueUsername || null) : 'simulation-user';
    this.simFault = process.env.HUE_SIM_FAULT || '';
  }

  record(error, fallbackCode = 'INTERNAL_ERROR') {
    this.diagnostics?.record(error.code || fallbackCode, error.message, error.details || {});
  }

  simulationBridge() {
    return { id: 'hue-sim-001', name: 'Philips Hue Bridge (Simulation)', ip: '127.0.0.1', status: 'ready', simulated: true };
  }

  async discover() {
    if (this.mode !== 'real') {
      if (this.simFault === 'not-found') return null;
      this.bridge = this.simulationBridge();
      return this.bridge;
    }

    const configuredIp = process.env.HUE_BRIDGE_IP || this.bridge?.ip;
    if (configuredIp) {
      const bridge = await this.verifyBridge(configuredIp);
      if (bridge) return this.rememberBridge(bridge);
    }

    const locations = await this.ssdpSearch();
    for (const location of locations) {
      try {
        const parsed = new URL(location);
        if (!isPrivateIpv4(parsed.hostname)) continue;
        const bridge = await this.verifyBridge(parsed.hostname);
        if (bridge) return this.rememberBridge(bridge);
      } catch (error) {
        this.record(error, 'HUE_DISCOVERY_RESPONSE_INVALID');
      }
    }
    return null;
  }

  rememberBridge(bridge) {
    if (this.mode !== 'real') { this.bridge = bridge; return bridge; }
    const previousBridgeId = this.secrets.hueBridge?.id;
    if (previousBridgeId && previousBridgeId !== bridge.id) {
      this.username = null;
      delete this.secrets.hueUsername;
      delete this.secrets.huePairedBridgeId;
    }
    this.bridge = bridge;
    this.secrets.hueBridge = bridge;
    this.storage.saveSecrets(this.secrets);
    return bridge;
  }

  isPairedWithCurrentBridge() {
    if (this.mode !== 'real') return Boolean(this.username && this.bridge);
    return Boolean(this.username && this.bridge?.id && this.secrets.huePairedBridgeId === this.bridge.id);
  }

  async verifyBridge(ip) {
    if (this.mode !== 'real') return null;
    if (!isPrivateIpv4(ip)) throw typedError('HUE_INVALID_BRIDGE_IP', 'Es werden nur private lokale IPv4-Adressen als Hue-Ziel akzeptiert.', { ip });
    const response = await requestWithTimeout(`http://${ip}/description.xml`);
    if (!response.ok) throw typedError('HUE_HTTP_ERROR', `Hue-Beschreibung antwortet mit HTTP ${response.status}.`, { status: response.status });
    const xml = await response.text();
    if (!/philips hue|signify/i.test(xml)) throw typedError('HUE_INVALID_BRIDGE_RESPONSE', 'Gefundenes Gerät ist keine erkannte Hue Bridge.');
    const name = xml.match(/<friendlyName>([^<]+)<\/friendlyName>/i)?.[1] || 'Philips Hue Bridge';
    const id = xml.match(/<serialNumber>([^<]+)<\/serialNumber>/i)?.[1] || ip;
    return { id, name, ip, status: 'ready', simulated: false };
  }

  ssdpSearch(timeoutMs = 1800) {
    if (this.mode !== 'real') return Promise.resolve([]);
    return new Promise(resolve => {
      const socket = dgram.createSocket('udp4');
      const found = new Set();
      let finished = false;
      const message = Buffer.from(['M-SEARCH * HTTP/1.1','HOST: 239.255.255.250:1900','MAN: "ssdp:discover"','MX: 1','ST: upnp:rootdevice','',''].join('\r\n'));
      const finish = () => { if (finished) return; finished = true; try { socket.close(); } catch {} resolve([...found]); };
      socket.on('message', msg => {
        const location = msg.toString().match(/^LOCATION:\s*(.+)$/im)?.[1]?.trim();
        if (location) found.add(location);
      });
      socket.on('error', error => { this.record(typedError('HUE_SSDP_ERROR', 'SSDP-Suche ist fehlgeschlagen.', { cause: error.message })); finish(); });
      socket.bind(() => {
        try { socket.setBroadcast(true); socket.send(message, 1900, '239.255.255.250'); }
        catch (error) { this.record(typedError('HUE_SSDP_ERROR', 'SSDP-Anfrage konnte nicht gesendet werden.', { cause: error.message })); finish(); }
      });
      setTimeout(finish, timeoutMs);
    });
  }

  async pair() {
    if (!this.bridge) await this.discover();
    if (!this.bridge) throw typedError('HUE_NOT_FOUND', 'Keine Hue Bridge gefunden.');
    if (this.mode !== 'real') {
      if (this.simFault === 'link-button') throw typedError('HUE_LINK_BUTTON_REQUIRED', 'Simulation: Link-Taste wurde nicht bestätigt.');
      return { paired: true, bridge: this.bridge };
    }
    const response = await requestWithTimeout(`http://${this.bridge.ip}/api`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ devicetype: 'systemone_pi#admin' })
    }, 5000);
    if (!response.ok) throw typedError('HUE_HTTP_ERROR', `Hue-Pairing antwortet mit HTTP ${response.status}.`, { status: response.status });
    const result = await response.json();
    const username = result?.[0]?.success?.username;
    if (!username) throw typedError('HUE_LINK_BUTTON_REQUIRED', result?.[0]?.error?.description || 'Link-Taste der Hue Bridge drücken und erneut versuchen.');
    this.username = username;
    this.secrets.hueUsername = username;
    this.secrets.huePairedBridgeId = this.bridge.id;
    this.storage.saveSecrets(this.secrets);
    return { paired: true, bridge: this.bridge };
  }

  async fetchLights() {
    if (!this.bridge || !this.username) return [];
    if (this.mode !== 'real') {
      if (this.simFault === 'timeout') throw typedError('HUE_TIMEOUT', 'Simulation: Bridge-Zeitüberschreitung.');
      if (this.simFault === 'auth') throw typedError('HUE_AUTH_ERROR', 'Simulation: Hue-Credential ungültig.');
      if (this.simFault === 'offline') return this.demoDevices.map(device => this.normalizeLight({ ...device, online: false, syncError: 'Simulation: Gerät offline' }));
      return this.demoDevices.map(device => this.normalizeLight(device));
    }
    const response = await requestWithTimeout(`http://${this.bridge.ip}/api/${encodeURIComponent(this.username)}/lights`, {}, 3500);
    if (!response.ok) throw typedError('HUE_HTTP_ERROR', `Hue-Lichtliste antwortet mit HTTP ${response.status}.`, { status: response.status });
    const lights = await response.json();
    if (Array.isArray(lights) && lights[0]?.error) throw typedError('HUE_AUTH_ERROR', lights[0].error.description || 'Hue-Zugriff nicht autorisiert.');
    return Object.entries(lights).map(([id, light]) => this.normalizeLight({
      id: `hue-${id}`, hueId: id, integration: 'hue', type: 'light', sourceName: light.name || `Hue ${id}`,
      name: light.name || `Hue ${id}`, roomId: null, online: light.state?.reachable !== false,
      on: Boolean(light.state?.on), brightness: Math.max(1, Math.min(100, Math.round(((light.state?.bri || 1) / 254) * 100)))
    }));
  }

  normalizeLight(light) {
    if (light.profile && light.capabilities) return createDevice(light);
    return createDevice({
      id: light.id, integration: 'hue', manufacturer: 'Philips', model: light.model || 'Hue Light', profile: 'light',
      name: light.name, roomId: light.roomId || null, online: light.online !== false,
      availability: light.online === false ? 'offline' : 'online', compatibility: 'certified',
      capabilities: { power: Boolean(light.on), brightness: Number.isFinite(light.brightness) ? light.brightness : 1 },
      diagnostics: { lastSeen: light.online === false ? null : new Date().toISOString(), lastError: light.syncError || null },
      adapterData: { hueId: light.hueId }
    });
  }

  async listDevices() { return this.fetchLights(); }

  async applyCapabilities(device, patch) {
    const capabilities = validateCapabilities('light', patch, { partial: true });
    const legacy = {};
    if (typeof capabilities.power === 'boolean') legacy.on = capabilities.power;
    if (Number.isFinite(capabilities.brightness)) legacy.brightness = capabilities.brightness;
    const updated = await this.setLight(device, legacy);
    return { power: Boolean(updated.on), brightness: Number.isFinite(updated.brightness) ? updated.brightness : device.capabilities.brightness };
  }

  async setLight(device, patch) {
    if (!this.bridge || !this.username) throw typedError('HUE_NOT_PAIRED', 'Hue Bridge ist nicht gekoppelt.');
    if (this.mode !== 'real') {
      if (this.simFault === 'command') throw typedError('HUE_COMMAND_FAILED', 'Simulation: Hue-Befehl wurde abgelehnt.');
      if (!device.online) throw typedError('HUE_DEVICE_OFFLINE', `${device.name} ist offline.`);
      return { ...device, ...patch };
    }
    const body = {};
    if (typeof patch.on === 'boolean') body.on = patch.on;
    if (Number.isFinite(patch.brightness)) body.bri = Math.max(1, Math.min(254, Math.round((patch.brightness / 100) * 254)));
    if (!Object.keys(body).length) return device;
    const hueId = device.adapterData?.hueId || device.hueId;
    const response = await requestWithTimeout(`http://${this.bridge.ip}/api/${encodeURIComponent(this.username)}/lights/${encodeURIComponent(hueId)}/state`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    }, 3500);
    if (!response.ok) throw typedError('HUE_HTTP_ERROR', `Hue-Befehl antwortet mit HTTP ${response.status}.`, { status: response.status });
    const result = await response.json();
    const hueError = result.find(item => item.error)?.error;
    if (hueError) throw typedError('HUE_COMMAND_FAILED', hueError.description || 'Hue-Befehl fehlgeschlagen.');
    return { ...device, ...patch };
  }
}

module.exports = { HueAdapter, typedError, isPrivateIpv4 };
