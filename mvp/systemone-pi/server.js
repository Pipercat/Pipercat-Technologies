const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { LocalStorage } = require('./lib/storage');
const { HueAdapter } = require('./lib/hue');
const { Diagnostics } = require('./lib/diagnostics');

const PORT = Number(process.env.PORT || 4170);
const PUBLIC_DIR = path.join(__dirname, 'web');
const DATA_DIR = process.env.SYSTEMONE_DATA_DIR || path.join(__dirname, 'data');
const storage = new LocalStorage(DATA_DIR);
const diagnostics = new Diagnostics();

const DEVICE_PROFILES = {
  light: { label: 'Licht', capabilities: ['on', 'brightness'] },
  switch: { label: 'Steckdose / Schalter', capabilities: ['on'] },
  sensor: { label: 'Sensor', capabilities: ['value', 'unit'] },
  thermostat: { label: 'Heizung / Thermostat', capabilities: ['temperature', 'targetTemperature'] },
  blind: { label: 'Rollladen / Jalousie', capabilities: ['position'] }
};

const initialState = {
  system: { name: 'SystemONE Pi', version: '0.3.0', mode: 'local', online: true },
  onboarding: { completed: false, adminPaired: false, selectedTheme: 'Clear', pairingSession: null },
  integrations: { hue: { discovered: false, paired: false, bridge: null, lastSync: null, syncError: null, mode: 'simulation' } },
  rooms: [{ id: 'living', name: 'Wohnzimmer' }, { id: 'office', name: 'Büro' }, { id: 'bedroom', name: 'Schlafzimmer' }],
  devices: []
};

const persisted = storage.loadState(initialState);
const state = {
  ...initialState, ...persisted,
  system: { ...initialState.system, ...(persisted.system || {}), version: '0.3.0' },
  onboarding: { ...initialState.onboarding, ...(persisted.onboarding || {}), pairingSession: null },
  integrations: { ...initialState.integrations, ...(persisted.integrations || {}), hue: { ...initialState.integrations.hue, ...(persisted.integrations?.hue || {}) } },
  rooms: Array.isArray(persisted.rooms) ? persisted.rooms : initialState.rooms,
  devices: Array.isArray(persisted.devices) ? persisted.devices : []
};

const demoDevices = [
  { id: 'hue-1', hueId: '1', integration: 'hue', type: 'light', sourceName: 'Stehlampe', name: 'Stehlampe', roomId: 'living', online: true, on: true, brightness: 72 },
  { id: 'hue-2', hueId: '2', integration: 'hue', type: 'light', sourceName: 'Schreibtisch', name: 'Schreibtisch', roomId: 'office', online: true, on: false, brightness: 35 }
];
const hue = new HueAdapter({ storage, demoDevices, diagnostics });
state.integrations.hue.mode = hue.mode;

function persist() {
  const safeState = JSON.parse(JSON.stringify(state));
  safeState.onboarding.pairingSession = null;
  storage.saveState(safeState);
}

function json(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify({ success: status < 400, data: status < 400 ? data : null, error: status >= 400 ? data : null }));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => {
      body += chunk;
      if (body.length > 1024 * 1024) reject(Object.assign(new Error('Payload zu groß.'), { code: 'INVALID_REQUEST' }));
    });
    req.on('end', () => {
      if (!body) return resolve({});
      try { resolve(JSON.parse(body)); } catch { reject(Object.assign(new Error('Ungültiges JSON.'), { code: 'INVALID_REQUEST' })); }
    });
    req.on('error', reject);
  });
}

function serveStatic(req, res) {
  const rawPath = req.url === '/' ? '/index.html' : req.url.split('?')[0];
  const normalized = path.normalize(rawPath).replace(/^([.][.][/\\])+/, '');
  const filePath = path.join(PUBLIC_DIR, normalized);
  if (!filePath.startsWith(PUBLIC_DIR) || !fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) return false;
  const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript', '.svg': 'image/svg+xml' };
  res.writeHead(200, { 'Content-Type': `${types[path.extname(filePath)] || 'application/octet-stream'}; charset=utf-8` });
  fs.createReadStream(filePath).pipe(res);
  return true;
}

function markHueOffline(error) {
  state.devices = state.devices.map(device => device.integration === 'hue' ? { ...device, online: false, syncError: error.message } : device);
  state.integrations.hue.lastSync = new Date().toISOString();
  state.integrations.hue.syncError = error.message;
  diagnostics.record(error.code || 'HUE_SYNC_FAILED', error.message, error.details || {});
}

async function discoverHue() {
  try {
    const bridge = await hue.discover();
    state.integrations.hue.discovered = Boolean(bridge);
    state.integrations.hue.bridge = bridge;
    state.integrations.hue.paired = Boolean(bridge && hue.isPairedWithCurrentBridge());
    state.integrations.hue.mode = hue.mode;
    state.integrations.hue.syncError = bridge ? null : 'Keine Hue Bridge gefunden.';
    if (!bridge) diagnostics.record('HUE_NOT_FOUND', 'Keine Hue Bridge gefunden.', { mode: hue.mode });
    persist();
    return state.integrations.hue;
  } catch (error) {
    diagnostics.record(error.code || 'HUE_NOT_FOUND', error.message, error.details || {});
    state.integrations.hue.syncError = error.message;
    persist();
    return state.integrations.hue;
  }
}

