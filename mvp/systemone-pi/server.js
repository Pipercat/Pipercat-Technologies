const http = require('http');
const https = require('https');
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
const { createBackup, validateBackup, summarizeBackup } = require('./lib/backup');
const { BackupManager } = require('./lib/backup-manager');
const { AutomationEngine, TEMPLATES, validateAutomation, builderOptions } = require('./lib/automations');
const { AutomationScheduler } = require('./lib/scheduler');
const { validateLocation, calculateSolarEvents } = require('./lib/solar');
const { THEMES, validateTheme } = require('./lib/themes');
const { availableIntegrations, discoverCandidates, validateOnboardingRequest } = require('./lib/device-onboarding');
const { publicCompatibilityCatalog } = require('./lib/compatibility');
const { migrateOnboardingState, advanceOnboarding, resetOnboarding } = require('./lib/onboarding-state');
const { createSession, assertSessionCanStart, verifySession, publicSession } = require('./lib/admin-pairing');
const { LocalSessionStore } = require('./lib/local-sessions');
const { displayState } = require('./lib/display-state');
const { defaultDashboard, validateDashboard, migrateDashboard } = require('./lib/dashboard-layout');
const { DEFAULT_LOCALE, validateLocale, localeCatalog, messagesFor } = require('./lib/i18n');
const { normalizedDeviceEvent } = require('./lib/device-events');
const { securityHeaders, validateHost, validateWriteRequest, RateLimiter } = require('./lib/web-security');
const { AuditLog } = require('./lib/audit-log');
const { certificateStatus } = require('./lib/tls-identity');
const { validateUpdatePackage, approveUpdate } = require('./lib/update-package');
const { createSlotState, stageUpdate, activateStaged, reportBootHealth, recoverInterruptedBoot } = require('./lib/update-slots');
const { createDiagnosticPackage, previewDiagnosticPackage } = require('./lib/diagnostic-export');
const { CameraModule } = require('./lib/camera-module');
const { PiHoleModule } = require('./lib/pihole-module');
const { createYouDoModules } = require('./lib/module-registry');
const { GoveeAdapter, LOCAL_MODEL_ALLOWLIST, CLOUD_ONLY_EXCLUDED } = require('./lib/govee');
const { publicPilotPlan } = require('./lib/integration-pilots');
const { API_VERSION, normalizeApiPath, responseEnvelope, publicContract } = require('./lib/api-contract');
const { shouldServeAppShell, staticResponseHeaders } = require('./lib/http-routing');

const PORT = Number(process.env.PORT || 4170);
const PUBLIC_DIR = path.join(__dirname, 'web');
const DOCS_DIR = path.join(__dirname, 'docs');
const DATA_DIR = process.env.SYSTEMONE_DATA_DIR || path.join(__dirname, 'data');
const diagnostics = new Diagnostics();
const updatePublicKey=process.env.UPDATE_PUBLIC_KEY_PATH&&fs.existsSync(process.env.UPDATE_PUBLIC_KEY_PATH)?fs.readFileSync(process.env.UPDATE_PUBLIC_KEY_PATH,'utf8'):process.env.UPDATE_PUBLIC_KEY?.replace(/\\n/g,'\n')||null;
const storage = new LocalStorage(DATA_DIR, { onError: error => diagnostics.record(error.code, error.message, error.details) });
const reconnect = new ReconnectController({ diagnostics });
const cameras=new CameraModule({dataDir:DATA_DIR,enabled:process.env.CAMERA_MODULE_ENABLED==='true',mode:process.env.CAMERA_MODE||'simulation'});
const pihole=new PiHoleModule({enabled:process.env.PIHOLE_MODULE_ENABLED==='true',mode:process.env.PIHOLE_MODE||'simulation',baseUrl:process.env.PIHOLE_BASE_URL,token:process.env.PIHOLE_API_TOKEN});
const modules=createYouDoModules();
const backupManager=new BackupManager({localDir:path.join(DATA_DIR,'backups'),retentionCount:process.env.BACKUP_RETENTION_COUNT||7,retentionDays:process.env.BACKUP_RETENTION_DAYS||30,allowedRoots:String(process.env.SYSTEMONE_EXPORT_ROOTS||'').split(path.delimiter).filter(Boolean)});
let lastBackupRestoreTest=null;

const DEVICE_PROFILES = publicProfiles();

