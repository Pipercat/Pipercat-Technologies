const http = require('http');
const fs = require('fs');
const path = require('path');
const { LocalStorage } = require('./lib/storage');
const { HueAdapter } = require('./lib/hue');

const PORT = Number(process.env.PORT || 4170);
const PUBLIC_DIR = path.join(__dirname, 'web');
const DATA_DIR = process.env.SYSTEMONE_DATA_DIR || path.join(__dirname, 'data');
const storage = new LocalStorage(DATA_DIR);

const initialState = {
  system: { name: 'SystemONE Pi', version: '0.2.0', mode: 'local', online: true },
  onboarding: { completed: false, adminPaired: false, selectedTheme: 'Clear' },
  integrations: { hue: { discovered: false, paired: false, bridge: null, lastSync: null, syncError: null } },
  rooms: [
    { id: 'living', name: 'Wohnzimmer' },
    { id: 'office', name: 'Büro' },
    { id: 'bedroom', name: 'Schlafzimmer' }
  ],
  devices: []
};

const persisted = storage.loadState(initialState);
const state = {
  ...initialState,
  ...persisted,
  system: { ...initialState.system, ...(persisted.system || {}), version: '0.2.0' },
  onboarding: { ...initialState.onboarding, ...(persisted.onboarding || {}) },
  integrations: {
    ...initialState.integrations,
    ...(persisted.integrations || {}),
    hue: { ...initialState.integrations.hue, ...(persisted.integrations?.hue || {}) }
  },
  rooms: Array.isArray(persisted.rooms) ? persisted.rooms : initialState.rooms,
  devices: Array.isArray(persisted.devices) ? persisted.devices : []
};

const demoDevices = [
  { id: 'hue-1', hueId: '1', integration: 'hue', type: 'light', sourceName: 'Stehlampe', name: 'Stehlampe', roomId: 'living', online: true, on: true, brightness: 72 },
  { id: 'hue-2', hueId: '2', integration: 'hue', type: 'light', sourceName: 'Schreibtisch', name: 'Schreibtisch', roomId: 'office', online: true, on: false, brightness: 35 }
];
const hue = new HueAdapter({ storage, demoDevices });

function persist() {
  storage.saveState(state);
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
      if (body.length > 1024 * 1024) reject(new Error('Payload too large'));
    });
    req.on('end', () => {
      if (!body) return resolve({});
      try { resolve(JSON.parse(body)); } catch { reject(new Error('Invalid JSON')); }
    });
    req.on('error', reject);
  });
}

function serveStatic(req, res) {
  const rawPath = req.url === '/' ? '/index.html' : req.url.split('?')[0];
  const normalized = path.normalize(rawPath).replace(/^([.][.][/\\])+/, '');
  const filePath = path.join(PUBLIC_DIR, normalized);
  if (!filePath.startsWith(PUBLIC_DIR)) return false;
  if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) return false;
  const ext = path.extname(filePath);
  const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript', '.svg': 'image/svg+xml' };
  res.writeHead(200, { 'Content-Type': `${types[ext] || 'application/octet-stream'}; charset=utf-8` });
  fs.createReadStream(filePath).pipe(res);
  return true;
}

async function discoverHue() {
  const bridge = await hue.discover();
  state.integrations.hue.discovered = Boolean(bridge);
  state.integrations.hue.bridge = bridge;
  state.integrations.hue.paired = Boolean(bridge && hue.isPairedWithCurrentBridge());
  state.integrations.hue.syncError = bridge ? null : 'Keine lokale Hue Bridge gefunden.';
  persist();
  return state.integrations.hue;
}

