const crypto = require('crypto');
const { migrateLegacyDevice } = require('./device-model');

const FORMAT = 'systemone-backup';
const SCHEMA_VERSION = 2;

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, stable(value[key])]));
  return value;
}

function checksum(data) { return crypto.createHash('sha256').update(JSON.stringify(stable(data))).digest('hex'); }
function backupError(message, details = {}) { return Object.assign(new Error(message), { code: 'BACKUP_INVALID', details }); }

function validateData(data) {
  if (!data || typeof data !== 'object' || !Array.isArray(data.rooms) || !Array.isArray(data.devices)) throw backupError('Backup-Daten sind unvollständig.');
  if (data.rooms.length > 100 || data.devices.length > 500) throw backupError('Backup überschreitet die zulässige Größe.');
  const rooms = data.rooms.map(room => {
    if (!room?.id || !room?.name) throw backupError('Ein Raum im Backup ist ungültig.');
    return { id: String(room.id).slice(0, 80), name: String(room.name).slice(0, 60) };
  });
  const roomIds = new Set(rooms.map(room => room.id));
  if (roomIds.size !== rooms.length) throw backupError('Backup enthält doppelte Raum-IDs.');
  const devices = data.devices.map(migrateLegacyDevice).filter(device => device.integration === 'simulation');
  return { rooms, devices, onboarding: { selectedTheme: String(data.onboarding?.selectedTheme || 'Clear').slice(0, 30) } };
}

function createBackup(state, systemVersion = '0.4.0') {
  const data = validateData({ rooms: state.rooms, devices: state.devices.filter(device => device.integration === 'simulation'), onboarding: { selectedTheme: state.onboarding?.selectedTheme || 'Clear' } });
  return { format: FORMAT, schemaVersion: SCHEMA_VERSION, systemVersion, createdAt: new Date().toISOString(), checksum: checksum(data), data };
}

function migrateV1(input) {
  if (input?.format !== FORMAT || input?.version !== 1 || !input.state) throw backupError('Backup-Version wird nicht unterstützt.');
  const data = validateData(input.state);
  return { format: FORMAT, schemaVersion: SCHEMA_VERSION, systemVersion: '0.3.1', createdAt: input.createdAt || new Date().toISOString(), checksum: checksum(data), data };
}

function validateBackup(input) {
  const backup = input?.version === 1 ? migrateV1(input) : input;
  if (backup?.format !== FORMAT || backup?.schemaVersion !== SCHEMA_VERSION) throw backupError('Backup-Format oder Schema-Version ist ungültig.');
  if (!/^\d{4}-\d{2}-\d{2}T/.test(backup.createdAt || '')) throw backupError('Backup-Zeitstempel ist ungültig.');
  const data = validateData(backup.data);
  const actual = checksum(data);
  if (typeof backup.checksum !== 'string' || backup.checksum.length !== 64 || !crypto.timingSafeEqual(Buffer.from(actual), Buffer.from(backup.checksum))) throw backupError('Backup-Prüfsumme stimmt nicht überein.', { expected: actual });
  return { ...backup, data, migrated: input?.version === 1 };
}

function summarizeBackup(input) {
  const backup = validateBackup(input);
  return { valid: true, format: backup.format, schemaVersion: backup.schemaVersion, systemVersion: backup.systemVersion, createdAt: backup.createdAt, checksum: backup.checksum, migrated: backup.migrated, rooms: backup.data.rooms.length, devices: backup.data.devices.length, theme: backup.data.onboarding.selectedTheme };
}

module.exports = { FORMAT, SCHEMA_VERSION, checksum, createBackup, migrateV1, validateBackup, summarizeBackup };