async function syncHue() {
  if (!state.integrations.hue.paired) return state.devices;
  try {
    const lights = await hue.fetchLights();
    const oldById = new Map(state.devices.map(device => [device.id, device]));
    const nonHue = state.devices.filter(device => device.integration !== 'hue');
    const synced = lights.map(light => {
      const previous = oldById.get(light.id);
      return { ...light, name: previous?.name || light.name, roomId: previous?.roomId || light.roomId || null, syncError: light.syncError || null };
    });
    state.devices = [...nonHue, ...synced];
    state.integrations.hue.lastSync = new Date().toISOString();
    state.integrations.hue.syncError = null;
  } catch (error) { markHueOffline(error); }
  persist();
  return state.devices;
}

function createPairingSession() {
  const token = crypto.randomBytes(24).toString('base64url');
  const code = String(crypto.randomInt(100000, 1000000));
  const expiresAt = new Date(Date.now() + 5 * 60 * 1000).toISOString();
  state.onboarding.pairingSession = { token, code, expiresAt, pairingUri: `systemone://pair?token=${token}&code=${code}` };
  return state.onboarding.pairingSession;
}

function completePairing(body) {
  const session = state.onboarding.pairingSession;
  if (!session) throw Object.assign(new Error('Keine aktive Pairing-Sitzung.'), { code: 'PAIRING_SESSION_MISSING' });
  if (Date.parse(session.expiresAt) < Date.now()) throw Object.assign(new Error('Pairing-Sitzung ist abgelaufen.'), { code: 'PAIRING_SESSION_EXPIRED' });
  if (body.token !== session.token || String(body.code) !== session.code) throw Object.assign(new Error('Pairing-Code oder Token ist ungültig.'), { code: 'PAIRING_INVALID' });
  state.onboarding.adminPaired = true;
  state.onboarding.pairingSession = null;
  persist();
  return { adminPaired: true };
}

function createSimulatedDevice(body) {
  const type = DEVICE_PROFILES[body.type] ? body.type : null;
  if (!type) throw Object.assign(new Error('Unbekanntes Geräteprofil.'), { code: 'DEVICE_PROFILE_INVALID' });
  const roomId = state.rooms.some(room => room.id === body.roomId) ? body.roomId : null;
  const id = `sim-${type}-${crypto.randomBytes(4).toString('hex')}`;
  const base = { id, integration: 'simulation', type, name: String(body.name || DEVICE_PROFILES[type].label).slice(0, 60), roomId, online: true };
  if (type === 'light') Object.assign(base, { on: false, brightness: 50 });
  if (type === 'switch') Object.assign(base, { on: false });
  if (type === 'sensor') Object.assign(base, { value: 21.4, unit: '°C' });
  if (type === 'thermostat') Object.assign(base, { temperature: 20.8, targetTemperature: 21 });
  if (type === 'blind') Object.assign(base, { position: 50 });
  state.devices.push(base); persist(); return base;
}

function applyGenericPatch(device, body) {
  if (typeof body.name === 'string' && body.name.trim()) device.name = body.name.trim().slice(0, 60);
  if (typeof body.roomId === 'string' && state.rooms.some(r => r.id === body.roomId)) device.roomId = body.roomId;
  if (device.integration === 'simulation') {
    if (typeof body.on === 'boolean' && ['light', 'switch'].includes(device.type)) device.on = body.on;
    if (Number.isFinite(body.brightness) && device.type === 'light') device.brightness = Math.max(1, Math.min(100, Math.round(body.brightness)));
    if (Number.isFinite(body.targetTemperature) && device.type === 'thermostat') device.targetTemperature = Math.max(5, Math.min(35, Number(body.targetTemperature.toFixed(1))));
    if (Number.isFinite(body.position) && device.type === 'blind') device.position = Math.max(0, Math.min(100, Math.round(body.position)));
  }
}