async function syncHue() {
  if (!state.integrations.hue.paired) return state.devices;
  try {
    const lights = await hue.fetchLights();
    const oldById = new Map(state.devices.map(device => [device.id, device]));
    state.devices = lights.map(light => {
      const previous = oldById.get(light.id);
      return {
        ...light,
        name: previous?.name || light.name,
        roomId: previous?.roomId || light.roomId || null,
        syncError: null
      };
    });
    state.integrations.hue.lastSync = new Date().toISOString();
    state.integrations.hue.syncError = null;
  } catch (error) {
    state.devices = state.devices.map(device => device.integration === 'hue'
      ? { ...device, online: false, syncError: error.message }
      : device);
    state.integrations.hue.lastSync = new Date().toISOString();
    state.integrations.hue.syncError = error.message;
  }
  persist();
  return state.devices;
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);

    if (req.method === 'GET' && url.pathname === '/api/health') {
      return json(res, 200, { status: 'ok', localOnly: true, version: state.system.version, timestamp: new Date().toISOString() });
    }
    if (req.method === 'GET' && url.pathname === '/api/system') return json(res, 200, state.system);
    if (req.method === 'GET' && url.pathname === '/api/state') {
      if (url.searchParams.get('sync') === '1') await syncHue();
      return json(res, 200, state);
    }
    if (req.method === 'GET' && url.pathname === '/api/integrations/hue/discover') return json(res, 200, await discoverHue());
    if (req.method === 'POST' && url.pathname === '/api/integrations/hue/sync') return json(res, 200, await syncHue());

    if (req.method === 'POST' && url.pathname === '/api/onboarding/pair-admin') {
      state.onboarding.adminPaired = true;
      persist();
      return json(res, 200, state.onboarding);
    }

    if (req.method === 'POST' && url.pathname === '/api/integrations/hue/pair') {
      if (!state.integrations.hue.discovered) await discoverHue();
      const result = await hue.pair();
      state.integrations.hue.discovered = true;
      state.integrations.hue.paired = true;
      state.integrations.hue.bridge = result.bridge;
      state.integrations.hue.syncError = null;
      state.onboarding.completed = true;
      await syncHue();
      persist();
      return json(res, 200, state.integrations.hue);
    }

    const lightMatch = url.pathname.match(/^\/api\/devices\/([^/]+)$/);
    if (lightMatch && req.method === 'PATCH') {
      const device = state.devices.find(d => d.id === lightMatch[1]);
      if (!device) return json(res, 404, { code: 'DEVICE_NOT_FOUND', message: 'Gerät nicht gefunden.' });
      const body = await readBody(req);
      const hardwarePatch = {};
      if (typeof body.on === 'boolean') hardwarePatch.on = body.on;
      if (Number.isFinite(body.brightness)) hardwarePatch.brightness = Math.max(1, Math.min(100, Math.round(body.brightness)));
      if (Object.keys(hardwarePatch).length) {
        if (!device.online) return json(res, 409, { code: 'DEVICE_OFFLINE', message: `${device.name} ist offline.` });
        const updated = await hue.setLight(device, hardwarePatch);
        Object.assign(device, updated);
      }
      if (typeof body.name === 'string' && body.name.trim()) device.name = body.name.trim().slice(0, 60);
      if (typeof body.roomId === 'string' && state.rooms.some(r => r.id === body.roomId)) device.roomId = body.roomId;
      persist();
      return json(res, 200, device);
    }

    if (req.method === 'POST' && url.pathname === '/api/rooms') {
      const body = await readBody(req);
      const name = typeof body.name === 'string' ? body.name.trim().slice(0, 60) : '';
      if (!name) return json(res, 400, { code: 'ROOM_NAME_REQUIRED', message: 'Raumname fehlt.' });
      const base = name.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'room';
      let id = base;
      let suffix = 2;
      while (state.rooms.some(room => room.id === id)) id = `${base}-${suffix++}`;
      const room = { id, name };
      state.rooms.push(room);
      persist();
      return json(res, 201, room);
    }

    if (req.method === 'GET' && url.pathname === '/api/devices') return json(res, 200, state.devices);
    if (req.method === 'GET' && url.pathname === '/api/rooms') return json(res, 200, state.rooms);

    if (req.method === 'GET' && !url.pathname.startsWith('/api/') && serveStatic(req, res)) return;
    if (req.method === 'GET' && !url.pathname.startsWith('/api/')) {
      req.url = '/index.html';
      if (serveStatic(req, res)) return;
    }
    return json(res, 404, { code: 'NOT_FOUND', message: 'Route nicht gefunden.' });
  } catch (error) {
    const status = error.code === 'HUE_LINK_BUTTON_REQUIRED' ? 409 : 400;
    return json(res, status, { code: error.code || 'BAD_REQUEST', message: error.message || 'Ungültige Anfrage.' });
  }
});

server.listen(PORT, '0.0.0.0', async () => {
  console.log(`SystemONE Pi MVP v0.2 läuft lokal auf http://localhost:${PORT}`);
  try {
    await discoverHue();
    if (state.integrations.hue.paired) await syncHue();
  } catch (error) {
    console.warn(`Hue-Startsync übersprungen: ${error.message}`);
  }
});

setInterval(() => {
  if (state.integrations.hue.paired) syncHue().catch(error => {
    state.integrations.hue.syncError = error.message;
  });
}, 3000).unref();
