const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const QRCode = require('qrcode');
const { LocalStorage } = require('./lib/storage');
const { HueAdapter } = require('./lib/hue');
const { Diagnostics } = require('./lib/diagnostics');
const { ReconnectController } = require('./lib/reconnect');
const { publicProfiles, validateCapabilities } = require('./lib/capabilities');
const { migrateLegacyDevice, publicDevice } = require('./lib/device-model');
const { DeviceRegistry } = require('./lib/device-registry');
const { SimulationAdapter } = require('./lib/simulation');
const { assertAdapter } = require('./lib/adapter');
const { createBackup, validateBackup } = require('./lib/backup');
const { AutomationEngine, TEMPLATES, validateAutomation } = require('./lib/automations');
const { AutomationScheduler } = require('./lib/scheduler');

const PORT = Number(process.env.PORT || 4170);
const PUBLIC_DIR = path.join(__dirname, 'web');
const DATA_DIR = process.env.SYSTEMONE_DATA_DIR || path.join(__dirname, 'data');
const diagnostics = new Diagnostics();
const storage = new LocalStorage(DATA_DIR, { onError: error => diagnostics.record(error.code, error.message, error.details) });
const reconnect = new ReconnectController({ diagnostics });

const DEVICE_PROFILES = publicProfiles();

const initialState = {
  system: { name: 'SystemONE Pi', version: '0.4.0', mode: 'local', online: true },
  onboarding: { completed: false, adminPaired: false, selectedTheme: 'Clear', pairingSession: null },
  integrations: { hue: { discovered: false, paired: false, bridge: null, lastSync: null, syncError: null, mode: 'simulation', reconnect: reconnect.snapshot() } },
  rooms: [{ id: 'living', name: 'Wohnzimmer' }, { id: 'office', name: 'Büro' }, { id: 'bedroom', name: 'Schlafzimmer' }],
  devices: [],
  automations: []
};

const persisted = storage.loadState(initialState);
const state = {
  ...initialState, ...persisted,
  system: { ...initialState.system, ...(persisted.system || {}), version: '0.4.0' },
  onboarding: { ...initialState.onboarding, ...(persisted.onboarding || {}), pairingSession: null },
  integrations: { ...initialState.integrations, ...(persisted.integrations || {}), hue: { ...initialState.integrations.hue, ...(persisted.integrations?.hue || {}), reconnect: reconnect.snapshot() } },
  rooms: Array.isArray(persisted.rooms) ? persisted.rooms : initialState.rooms,
  devices: Array.isArray(persisted.devices) ? persisted.devices.map(migrateLegacyDevice) : [],
  automations: Array.isArray(persisted.automations) ? persisted.automations : []
};

const demoDevices = [
  { id: 'hue-1', hueId: '1', integration: 'hue', type: 'light', sourceName: 'Stehlampe', name: 'Stehlampe', roomId: 'living', online: true, on: true, brightness: 72 },
  { id: 'hue-2', hueId: '2', integration: 'hue', type: 'light', sourceName: 'Schreibtisch', name: 'Schreibtisch', roomId: 'office', online: true, on: false, brightness: 35 }
];
const hue = new HueAdapter({ storage, demoDevices, diagnostics });
const simulation = new SimulationAdapter();
const adapters = new Map([['hue', assertAdapter(hue)], ['simulation', assertAdapter(simulation)]]);
const registry = new DeviceRegistry(state.devices);
state.integrations.hue.mode = hue.mode;

async function applyDeviceCapabilities(deviceId, capabilityPatch) {
  const device = registry.get(deviceId);
  if (!device) throw Object.assign(new Error('Gerät nicht gefunden.'), { code: 'DEVICE_NOT_FOUND' });
  if (!device.online) throw Object.assign(new Error(`${device.name} ist offline.`), { code: 'DEVICE_OFFLINE' });
  const adapter = adapters.get(device.integration);
  if (!adapter) throw Object.assign(new Error('Geräteadapter ist nicht verfügbar.'), { code: 'ADAPTER_NOT_FOUND' });
  const validated = validateCapabilities(device.profile, capabilityPatch, { partial: true });
  const applied = await adapter.applyCapabilities(device, validated);
  return registry.patch(device.id, { capabilities: applied, diagnostics: { lastSeen: new Date().toISOString(), lastError: null } });
}

const validPersistedAutomations = state.automations.flatMap(value => { try { return [validateAutomation(value, registry)]; } catch (error) { diagnostics.record('AUTOMATION_INVALID', 'Gespeicherte Automation wurde übersprungen.', { cause: error.message }); return []; } });
const automationEngine = new AutomationEngine({ registry, automations: validPersistedAutomations, executeAction: action => applyDeviceCapabilities(action.deviceId, action.capabilities) });
const scheduler = new AutomationScheduler({ engine: automationEngine });
state.automations = automationEngine.list();