function exportBackup() {
  return { format: 'systemone-backup', version: 1, createdAt: new Date().toISOString(), state: { rooms: state.rooms, devices: state.devices.filter(d => d.integration !== 'hue'), onboarding: { selectedTheme: state.onboarding.selectedTheme } } };
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);

    if (req.method === 'GET' && url.pathname === '/api/health') return json(res, 200, diagnostics.health(state, hue));
    if (req.method === 'GET' && url.pathname === '/api/diagnostics') return json(res, 200, diagnostics.report(state, hue));
    if (req.method === 'GET' && url.pathname === '/api/profiles') return json(res, 200, DEVICE_PROFILES);
    if (req.method === 'GET' && url.pathname === '/api/system') return json(res, 200, state.system);
    if (req.method === 'GET' && url.pathname === '/api/state') { if (url.searchParams.get('sync') === '1') await syncHue(); return json(res, 200, state); }
    if (req.method === 'GET' && url.pathname === '/api/backup') return json(res, 200, exportBackup());

    if (req.method === 'POST' && url.pathname === '/api/onboarding/pair-admin/session') return json(res, 201, createPairingSession());
    if (req.method === 'POST' && url.pathname === '/api/onboarding/pair-admin/complete') return json(res, 200, completePairing(await readBody(req)));
    if (req.method === 'GET' && url.pathname === '/api/integrations/hue/discover') return json(res, 200, await discoverHue());
    if (req.method === 'POST' && url.pathname === '/api/integrations/hue/sync') return json(res, 200, await syncHue());

    if (req.method === 'POST' && url.pathname === '/api/integrations/hue/pair') {
      if (!state.integrations.hue.discovered) await discoverHue();
      const result = await hue.pair();
      state.integrations.hue.discovered = true; state.integrations.hue.paired = true; state.integrations.hue.bridge = result.bridge; state.integrations.hue.syncError = null;
      state.onboarding.completed = true; await syncHue(); persist(); return json(res, 200, state.integrations.hue);
    }

    if (req.method === 'POST' && url.pathname === '/api/devices/simulate') return json(res, 201, createSimulatedDevice(await readBody(req)));

    const deviceMatch = url.pathname.match(/^\/api\/devices\/([^/]+)$/);
    if (deviceMatch && req.method === 'PATCH') {
      const device = state.devices.find(d => d.id === deviceMatch[1]);
      if (!device) return json(res, 404, { code: 'DEVICE_NOT_FOUND', message: 'Gerät nicht gefunden.' });
      const body = await readBody(req);
      if (device.integration === 'hue' && (typeof body.on === 'boolean' || Number.isFinite(body.brightness))) {
        if (!device.online) return json(res, 409, { code: 'HUE_DEVICE_OFFLINE', message: `${device.name} ist offline.` });
        Object.assign(device, await hue.setLight(device, body));
      }
      applyGenericPatch(device, body); persist(); return json(res, 200, device);
    }

    if (req.method === 'POST' && url.pathname === '/api/rooms') {
      const body = await readBody(req); const name = typeof body.name === 'string' ? body.name.trim().slice(0, 60) : '';
      if (!name) return json(res, 400, { code: 'ROOM_NAME_REQUIRED', message: 'Raumname fehlt.' });
      const base = name.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'room';
      let id = base, suffix = 2; while (state.rooms.some(room => room.id === id)) id = `${base}-${suffix++}`;
      const room = { id, name }; state.rooms.push(room); persist(); return json(res, 201, room);
    }

    if (req.method === 'POST' && url.pathname === '/api/backup/restore') {
      const body = await readBody(req);
      if (body?.format !== 'systemone-backup' || body?.version !== 1 || !body?.state) return json(res, 400, { code: 'BACKUP_INVALID', message: 'Backup-Format ist ungültig.' });
      if (!Array.isArray(body.state.rooms) || !Array.isArray(body.state.devices)) return json(res, 400, { code: 'BACKUP_INVALID', message: 'Backup enthält ungültige Daten.' });
      state.rooms = body.state.rooms.slice(0, 100).map(r => ({ id: String(r.id).slice(0, 80), name: String(r.name).slice(0, 60) }));
      state.devices = state.devices.filter(d => d.integration === 'hue').concat(body.state.devices.filter(d => d.integration === 'simulation').slice(0, 500));
      persist(); return json(res, 200, { restored: true, rooms: state.rooms.length, devices: state.devices.length });
    }

    if (req.method === 'GET' && url.pathname === '/api/devices') return json(res, 200, state.devices);
    if (req.method === 'GET' && url.pathname === '/api/rooms') return json(res, 200, state.rooms);
    if (req.method === 'GET' && !url.pathname.startsWith('/api/') && serveStatic(req, res)) return;
    if (req.method === 'GET' && !url.pathname.startsWith('/api/')) { req.url = '/index.html'; if (serveStatic(req, res)) return; }
    return json(res, 404, { code: 'NOT_FOUND', message: 'Route nicht gefunden.' });
  } catch (error) {
    diagnostics.record(error.code || 'INTERNAL_ERROR', error.message || 'Unbekannter Fehler.', error.details || {});
    const conflictCodes = ['HUE_LINK_BUTTON_REQUIRED','PAIRING_SESSION_EXPIRED','PAIRING_INVALID','HUE_DEVICE_OFFLINE'];
    return json(res, conflictCodes.includes(error.code) ? 409 : 400, { code: error.code || 'INTERNAL_ERROR', message: error.message || 'Ungültige Anfrage.' });
  }
});

server.listen(PORT, '0.0.0.0', async () => {
  console.log(`SystemONE Pi MVP v0.3 läuft auf http://localhost:${PORT} · Hue-Modus: ${hue.mode}`);
  if (hue.mode !== 'real') diagnostics.record('HUE_REAL_MODE_DISABLED', 'Sicherer Simulationsmodus aktiv: keine private Hue Bridge wird angesprochen.');
  await discoverHue();
  if (state.integrations.hue.paired) await syncHue();
});

setInterval(() => { if (state.integrations.hue.paired) syncHue().catch(error => markHueOffline(error)); }, 3000).unref();
