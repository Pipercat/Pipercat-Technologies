const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = Number(process.env.PORT || 4170);
const PUBLIC_DIR = path.join(__dirname, 'web');

const state = {
  system: { name: 'SystemONE Pi', version: '0.1.0', mode: 'local', online: true },
  onboarding: { completed: false, adminPaired: false, selectedTheme: 'Clear' },
  integrations: {
    hue: {
      discovered: true,
      paired: false,
      bridge: { id: 'hue-demo-001', name: 'Philips Hue Bridge', ip: '192.168.178.42', status: 'ready' }
    }
  },
  rooms: [
    { id: 'living', name: 'Wohnzimmer' },
    { id: 'office', name: 'Büro' }
  ],
  devices: [
    { id: 'light-1', integration: 'hue', type: 'light', name: 'Stehlampe', roomId: 'living', online: true, on: true, brightness: 72 },
    { id: 'light-2', integration: 'hue', type: 'light', name: 'Schreibtisch', roomId: 'office', online: false, on: false, brightness: 35 }
  ]
};

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

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);

    if (req.method === 'GET' && url.pathname === '/api/health') {
      return json(res, 200, { status: 'ok', localOnly: true, timestamp: new Date().toISOString() });
    }
    if (req.method === 'GET' && url.pathname === '/api/system') return json(res, 200, state.system);
    if (req.method === 'GET' && url.pathname === '/api/state') return json(res, 200, state);
    if (req.method === 'GET' && url.pathname === '/api/integrations/hue/discover') return json(res, 200, state.integrations.hue);

    if (req.method === 'POST' && url.pathname === '/api/onboarding/pair-admin') {
      state.onboarding.adminPaired = true;
      return json(res, 200, state.onboarding);
    }

    if (req.method === 'POST' && url.pathname === '/api/integrations/hue/pair') {
      if (!state.integrations.hue.discovered) return json(res, 409, { code: 'HUE_NOT_FOUND', message: 'Keine Hue Bridge gefunden.' });
      state.integrations.hue.paired = true;
      state.onboarding.completed = true;
      return json(res, 200, state.integrations.hue);
    }

    const lightMatch = url.pathname.match(/^\/api\/devices\/([^/]+)$/);
    if (lightMatch && req.method === 'PATCH') {
      const device = state.devices.find(d => d.id === lightMatch[1]);
      if (!device) return json(res, 404, { code: 'DEVICE_NOT_FOUND', message: 'Gerät nicht gefunden.' });
      if (!device.online) return json(res, 409, { code: 'DEVICE_OFFLINE', message: `${device.name} ist offline.` });
      const body = await readBody(req);
      if (typeof body.on === 'boolean') device.on = body.on;
      if (Number.isFinite(body.brightness)) device.brightness = Math.max(1, Math.min(100, Math.round(body.brightness)));
      if (typeof body.name === 'string' && body.name.trim()) device.name = body.name.trim().slice(0, 60);
      if (typeof body.roomId === 'string' && state.rooms.some(r => r.id === body.roomId)) device.roomId = body.roomId;
      return json(res, 200, device);
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
    return json(res, 400, { code: 'BAD_REQUEST', message: error.message || 'Ungültige Anfrage.' });
  }
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`SystemONE Pi MVP v0.1 läuft lokal auf http://localhost:${PORT}`);
});
