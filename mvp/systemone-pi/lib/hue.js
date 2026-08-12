const dgram = require('dgram');

function isPrivateIpv4(host) {
  const match = String(host || '').match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!match) return false;
  const octets = match.slice(1).map(Number);
  if (octets.some(n => n < 0 || n > 255)) return false;
  const [a, b] = octets;
  return a === 10 || a === 127 || (a === 192 && b === 168) || (a === 172 && b >= 16 && b <= 31) || (a === 169 && b === 254);
}

function requestWithTimeout(url, options = {}, timeoutMs = 3000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal }).finally(() => clearTimeout(timer));
}

class HueAdapter {
  constructor({ storage, demoDevices = [] }) {
    this.storage = storage;
    this.demoDevices = demoDevices;
    this.secrets = storage.loadSecrets();
    this.bridge = this.secrets.hueBridge || null;
    this.username = this.secrets.hueUsername || null;
    this.mock = process.env.HUE_MODE === 'mock';
  }

  async discover() {
    const configuredIp = process.env.HUE_BRIDGE_IP || this.bridge?.ip;
    if (configuredIp) {
      const bridge = await this.verifyBridge(configuredIp);
      if (bridge) return this.rememberBridge(bridge);
    }
    if (this.mock) return this.rememberBridge({ id: 'hue-demo-001', name: 'Philips Hue Bridge (Demo)', ip: '127.0.0.1', status: 'ready', mock: true });

    const locations = await this.ssdpSearch();
    for (const location of locations) {
      try {
        const parsed = new URL(location);
        if (!isPrivateIpv4(parsed.hostname)) continue;
        const bridge = await this.verifyBridge(parsed.hostname);
        if (bridge) return this.rememberBridge(bridge);
      } catch {}
    }
    return null;
  }

  rememberBridge(bridge) {
    this.bridge = bridge;
    this.secrets.hueBridge = bridge;
    this.storage.saveSecrets(this.secrets);
    return bridge;
  }

  async verifyBridge(ip) {
    if (!isPrivateIpv4(ip) && ip !== '127.0.0.1') return null;
    try {
      const response = await requestWithTimeout(`http://${ip}/description.xml`);
      if (!response.ok) return null;
      const xml = await response.text();
      if (!/philips hue|signify/i.test(xml)) return null;
      const name = xml.match(/<friendlyName>([^<]+)<\/friendlyName>/i)?.[1] || 'Philips Hue Bridge';
      const id = xml.match(/<serialNumber>([^<]+)<\/serialNumber>/i)?.[1] || ip;
      return { id, name, ip, status: 'ready', mock: false };
    } catch {
      return null;
    }
  }

  ssdpSearch(timeoutMs = 1800) {
    return new Promise(resolve => {
      const socket = dgram.createSocket('udp4');
      const found = new Set();
      const message = Buffer.from([
        'M-SEARCH * HTTP/1.1',
        'HOST: 239.255.255.250:1900',
        'MAN: "ssdp:discover"',
        'MX: 1',
        'ST: upnp:rootdevice',
        '', ''
      ].join('\r\n'));
      const finish = () => { try { socket.close(); } catch {} resolve([...found]); };
      socket.on('message', msg => {
        const location = msg.toString().match(/^LOCATION:\s*(.+)$/im)?.[1]?.trim();
        if (location) found.add(location);
      });
      socket.on('error', finish);
      socket.bind(() => {
        socket.setBroadcast(true);
        socket.send(message, 1900, '239.255.255.250');
      });
      setTimeout(finish, timeoutMs);
    });
  }

  async pair() {
    if (!this.bridge) await this.discover();
    if (!this.bridge) throw Object.assign(new Error('Keine Hue Bridge gefunden.'), { code: 'HUE_NOT_FOUND' });
    if (this.bridge.mock) {
      this.username = 'demo-user';
      return { paired: true, bridge: this.bridge };
    }
    const response = await requestWithTimeout(`http://${this.bridge.ip}/api`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ devicetype: 'systemone_pi#admin' })
    }, 5000);
    const result = await response.json();
    const username = result?.[0]?.success?.username;
    if (!username) {
      const description = result?.[0]?.error?.description || 'Link-Taste der Hue Bridge drücken und erneut versuchen.';
      throw Object.assign(new Error(description), { code: 'HUE_LINK_BUTTON_REQUIRED' });
    }
    this.username = username;
    this.secrets.hueUsername = username;
    this.storage.saveSecrets(this.secrets);
    return { paired: true, bridge: this.bridge };
  }

  async fetchLights() {
    if (!this.bridge || !this.username) return [];
    if (this.bridge.mock) return this.demoDevices;
    try {
      const response = await requestWithTimeout(`http://${this.bridge.ip}/api/${encodeURIComponent(this.username)}/lights`, {}, 3500);
      if (!response.ok) throw new Error(`Hue HTTP ${response.status}`);
      const lights = await response.json();
      return Object.entries(lights).map(([id, light]) => ({
        id: `hue-${id}`,
        hueId: id,
        integration: 'hue',
        type: 'light',
        sourceName: light.name || `Hue ${id}`,
        name: light.name || `Hue ${id}`,
        roomId: null,
        online: light.state?.reachable !== false,
        on: Boolean(light.state?.on),
        brightness: Math.max(1, Math.min(100, Math.round(((light.state?.bri || 1) / 254) * 100)))
      }));
    } catch (error) {
      return this.demoDevices.map(device => ({ ...device, online: false, syncError: error.message }));
    }
  }

  async setLight(device, patch) {
    if (!this.bridge || !this.username) throw Object.assign(new Error('Hue Bridge ist nicht gekoppelt.'), { code: 'HUE_NOT_PAIRED' });
    if (this.bridge.mock) return { ...device, ...patch };
    const body = {};
    if (typeof patch.on === 'boolean') body.on = patch.on;
    if (Number.isFinite(patch.brightness)) body.bri = Math.max(1, Math.min(254, Math.round((patch.brightness / 100) * 254)));
    if (!Object.keys(body).length) return device;
    const response = await requestWithTimeout(`http://${this.bridge.ip}/api/${encodeURIComponent(this.username)}/lights/${encodeURIComponent(device.hueId)}/state`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    }, 3500);
    if (!response.ok) throw new Error(`Hue HTTP ${response.status}`);
    const result = await response.json();
    const hueError = result.find(item => item.error)?.error;
    if (hueError) throw Object.assign(new Error(hueError.description || 'Hue-Befehl fehlgeschlagen.'), { code: 'HUE_COMMAND_FAILED' });
    return { ...device, ...patch };
  }
}

module.exports = { HueAdapter };