const initialState = {
  system: { name: 'SystemONE Pi', version: '0.4.0', mode: 'local', online: true },
  onboarding: { completed: false, adminPaired: false, selectedTheme: 'Clear', locale: DEFAULT_LOCALE, pairingSession: null, flow: null },
  home: { name: 'Mein Zuhause', location: null },
  integrations: { hue: { discovered: false, paired: false, bridge: null, lastSync: null, syncError: null, mode: 'simulation', reconnect: reconnect.snapshot() } },
  rooms: [{ id: 'living', name: 'Wohnzimmer' }, { id: 'office', name: 'Büro' }, { id: 'bedroom', name: 'Schlafzimmer' }],
  devices: [],
  automations: [],
  automationHistory: [],
  schedulerExecuted: {},
  auditLog: [],
  updateSlots: createSlotState('0.4.0'),
  dashboard: defaultDashboard()
};

const persisted = storage.loadState(initialState);
const state = {
  ...initialState, ...persisted,
  system: { ...initialState.system, ...(persisted.system || {}), version: '0.4.0' },
  onboarding: { ...initialState.onboarding, ...(persisted.onboarding || {}), pairingSession: null },
  home: { ...initialState.home, ...(persisted.home || {}), location: persisted.home?.location || null },
  integrations: { ...initialState.integrations, ...(persisted.integrations || {}), hue: { ...initialState.integrations.hue, ...(persisted.integrations?.hue || {}), reconnect: reconnect.snapshot() } },
  rooms: Array.isArray(persisted.rooms) ? persisted.rooms : initialState.rooms,
  devices: Array.isArray(persisted.devices) ? persisted.devices.map(migrateLegacyDevice) : [],
  automations: Array.isArray(persisted.automations) ? persisted.automations : [],
  automationHistory: Array.isArray(persisted.automationHistory) ? persisted.automationHistory.slice(0,100) : [],
  schedulerExecuted: persisted.schedulerExecuted && typeof persisted.schedulerExecuted === 'object' ? persisted.schedulerExecuted : {},
  auditLog: Array.isArray(persisted.auditLog) ? persisted.auditLog.slice(0,500) : [],
  updateSlots: persisted.updateSlots && persisted.updateSlots.schemaVersion===1 ? persisted.updateSlots : createSlotState('0.4.0'),
  dashboard: migrateDashboard(persisted.dashboard)
};
state.onboarding.flow = migrateOnboardingState(state.onboarding);
state.updateSlots=recoverInterruptedBoot(state.updateSlots);
state.onboarding.completed = state.onboarding.flow.currentStep === 'complete';
try { state.onboarding.locale = validateLocale(state.onboarding.locale || DEFAULT_LOCALE); } catch { state.onboarding.locale = DEFAULT_LOCALE; }

const demoDevices = [
  { id: 'hue-1', hueId: '1', integration: 'hue', type: 'light', sourceName: 'Stehlampe', name: 'Stehlampe', roomId: 'living', online: true, on: true, brightness: 72 },
  { id: 'hue-2', hueId: '2', integration: 'hue', type: 'light', sourceName: 'Schreibtisch', name: 'Schreibtisch', roomId: 'office', online: true, on: false, brightness: 35 }
];
const hue = new HueAdapter({ storage, demoDevices, diagnostics });
const simulation = new SimulationAdapter();
const govee=new GoveeAdapter({mode:process.env.GOVEE_MODE||'simulation',fault:process.env.GOVEE_SIM_FAULT||''});
const adapters = new Map([['hue', assertAdapter(hue)], ['simulation', assertAdapter(simulation)],['govee',assertAdapter(govee)]]);
const registry = new DeviceRegistry(state.devices);
state.integrations.hue.mode = hue.mode;
const deviceEventClients = new Set();
let deviceEventSequence = 0;
function sendDeviceEvent(type, payload = {}) {
  const event = normalizedDeviceEvent(type, payload, ++deviceEventSequence);
  const frame = `id: ${event.sequence}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`;
  for (const client of deviceEventClients) client.write(frame);
  return event;
}

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
const automationEngine = new AutomationEngine({ registry, automations: validPersistedAutomations, history: state.automationHistory, executeAction: action => applyDeviceCapabilities(action.deviceId, action.capabilities) });
const localSessions = new LocalSessionStore({ initial: storage.loadSessions(), onChange: sessions => storage.saveSessions(sessions) });
const auditLog = new AuditLog({ initial: state.auditLog, limit: 500 });
const writeLimiter=new RateLimiter({limit:120,windowMs:60000}),pairingLimiter=new RateLimiter({limit:10,windowMs:15*60000}),loginLimiter=new RateLimiter({limit:10,windowMs:15*60000});
const scheduler = new AutomationScheduler({ engine: automationEngine, initialExecuted: state.schedulerExecuted, onExecutedChange: executed => { state.schedulerExecuted=executed;persist(); }, solarProvider: async date => state.home.location ? calculateSolarEvents(date, state.home.location) : null });
state.automations = automationEngine.list();

