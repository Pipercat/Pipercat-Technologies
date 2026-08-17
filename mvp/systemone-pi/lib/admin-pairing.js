const TTL_MS = 5 * 60 * 1000;
const MAX_FAILED_ATTEMPTS = 5;

function pairingError(code, message) { return Object.assign(new Error(message), { code }); }

function createSession({ token, code, qrDataUrl, pairingUri, now = Date.now() }) {
  if (!token || !/^\d{6}$/.test(String(code))) throw pairingError('PAIRING_SESSION_INVALID', 'Pairing-Sitzung konnte nicht sicher erstellt werden.');
  return { token, code: String(code), qrDataUrl, pairingUri, createdAt: new Date(now).toISOString(), expiresAt: new Date(now + TTL_MS).toISOString(), failedAttempts: 0 };
}

function assertSessionCanStart(session, now = Date.now()) {
  if (session && Date.parse(session.expiresAt) >= now) throw pairingError('PAIRING_SESSION_ACTIVE', 'Es läuft bereits eine Pairing-Sitzung.');
}

function verifySession(session, input, now = Date.now()) {
  if (!session) throw pairingError('PAIRING_SESSION_MISSING', 'Keine aktive Pairing-Sitzung.');
  if (Date.parse(session.expiresAt) < now) throw pairingError('PAIRING_SESSION_EXPIRED', 'Pairing-Sitzung ist abgelaufen.');
  if ((session.failedAttempts || 0) >= MAX_FAILED_ATTEMPTS) throw pairingError('PAIRING_RATE_LIMITED', 'Zu viele fehlgeschlagene Pairing-Versuche. Bitte Sitzung widerrufen und neu starten.');
  if (input?.token !== session.token || String(input?.code) !== session.code) {
    session.failedAttempts = (session.failedAttempts || 0) + 1;
    throw pairingError(session.failedAttempts >= MAX_FAILED_ATTEMPTS ? 'PAIRING_RATE_LIMITED' : 'PAIRING_INVALID', 'Pairing-Code oder Token ist ungültig.');
  }
  return true;
}

function publicSession(session) {
  if (!session) return null;
  return { active: true, createdAt: session.createdAt, expiresAt: session.expiresAt, failedAttempts: session.failedAttempts || 0, attemptsRemaining: Math.max(0, MAX_FAILED_ATTEMPTS - (session.failedAttempts || 0)) };
}

module.exports = { TTL_MS, MAX_FAILED_ATTEMPTS, createSession, assertSessionCanStart, verifySession, publicSession };
