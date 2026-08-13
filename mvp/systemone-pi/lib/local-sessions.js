const crypto = require('crypto');

const SESSION_TTL_MS = 12 * 60 * 60 * 1000;
const ROLE_PERMISSIONS = Object.freeze({
  owner: ['system:read', 'system:write', 'users:manage'],
  administrator: ['system:read', 'system:write'],
  member: ['system:read', 'devices:control'],
  guest: ['system:read'],
  display: ['dashboard:read']
});

function sessionError(code, message) { return Object.assign(new Error(message), { code }); }
function hashToken(token) { return crypto.createHash('sha256').update(String(token)).digest('hex'); }
function can(role, permission) { return Boolean(ROLE_PERMISSIONS[role]?.includes(permission)); }

class LocalSessionStore {
  constructor({ now = () => Date.now(), initial = [], onChange = () => {} } = {}) { this.now = now; this.onChange = onChange; this.sessions = new Map(initial.filter(item => item?.id && item?.tokenHash && ROLE_PERMISSIONS[item.role]).map(item => [item.id, { ...item }])); }
  create(role = 'owner') {
    if (!ROLE_PERMISSIONS[role]) throw sessionError('ROLE_INVALID', 'Unbekannte lokale Rolle.');
    const token = crypto.randomBytes(32).toString('base64url'), id = crypto.randomUUID(), createdAt = this.now(), expiresAt = createdAt + SESSION_TTL_MS;
    this.sessions.set(id, { id, tokenHash: hashToken(token), role, createdAt, expiresAt, revokedAt: null }); this.onChange(this.export());
    return { token, session: this.public(this.sessions.get(id)) };
  }
  authenticate(token, permission = 'system:read') {
    const tokenHash = hashToken(token || ''), session = [...this.sessions.values()].find(item => item.tokenHash === tokenHash);
    if (!session) throw sessionError('SESSION_INVALID', 'Lokale Session ist ungültig.');
    if (session.revokedAt) throw sessionError('SESSION_REVOKED', 'Lokale Session wurde widerrufen.');
    if (session.expiresAt < this.now()) throw sessionError('SESSION_EXPIRED', 'Lokale Session ist abgelaufen.');
    if (!can(session.role, permission)) throw sessionError('SESSION_FORBIDDEN', 'Diese Rolle darf die Aktion nicht ausführen.');
    return this.public(session);
  }
  revoke(id) { const session = this.sessions.get(id); if (!session) return false; session.revokedAt = this.now(); this.onChange(this.export()); return true; }
  public(session) { return { id: session.id, role: session.role, createdAt: new Date(session.createdAt).toISOString(), expiresAt: new Date(session.expiresAt).toISOString(), revokedAt: session.revokedAt ? new Date(session.revokedAt).toISOString() : null }; }
  list() { return [...this.sessions.values()].map(session => this.public(session)); }
  export() { return [...this.sessions.values()].map(session => ({ ...session })); }
}

module.exports = { SESSION_TTL_MS, ROLE_PERMISSIONS, LocalSessionStore, can, hashToken };