function syncRegistryState() { state.devices = registry.list(); }
registry.on('device.added', device => { syncRegistryState(); sendDeviceEvent('device.added', device); });
registry.on('device.updated', device => { syncRegistryState(); sendDeviceEvent('device.updated', device); });
registry.on('registry.changed', () => { syncRegistryState(); sendDeviceEvent('devices.resync'); });
automationEngine.on('changed', automations => { state.automations = automations; });
automationEngine.on('history.changed', history => { state.automationHistory = history; persist(); });
automationEngine.on('executed', automation => { if (automation.lastError) diagnostics.record('AUTOMATION_ACTION_FAILED', automation.lastError.message, { automationId: automation.id }); });

function updateReconnectState() { state.integrations.hue.reconnect = reconnect.snapshot(); }
function persist() {
  updateReconnectState();
  syncRegistryState();
  const safeState = JSON.parse(JSON.stringify(state));
  safeState.onboarding.pairingSession = null;
  storage.saveState(safeState);
}
function json(res, status, data, headers = {}) {
  res.writeHead(status, { ...securityHeaders(), 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store','X-SystemONE-API-Version':API_VERSION, ...headers });
  res.end(JSON.stringify(responseEnvelope(status,data)));
}
function sessionToken(req, cookieName = 'systemone_session') { const cookie = String(req.headers.cookie || '').split(';').map(item => item.trim()).find(item => item.startsWith(`${cookieName}=`)); return cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : String(req.headers.authorization || '').replace(/^Bearer\s+/i, ''); }
function bearerToken(req) { return String(req.headers.authorization || '').replace(/^Bearer\s+/i, ''); }
function requireSession(req, permission = 'system:write', cookieName = 'systemone_session') { return localSessions.authenticate(sessionToken(req, cookieName), permission); }
function publicState() { const {auditLog:_,...publicData}=state,onboarding = { ...state.onboarding, pairingSession: publicSession(state.onboarding.pairingSession) }; return { ...publicData, onboarding, devices: registry.list({ publicOnly: true }), automations: automationEngine.list() }; }
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
  const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript', '.svg': 'image/svg+xml','.webmanifest':'application/manifest+json' };
  const size=fs.statSync(filePath).size;
  res.writeHead(200, { ...securityHeaders(), ...staticResponseHeaders(filePath), 'Content-Type': `${types[path.extname(filePath)] || 'application/octet-stream'}; charset=utf-8`, 'Content-Length':size });
  if(req.method==='HEAD'){res.end();return true}
  fs.createReadStream(filePath).pipe(res); return true;
}
function servePublicDoc(req,res){const name=req.url.split('?')[0].replace(/^\/docs\//,'');if(!/^[a-z0-9-]+\.md$/.test(name))return false;const file=path.join(DOCS_DIR,name);if(!file.startsWith(DOCS_DIR)||!fs.existsSync(file))return false;res.writeHead(200,{...securityHeaders(),'Content-Type':'text/markdown; charset=utf-8','Content-Disposition':'inline','Cache-Control':'no-store','Content-Length':fs.statSync(file).size});if(req.method==='HEAD'){res.end();return true}fs.createReadStream(file).pipe(res);return true}
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
  assertSessionCanStart(state.onboarding.pairingSession);
  const token = crypto.randomBytes(24).toString('base64url');
  const code = String(crypto.randomInt(100000, 1000000));
  const pairingUri = `systemone://pair?token=${token}&code=${code}`;
  const qrDataUrl = await QRCode.toDataURL(pairingUri, { errorCorrectionLevel: 'M', margin: 2, width: 240 });
  state.onboarding.pairingSession = createSession({ token, code, pairingUri, qrDataUrl });
  return state.onboarding.pairingSession;
}
function completePairing(body) {
  const session = state.onboarding.pairingSession;
  verifySession(session, body);
  state.onboarding.adminPaired = true; state.onboarding.pairingSession = null; persist(); const local = localSessions.create('owner'); return { adminPaired: true, local };
}
function createSimulatedDevice(body) {
  const profile = DEVICE_PROFILES[body.profile || body.type] ? (body.profile || body.type) : null;
  if (!profile) throw Object.assign(new Error('Unbekanntes Geräteprofil.'), { code: 'DEVICE_PROFILE_INVALID' });
  const roomId = state.rooms.some(room => room.id === body.roomId) ? body.roomId : null;
  const device = simulation.create({ profile, name: body.name, roomId });
  registry.upsert(device); persist(); return publicDevice(device);
}
function exportBackup() { syncRegistryState(); return createBackup(state, state.system.version); }
function runBackupCycle(){try{const written=backupManager.write(exportBackup());lastBackupRestoreTest=backupManager.testRestore(written.file);return{written,restoreTest:lastBackupRestoreTest}}catch(error){lastBackupRestoreTest={success:false,code:error.code||'BACKUP_CYCLE_FAILED',message:error.message,testedAt:new Date().toISOString()};diagnostics.record(lastBackupRestoreTest.code,lastBackupRestoreTest.message);throw error}}
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

const requestHandler = async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    url.pathname=normalizeApiPath(url.pathname);
    const clientKey=String(req.socket.remoteAddress||'local'),mutating=!['GET','HEAD','OPTIONS'].includes(req.method);let auditActor=null;if(mutating)res.once('finish',()=>{auditLog.record({method:req.method,path:url.pathname,status:res.statusCode,outcome:res.statusCode<400?'success':'failure',actor:auditActor,error:res._auditError});state.auditLog=auditLog.list();persist()});validateHost(req);validateWriteRequest(req);
    const pairingBootstrap = req.method === 'POST' && ['/api/onboarding/pair-admin/session','/api/onboarding/pair-admin/complete','/api/display/session'].includes(url.pathname);
    if(mutating){writeLimiter.consume(clientKey);if(url.pathname==='/api/onboarding/pair-admin/session')pairingLimiter.consume(clientKey);if(['/api/onboarding/pair-admin/complete','/api/display/session'].includes(url.pathname))loginLimiter.consume(clientKey)}
    if (state.onboarding.adminPaired && mutating && !pairingBootstrap) auditActor=requireSession(req, 'system:write');
    if (req.method === 'GET' && url.pathname === '/api/events/devices') {
      res.writeHead(200, { ...securityHeaders(), 'Content-Type': 'text/event-stream; charset=utf-8', 'Cache-Control': 'no-cache, no-transform', Connection: 'keep-alive' });
      res.write(`retry: 5000\nevent: devices.resync\ndata: ${JSON.stringify(normalizedDeviceEvent('devices.resync', {}, ++deviceEventSequence))}\n\n`);
      deviceEventClients.add(res);
      const heartbeat = setInterval(() => res.write(': keepalive\n\n'), 20000);
      req.on('close', () => { clearInterval(heartbeat); deviceEventClients.delete(res); });
      return;
    }
    if (req.method === 'GET' && url.pathname === '/api/health') return json(res, 200, diagnostics.health(state, hue));
    if (req.method === 'GET' && url.pathname === '/api/contract') return json(res,200,publicContract());
    if (req.method === 'GET' && url.pathname === '/api/diagnostics') return json(res, 200, { ...diagnostics.report(state, hue), reconnect: reconnect.snapshot() });
    if (req.method === 'GET' && url.pathname === '/api/diagnostics/export/preview') {if(state.onboarding.adminPaired)requireSession(req,'system:read');const pkg=createDiagnosticPackage(diagnostics.report(state,hue),{includeEvents:url.searchParams.get('events')!=='0'});return json(res,200,previewDiagnosticPackage(pkg));}
    if (req.method === 'GET' && url.pathname === '/api/diagnostics/export') {if(state.onboarding.adminPaired)requireSession(req,'system:read');return json(res,200,createDiagnosticPackage(diagnostics.report(state,hue),{includeEvents:url.searchParams.get('events')!=='0'}));}
    if (req.method === 'GET' && url.pathname === '/api/cameras') return json(res,200,cameras.status());
    if (req.method === 'GET' && url.pathname === '/api/pihole') return json(res,200,pihole.publicStatus());
    if (req.method === 'GET' && url.pathname === '/api/modules') return json(res,200,{modules:modules.list(),coreIndependent:true,cloudRequired:false,aiRequired:false});
    if (req.method === 'GET' && url.pathname === '/api/integrations/govee') return json(res,200,{mode:govee.mode,hardwareReleased:false,models:LOCAL_MODEL_ALLOWLIST,cloudOnlyExcluded:CLOUD_ONLY_EXCLUDED,devices:registry.list().filter(device=>device.integration==='govee').map(publicDevice)});
    if (req.method === 'GET' && url.pathname === '/api/integration-pilots') return json(res,200,publicPilotPlan());
    if (req.method === 'POST' && url.pathname === '/api/integrations/govee/simulate') {const body=await readBody(req),device=govee.create({model:body.model,name:body.name,roomId:body.roomId});registry.upsert(device);persist();return json(res,201,publicDevice(device));}
    if (req.method === 'POST' && url.pathname === '/api/pihole/refresh') return json(res,200,await pihole.refresh());
    if (req.method === 'POST' && url.pathname === '/api/pihole/blocking') {const body=await readBody(req);return json(res,200,await pihole.setBlocking(body.enabled));}
    if (req.method === 'POST' && url.pathname === '/api/cameras') return json(res,201,cameras.add(await readBody(req)));
    const cameraTestMatch=url.pathname.match(/^\/api\/cameras\/([^/]+)\/test$/);if(cameraTestMatch&&req.method==='POST')return json(res,200,await cameras.test(cameraTestMatch[1]));
    const cameraFrameMatch=url.pathname.match(/^\/api\/cameras\/([^/]+)\/frame\.svg$/);if(cameraFrameMatch&&req.method==='GET'){const svg=cameras.frame(cameraFrameMatch[1]);res.writeHead(200,{...securityHeaders(),'Content-Type':'image/svg+xml; charset=utf-8','Cache-Control':'no-store'});return res.end(svg)}
    if (req.method === 'GET' && url.pathname === '/api/admin/audit') { requireSession(req, 'users:manage'); return json(res, 200, auditLog.list()); }
    if (req.method === 'GET' && url.pathname === '/api/setup') return json(res, 200, setupStatus());
    if (req.method === 'GET' && url.pathname === '/api/onboarding') return json(res, 200, state.onboarding.flow);
    if (req.method === 'POST' && url.pathname === '/api/onboarding/advance') { const body = await readBody(req); state.onboarding.flow = advanceOnboarding(state.onboarding.flow, body.targetStep); state.onboarding.completed = state.onboarding.flow.currentStep === 'complete'; persist(); return json(res, 200, state.onboarding.flow); }
    if (req.method === 'POST' && url.pathname === '/api/onboarding/reset') { state.onboarding.flow = resetOnboarding(); state.onboarding.completed = false; persist(); return json(res, 200, state.onboarding.flow); }
    if (req.method === 'GET' && url.pathname === '/api/i18n') return json(res, 200, { ...localeCatalog(), selectedLocale: state.onboarding.locale });
    if (req.method === 'GET' && url.pathname === '/api/i18n/messages') return json(res, 200, messagesFor(url.searchParams.get('locale') || state.onboarding.locale));
    if (req.method === 'PATCH' && url.pathname === '/api/settings/locale') { const body = await readBody(req); state.onboarding.locale = validateLocale(body.locale); persist(); return json(res, 200, { locale: state.onboarding.locale }); }
    if (req.method === 'GET' && url.pathname === '/api/profiles') return json(res, 200, DEVICE_PROFILES);
    if (req.method === 'GET' && url.pathname === '/api/automations/builder-options') return json(res, 200, { devices: builderOptions(registry), operators: { equals: 'ist gleich', notEquals: 'ist nicht gleich', above: 'größer als', below: 'kleiner als' } });
    if (req.method === 'GET' && url.pathname === '/api/compatibility') return json(res, 200, publicCompatibilityCatalog());
    if (req.method === 'GET' && url.pathname === '/api/device-onboarding/integrations') return json(res, 200, availableIntegrations(hue.mode));
    if (req.method === 'GET' && url.pathname === '/api/device-onboarding/discover') return json(res, 200, { integration: url.searchParams.get('integration') || 'simulation', scannedAt: new Date().toISOString(), candidates: discoverCandidates(url.searchParams.get('integration') || 'simulation', registry.list()) });
    if (req.method === 'POST' && url.pathname === '/api/device-onboarding/complete') { const startedAt = Date.now(), input = validateOnboardingRequest(await readBody(req), state.rooms, registry.list()); const device = simulation.create({ ...input, id: input.candidateId || undefined, serialNumber: input.candidateId ? `DISC-${input.candidateId.toUpperCase()}` : undefined }); registry.upsert(device); persist(); return json(res, 201, { device: publicDevice(device), test: { success: true, latencyMs: Date.now() - startedAt, checks: [{ id: 'identity', ok: Boolean(device.id) }, { id: 'availability', ok: device.online }, { id: 'capabilities', ok: Object.keys(device.capabilities).length > 0 }], message: 'Identität, Erreichbarkeit und Funktionen wurden lokal geprüft.' } }); }
    if (req.method === 'GET' && url.pathname === '/api/system') return json(res, 200, state.system);
    if (req.method === 'GET' && url.pathname === '/api/system/identity') return json(res, 200, tlsEnabled ? certificateStatus(path.dirname(tlsKeyPath)) : { provisioned:false,revoked:false,keyLocalOnly:true,transport:'http-development' });
    if (req.method === 'POST' && url.pathname === '/api/updates/validate') return json(res, 200, validateUpdatePackage(await readBody(req),{publicKey:updatePublicKey,currentVersion:state.system.version}));
    if (req.method === 'GET' && url.pathname === '/api/updates/slots') return json(res,200,state.updateSlots);
    if (req.method === 'POST' && url.pathname === '/api/updates/approve') { const validation=validateUpdatePackage(await readBody(req),{publicKey:updatePublicKey,currentVersion:state.system.version}),approval=approveUpdate(validation,auditActor),staged=stageUpdate(state.updateSlots,validation,approval);state.updateSlots=staged.state;persist();return json(res,200,{validation,approval,targetSlot:staged.targetSlot}); }
    if (req.method === 'POST' && url.pathname === '/api/updates/activate') { const body=await readBody(req);state.updateSlots=activateStaged(state.updateSlots,body.targetSlot);persist();return json(res,200,state.updateSlots); }
    if (req.method === 'POST' && url.pathname === '/api/updates/health') { state.updateSlots=reportBootHealth(state.updateSlots,await readBody(req));persist();return json(res,200,state.updateSlots); }
    if (req.method === 'GET' && url.pathname === '/api/themes') return json(res, 200, THEMES);
    if (req.method === 'GET' && url.pathname === '/api/dashboard') return json(res, 200, state.dashboard);
    if (req.method === 'PATCH' && url.pathname === '/api/dashboard') { state.dashboard = validateDashboard(await readBody(req)); persist(); return json(res, 200, state.dashboard); }
    if (req.method === 'POST' && url.pathname === '/api/dashboard/reset') { state.dashboard = defaultDashboard(); persist(); return json(res, 200, state.dashboard); }
    if (req.method === 'PATCH' && url.pathname === '/api/settings/theme') { const body = await readBody(req); state.onboarding.selectedTheme = validateTheme(body.theme); persist(); return json(res, 200, { selectedTheme: state.onboarding.selectedTheme }); }
    if (req.method === 'GET' && url.pathname === '/api/home') return json(res, 200, state.home);
    if (req.method === 'PATCH' && url.pathname === '/api/home') { const body = await readBody(req); if (typeof body.name === 'string' && body.name.trim()) state.home.name = body.name.trim().slice(0, 80); if (body.location !== undefined) state.home.location = body.location === null ? null : validateLocation(body.location); persist(); return json(res, 200, state.home); }
    if (req.method === 'GET' && url.pathname === '/api/state') { if (url.searchParams.get('sync') === '1' && reconnect.state !== 'backoff') await syncHue(); updateReconnectState(); return json(res, 200, publicState()); }
    if (req.method === 'GET' && url.pathname === '/api/backup') return json(res, 200, exportBackup());
    if (req.method === 'GET' && url.pathname === '/api/backups/status') return json(res,200,backupManager.publicStatus(lastBackupRestoreTest));
    if (req.method === 'POST' && url.pathname === '/api/backups/run') return json(res,201,runBackupCycle());
    if (req.method === 'POST' && url.pathname === '/api/backups/export') {const body=await readBody(req),target=backupManager.allowedRoots[Number(body.targetId)];if(!target)throw Object.assign(new Error('Freigegebenes USB-/NAS-Ziel wurde nicht gefunden.'),{code:'BACKUP_TARGET_FORBIDDEN'});const written=backupManager.write(exportBackup(),{targetDir:target,passphrase:body.passphrase||null});return json(res,201,{written,restoreTest:backupManager.testRestore(written.file,{targetDir:target,passphrase:body.passphrase||null})});}
    if (req.method === 'POST' && url.pathname === '/api/backups/restore-test') {const body=await readBody(req);lastBackupRestoreTest=backupManager.testRestore(body.file,{passphrase:body.passphrase||null});return json(res,200,lastBackupRestoreTest);}
    if (req.method === 'POST' && url.pathname === '/api/backup/validate') return json(res, 200, summarizeBackup(await readBody(req)));
    if (req.method === 'GET' && url.pathname === '/api/automations/templates') return json(res, 200, TEMPLATES);
    if (req.method === 'GET' && url.pathname === '/api/automations/scheduler') return json(res, 200, scheduler.status());
    if (req.method === 'GET' && url.pathname === '/api/automations') return json(res, 200, automationEngine.list());
    if (req.method === 'GET' && url.pathname === '/api/automations/history') return json(res, 200, automationEngine.listHistory());
    const retryMatch = url.pathname.match(/^\/api\/automations\/history\/([^/]+)\/retry$/);
    if (retryMatch && req.method === 'POST') return json(res, 200, await automationEngine.retry(retryMatch[1]));
    if (req.method === 'POST' && url.pathname === '/api/automations') { const item = automationEngine.add(await readBody(req)); persist(); return json(res, 201, item); }
    if (req.method === 'POST' && url.pathname === '/api/automations/from-template') { const body = await readBody(req); const item = automationEngine.addFromTemplate(body.templateId, body); persist(); return json(res, 201, item); }
    const automationMatch = url.pathname.match(/^\/api\/automations\/([^/]+)$/);
    if (automationMatch && req.method === 'PATCH') { const body = await readBody(req); const item = automationEngine.setEnabled(automationMatch[1], body.enabled); if (!item) return json(res, 404, { code: 'AUTOMATION_NOT_FOUND', message: 'Automation nicht gefunden.' }); persist(); return json(res, 200, item); }
    if (automationMatch && req.method === 'DELETE') { if (!automationEngine.remove(automationMatch[1])) return json(res, 404, { code: 'AUTOMATION_NOT_FOUND', message: 'Automation nicht gefunden.' }); persist(); return json(res, 200, { deleted: true }); }
    if (req.method === 'POST' && url.pathname === '/api/onboarding/pair-admin/session') return json(res, 201, await createPairingSession());
    if (req.method === 'POST' && url.pathname === '/api/onboarding/pair-admin/complete') { const result = completePairing(await readBody(req)); return json(res, 200, { adminPaired: true, session: result.local.session }, { 'Set-Cookie': `systemone_session=${encodeURIComponent(result.local.token)}; HttpOnly; SameSite=Strict${tlsEnabled?'; Secure':''}; Path=/; Max-Age=43200` }); }
    if (req.method === 'DELETE' && url.pathname === '/api/onboarding/pair-admin/session') { const revoked = Boolean(state.onboarding.pairingSession); state.onboarding.pairingSession = null; return json(res, 200, { revoked }); }
    if (req.method === 'GET' && url.pathname === '/api/session') return json(res, 200, requireSession(req, 'system:read'));
    if (req.method === 'GET' && url.pathname === '/api/admin/sessions') { requireSession(req, 'users:manage'); return json(res, 200, localSessions.list()); }
    if (req.method === 'POST' && url.pathname === '/api/admin/display-sessions') { requireSession(req, 'users:manage'); const created = localSessions.create('display'); return json(res, 201, { session: created.session, launchUrl: `/display.html#token=${encodeURIComponent(created.token)}` }); }
    const adminSessionMatch = url.pathname.match(/^\/api\/admin\/sessions\/([^/]+)$/);
    if (adminSessionMatch && req.method === 'DELETE') { requireSession(req, 'users:manage'); return json(res, 200, { revoked: localSessions.revoke(adminSessionMatch[1]) }); }
    if (req.method === 'DELETE' && url.pathname === '/api/admin/session') { const current = requireSession(req, 'system:read'); return json(res, 200, { revoked: localSessions.revoke(current.id) }, { 'Set-Cookie': 'systemone_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0' }); }
    if (req.method === 'POST' && url.pathname === '/api/display/session') { const token = bearerToken(req), session = localSessions.authenticate(token, 'dashboard:read'); return json(res, 200, session, { 'Set-Cookie': `systemone_display=${encodeURIComponent(token)}; HttpOnly; SameSite=Strict${tlsEnabled?'; Secure':''}; Path=/; Max-Age=43200` }); }
    if (req.method === 'GET' && url.pathname === '/api/display') { requireSession(req, 'dashboard:read', 'systemone_display'); return json(res, 200, displayState(state, registry.list({ publicOnly: true }))); }
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
    const actionMatch = url.pathname.match(/^\/api\/devices\/([^/]+)\/actions\/([^/]+)$/);
    if (actionMatch && req.method === 'POST') { const device = registry.get(actionMatch[1]); if (!device) return json(res, 404, { code: 'DEVICE_NOT_FOUND', message: 'Gerät nicht gefunden.' }); const adapter = adapters.get(device.integration); if (!adapter?.applyAction) return json(res, 409, { code: 'DEVICE_ACTION_UNSUPPORTED', message: 'Aktion wird von diesem Gerät nicht unterstützt.' }); const capabilities = await adapter.applyAction(device, actionMatch[2]); if (Object.keys(capabilities).length) registry.patch(device.id, { capabilities }); persist(); return json(res, 200, publicDevice(registry.get(device.id))); }
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
    if (['GET','HEAD'].includes(req.method) && url.pathname.startsWith('/docs/') && servePublicDoc(req,res))return;
    if (['GET','HEAD'].includes(req.method) && !url.pathname.startsWith('/api/') && serveStatic(req, res)) return;
    if (['GET','HEAD'].includes(req.method) && shouldServeAppShell(url.pathname,req.headers.accept)) { req.url = '/index.html'; if (serveStatic(req, res)) return; }
    return json(res, 404, { code: 'NOT_FOUND', message: 'Route nicht gefunden.' });
  } catch (error) {
    res._auditError={code:error.code||'INTERNAL_ERROR',message:error.message};
    diagnostics.record(error.code || 'INTERNAL_ERROR', error.message || 'Unbekannter Fehler.', error.details || {});
    const conflictCodes = ['HUE_LINK_BUTTON_REQUIRED','PAIRING_SESSION_ACTIVE','PAIRING_SESSION_EXPIRED','PAIRING_INVALID','PAIRING_RATE_LIMITED','HUE_DEVICE_OFFLINE','DEVICE_OFFLINE'];
    const authCodes = ['SESSION_INVALID','SESSION_REVOKED','SESSION_EXPIRED'], forbiddenCodes = ['SESSION_FORBIDDEN','HOST_FORBIDDEN','CSRF_ORIGIN_INVALID','CSRF_TOKEN_MISSING'],rateCodes=['RATE_LIMITED'];
    return json(res, authCodes.includes(error.code) ? 401 : forbiddenCodes.includes(error.code) ? 403 : rateCodes.includes(error.code)?429:conflictCodes.includes(error.code) ? 409 : 400, { code: error.code || 'INTERNAL_ERROR', message: error.message || 'Ungültige Anfrage.' });
  }
};