function syncRegistryState() { state.devices = registry.list(); }
registry.on('device.added', syncRegistryState);
registry.on('device.updated', syncRegistryState);
registry.on('registry.changed', syncRegistryState);
automationEngine.on('changed', automations => { state.automations = automations; });
automationEngine.on('executed', automation => { if (automation.lastError) diagnostics.record('AUTOMATION_ACTION_FAILED', automation.lastError.message, { automationId: automation.id }); });

function updateReconnectState() { state.integrations.hue.reconnect = reconnect.snapshot(); }
function persist() {
  updateReconnectState();
  syncRegistryState();
  const safeState = JSON.parse(JSON.stringify(state));
  safeState.onboarding.pairingSession = null;
  storage.saveState(safeState);
}
function json(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify({ success: status < 400, data: status < 400 ? data : null, error: status >= 400 ? data : null }));
}
function publicState() { return { ...state, devices: registry.list({ publicOnly: true }), automations: automationEngine.list() }; }
function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => { body += chunk; if (body.length > 1024 * 1024) reject(Object.assign(new Error('Payload zu groß.'), { code: 'INVALID_REQUEST' })); });
    req.on('end', () => { if (!body) return resolve({}); try { resolve(JSON.parse(body)); } catch { reject(Object.assign(new Error('Ungültiges JSON.'), { code: 'INVALID_REQUEST' })); } });
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
  fs.createReadStream(filePath).pipe(res); return true;
}
function markHueOffline(error) {
  registry.list().filter(device => device.integration === 'hue').forEach(device => registry.patch(device.id, { online: false, availability: 'offline', diagnostics: { lastError: error.message } }));
  state.integrations.hue.lastSync = new Date().toISOString();
  state.integrations.hue.syncError = error.message;
  diagnostics.record(error.code || 'HUE_SYNC_FAILED', error.message, error.details || {});
  reconnect.failure(error); updateReconnectState();
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
    else reconnect.success();
    persist(); return state.integrations.hue;
  } catch (error) {
    diagnostics.record(error.code || 'HUE_NOT_FOUND', error.message, error.details || {});
    state.integrations.hue.syncError = error.message; reconnect.failure(error); persist(); return state.integrations.hue;
  }
}
async function syncHue() {
  if (!state.integrations.hue.paired) return state.devices;
  try {
    const lights = await hue.fetchLights();
    const oldById = new Map(registry.list().map(device => [device.id, device]));
    const synced = lights.map(light => { const previous = oldById.get(light.id); return { ...light, name: previous?.name || light.name, roomId: previous?.roomId || light.roomId || null }; });
    registry.replaceIntegration('hue', synced);
    state.integrations.hue.lastSync = new Date().toISOString(); state.integrations.hue.syncError = null; reconnect.success();
  } catch (error) { markHueOffline(error); }
  persist(); return state.devices;
}
async function createPairingSession() {
  const token = crypto.randomBytes(24).toString('base64url');
  const code = String(crypto.randomInt(100000, 1000000));
  const expiresAt = new Date(Date.now() + 5 * 60 * 1000).toISOString();
  const pairingUri = `systemone://pair?token=${token}&code=${code}`;
  const qrDataUrl = await QRCode.toDataURL(pairingUri, { errorCorrectionLevel: 'M', margin: 2, width: 240 });
  state.onboarding.pairingSession = { token, code, expiresAt, pairingUri, qrDataUrl };
  return state.onboarding.pairingSession;
}
function completePairing(body) {
  const session = state.onboarding.pairingSession;
  if (!session) throw Object.assign(new Error('Keine aktive Pairing-Sitzung.'), { code: 'PAIRING_SESSION_MISSING' });
  if (Date.parse(session.expiresAt) < Date.now()) throw Object.assign(new Error('Pairing-Sitzung ist abgelaufen.'), { code: 'PAIRING_SESSION_EXPIRED' });
  if (body.token !== session.token || String(body.code) !== session.code) throw Object.assign(new Error('Pairing-Code oder Token ist ungültig.'), { code: 'PAIRING_INVALID' });
  state.onboarding.adminPaired = true; state.onboarding.pairingSession = null; persist(); return { adminPaired: true };
}
function createSimulatedDevice(body) {
  const profile = DEVICE_PROFILES[body.profile || body.type] ? (body.profile || body.type) : null;
  if (!profile) throw Object.assign(new Error('Unbekanntes Geräteprofil.'), { code: 'DEVICE_PROFILE_INVALID' });
  const roomId = state.rooms.some(room => room.id === body.roomId) ? body.roomId : null;
  const device = simulation.create({ profile, name: body.name, roomId });
  registry.upsert(device); persist(); return publicDevice(device);
}
function exportBackup() { syncRegistryState(); return createBackup(state, state.system.version); }
function restoreBackup(input) {
  const backup = validateBackup(input);
  const snapshot = { rooms: structuredClone(state.rooms), devices: structuredClone(registry.list()), onboarding: structuredClone(state.onboarding) };
  try {
    state.rooms = backup.data.rooms;
    state.onboarding.selectedTheme = backup.data.onboarding.selectedTheme;
    registry.replaceIntegration('simulation', backup.data.devices);
    persist();
    return { restored: true, migrated: backup.migrated, schemaVersion: backup.schemaVersion, rooms: state.rooms.length, devices: backup.data.devices.length };
  } catch (error) {
    state.rooms = snapshot.rooms; state.onboarding = snapshot.onboarding;
    registry.devices.clear(); snapshot.devices.forEach(device => registry.upsert(device, { silent: true })); syncRegistryState();
    try { persist(); } catch {}
    throw Object.assign(new Error('Restore fehlgeschlagen; vorheriger Zustand wurde wiederhergestellt.'), { code: 'BACKUP_RESTORE_FAILED', details: { cause: error.message } });
  }
}
function setupStatus() {
  const health = diagnostics.health(state, hue);
  const steps = [
    { id: 'system', label: 'System lokal gestartet', done: true },
    { id: 'admin', label: 'Administrator gekoppelt', done: state.onboarding.adminPaired },
    { id: 'hue', label: hue.mode === 'real' ? 'Hue Bridge gekoppelt' : 'Hue-Simulation gekoppelt', done: state.integrations.hue.paired },
    { id: 'rooms', label: 'Mindestens ein Raum vorhanden', done: state.rooms.length > 0 },
    { id: 'devices', label: 'Mindestens ein Gerät getestet', done: state.devices.length > 0 },
    { id: 'diagnostics', label: 'Diagnose ohne kritischen Fehler', done: health.recentErrors.length === 0 }
  ];
  return { completed: steps.every(step => step.done), currentStep: steps.find(step => !step.done)?.id || 'complete', steps, hardwareSafe: hue.mode !== 'real' };
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    if (req.method === 'GET' && url.pathname === '/api/health') return json(res, 200, diagnostics.health(state, hue));
    if (req.method === 'GET' && url.pathname === '/api/diagnostics') return json(res, 200, { ...diagnostics.report(state, hue), reconnect: reconnect.snapshot() });
    if (req.method === 'GET' && url.pathname === '/api/setup') return json(res, 200, setupStatus());
    if (req.method === 'GET' && url.pathname === '/api/profiles') return json(res, 200, DEVICE_PROFILES);
    if (req.method === 'GET' && url.pathname === '/api/system') return json(res, 200, state.system);
    if (req.method === 'GET' && url.pathname === '/api/state') { if (url.searchParams.get('sync') === '1' && reconnect.state !== 'backoff') await syncHue(); updateReconnectState(); return json(res, 200, publicState()); }
    if (req.method === 'GET' && url.pathname === '/api/backup') return json(res, 200, exportBackup());
    if (req.method === 'GET' && url.pathname === '/api/automations/templates') return json(res, 200, TEMPLATES);
    if (req.method === 'GET' && url.pathname === '/api/automations/scheduler') return json(res, 200, scheduler.status());
    if (req.method === 'GET' && url.pathname === '/api/automations') return json(res, 200, automationEngine.list());
    if (req.method === 'POST' && url.pathname === '/api/automations') { const item = automationEngine.add(await readBody(req)); persist(); return json(res, 201, item); }
    if (req.method === 'POST' && url.pathname === '/api/automations/from-template') { const body = await readBody(req); const item = automationEngine.addFromTemplate(body.templateId, body); persist(); return json(res, 201, item); }
    const automationMatch = url.pathname.match(/^\/api\/automations\/([^/]+)$/);
    if (automationMatch && req.method === 'PATCH') { const body = await readBody(req); const item = automationEngine.setEnabled(automationMatch[1], body.enabled); if (!item) return json(res, 404, { code: 'AUTOMATION_NOT_FOUND', message: 'Automation nicht gefunden.' }); persist(); return json(res, 200, item); }
    if (automationMatch && req.method === 'DELETE') { if (!automationEngine.remove(automationMatch[1])) return json(res, 404, { code: 'AUTOMATION_NOT_FOUND', message: 'Automation nicht gefunden.' }); persist(); return json(res, 200, { deleted: true }); }
    if (req.method === 'POST' && url.pathname === '/api/onboarding/pair-admin/session') return json(res, 201, await createPairingSession());
    if (req.method === 'POST' && url.pathname === '/api/onboarding/pair-admin/complete') return json(res, 200, completePairing(await readBody(req)));
    if (req.method === 'GET' && url.pathname === '/api/integrations/hue/discover') return json(res, 200, await discoverHue());
    if (req.method === 'POST' && url.pathname === '/api/integrations/hue/sync') { reconnect.beginAttempt(); updateReconnectState(); return json(res, 200, await syncHue()); }
    if (req.method === 'POST' && url.pathname === '/api/integrations/hue/reconnect') { reconnect.beginAttempt(); updateReconnectState(); await discoverHue(); if (state.integrations.hue.paired) await syncHue(); return json(res, 200, state.integrations.hue); }
    if (req.method === 'POST' && url.pathname === '/api/integrations/hue/pair') {
      if (!state.integrations.hue.discovered) await discoverHue();
      const result = await hue.pair();
      state.integrations.hue.discovered = true; state.integrations.hue.paired = true; state.integrations.hue.bridge = result.bridge; state.integrations.hue.syncError = null;
      state.onboarding.completed = true; reconnect.success(); await syncHue(); persist(); return json(res, 200, state.integrations.hue);
    }
    if (req.method === 'POST' && url.pathname === '/api/devices/simulate') return json(res, 201, createSimulatedDevice(await readBody(req)));
    const deviceMatch = url.pathname.match(/^\/api\/devices\/([^/]+)$/);
    if (deviceMatch && req.method === 'PATCH') {
      const device = registry.get(deviceMatch[1]);
      if (!device) return json(res, 404, { code: 'DEVICE_NOT_FOUND', message: 'Gerät nicht gefunden.' });
      const body = await readBody(req);
      const capabilityPatch = body.capabilities ? validateCapabilities(device.profile, body.capabilities, { partial: true }) : {};
      if (Object.keys(capabilityPatch).length) {
        await applyDeviceCapabilities(device.id, capabilityPatch);
        await automationEngine.handleDeviceChange(device.id);
      }
      const metadata = {};
      if (typeof body.name === 'string' && body.name.trim()) metadata.name = body.name.trim().slice(0, 60);
      if (typeof body.roomId === 'string' && state.rooms.some(r => r.id === body.roomId)) metadata.roomId = body.roomId;
      if (Object.keys(metadata).length) registry.patch(device.id, metadata);
      persist(); return json(res, 200, publicDevice(registry.get(device.id)));
    }
    if (req.method === 'POST' && url.pathname === '/api/rooms') {
      const body = await readBody(req); const name = typeof body.name === 'string' ? body.name.trim().slice(0, 60) : '';
      if (!name) return json(res, 400, { code: 'ROOM_NAME_REQUIRED', message: 'Raumname fehlt.' });
      const base = name.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'room';
      let id = base, suffix = 2; while (state.rooms.some(room => room.id === id)) id = `${base}-${suffix++}`;
      const room = { id, name }; state.rooms.push(room); persist(); return json(res, 201, room);
    }
    if (req.method === 'POST' && url.pathname === '/api/backup/restore') {
      return json(res, 200, restoreBackup(await readBody(req)));
    }
    if (req.method === 'GET' && url.pathname === '/api/devices') return json(res, 200, registry.list({ publicOnly: true }));
    if (req.method === 'GET' && url.pathname === '/api/rooms') return json(res, 200, state.rooms);
    if (req.method === 'GET' && !url.pathname.startsWith('/api/') && serveStatic(req, res)) return;
    if (req.method === 'GET' && !url.pathname.startsWith('/api/')) { req.url = '/index.html'; if (serveStatic(req, res)) return; }
    return json(res, 404, { code: 'NOT_FOUND', message: 'Route nicht gefunden.' });
  } catch (error) {
    diagnostics.record(error.code || 'INTERNAL_ERROR', error.message || 'Unbekannter Fehler.', error.details || {});
    const conflictCodes = ['HUE_LINK_BUTTON_REQUIRED','PAIRING_SESSION_EXPIRED','PAIRING_INVALID','HUE_DEVICE_OFFLINE','DEVICE_OFFLINE'];
    return json(res, conflictCodes.includes(error.code) ? 409 : 400, { code: error.code || 'INTERNAL_ERROR', message: error.message || 'Ungültige Anfrage.' });
  }
});

server.listen(PORT, '0.0.0.0', async () => {
  console.log(`SystemONE Pi MVP v0.4.0 läuft auf http://localhost:${PORT} · Hue-Modus: ${hue.mode}`);
  if (hue.mode !== 'real') diagnostics.record('HUE_REAL_MODE_DISABLED', 'Sicherer Simulationsmodus aktiv: keine private Hue Bridge wird angesprochen.');
  scheduler.start();
  await discoverHue(); if (state.integrations.hue.paired) await syncHue();
});
setInterval(async () => {
  if (!state.integrations.hue.paired) return;
  if (reconnect.canRetry()) { reconnect.beginAttempt(); updateReconnectState(); await syncHue(); return; }
  if (reconnect.state !== 'backoff') await syncHue();
}, 3000).unref();
