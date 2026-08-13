const crypto = require('crypto');

const MAX_ATTEMPTS = 5;
function recoveryError(code, message) { return Object.assign(new Error(message), { code }); }
function normalize(code) { return String(code || '').toUpperCase().replace(/[^A-Z0-9]/g, ''); }
function derive(code, salt) { return crypto.scryptSync(normalize(code), salt, 32).toString('hex'); }

function createRecoveryCode(now = Date.now()) {
  const raw = crypto.randomBytes(10).toString('hex').toUpperCase(), code = raw.match(/.{1,5}/g).join('-'), salt = crypto.randomBytes(16).toString('hex');
  return { code, record: { salt, hash: derive(code, salt), createdAt: new Date(now).toISOString(), failedAttempts: 0, usedAt: null } };
}

function verifyRecovery(record, { code, physicalPresence }, now = Date.now()) {
  if (!physicalPresence) throw recoveryError('RECOVERY_PHYSICAL_PRESENCE_REQUIRED', 'Recovery benötigt die bestätigte physische Aktion am SystemONE Pi.');
  if (!record || record.usedAt) throw recoveryError('RECOVERY_CODE_UNAVAILABLE', 'Recovery-Code ist nicht verfügbar oder wurde bereits verwendet.');
  if ((record.failedAttempts || 0) >= MAX_ATTEMPTS) throw recoveryError('RECOVERY_RATE_LIMITED', 'Zu viele Recovery-Versuche. Physischer Werksreset erforderlich.');
  const candidate = derive(code, record.salt), valid = crypto.timingSafeEqual(Buffer.from(candidate, 'hex'), Buffer.from(record.hash, 'hex'));
  if (!valid) { record.failedAttempts = (record.failedAttempts || 0) + 1; throw recoveryError(record.failedAttempts >= MAX_ATTEMPTS ? 'RECOVERY_RATE_LIMITED' : 'RECOVERY_CODE_INVALID', 'Recovery-Code ist ungültig.'); }
  record.usedAt = new Date(now).toISOString(); return true;
}

module.exports = { MAX_ATTEMPTS, createRecoveryCode, verifyRecovery };