const tlsKeyPath=process.env.TLS_KEY_PATH,tlsCertPath=process.env.TLS_CERT_PATH,tlsEnabled=Boolean(tlsKeyPath&&tlsCertPath);let server;
if(tlsEnabled){const identity=certificateStatus(path.dirname(tlsKeyPath));if(identity.provisioned&&identity.revoked)throw Object.assign(new Error('Widerrufene TLS-Geräteidentität darf nicht starten.'),{code:'TLS_IDENTITY_REVOKED'});server=https.createServer({key:fs.readFileSync(tlsKeyPath),cert:fs.readFileSync(tlsCertPath),minVersion:'TLSv1.2'},requestHandler)}else server=http.createServer(requestHandler);

server.listen(PORT, '0.0.0.0', async () => {
  console.log(`SystemONE Pi MVP v0.4.0 läuft auf ${tlsEnabled?'https':'http'}://localhost:${PORT} · Hue-Modus: ${hue.mode}`);
  if (hue.mode !== 'real') diagnostics.record('HUE_REAL_MODE_DISABLED', 'Sicherer Simulationsmodus aktiv: keine private Hue Bridge wird angesprochen.');
  scheduler.start();
  if(!backupManager.list().length)runBackupCycle();
  await discoverHue(); if (state.integrations.hue.paired) await syncHue();
});
setInterval(async () => {
  if (!state.integrations.hue.paired) return;
  if (reconnect.canRetry()) { reconnect.beginAttempt(); updateReconnectState(); await syncHue(); return; }
  if (reconnect.state !== 'backoff') await syncHue();
}, 3000).unref();
setInterval(()=>{try{runBackupCycle()}catch{}},Math.max(3600000,Number(process.env.BACKUP_INTERVAL_MS)||86400000)).unref();
