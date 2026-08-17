"""Session store (S1V2-02-008): "sichere Sessions/Tokens, Rotation/Widerruf".

In-memory by design (not a new PostgreSQL table): sessions are ephemeral,
process-local state on a single-node local-first deployment - no
Redis/external store introduced without a demonstrated need (AGENTS.md
stack rule). A restart invalidating all sessions is an acceptable,
documented trade-off (see docs/architecture/auth.md).

Tokens are never stored raw, mirroring the pattern already proven in the
existing Node.js pilot (mvp/systemone-pi/lib/local-sessions.js): only a
SHA-256 hash of the token sits in memory, so a memory dump does not hand
over usable session tokens.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class StoredSession(BaseModel):
    user_id: str
    permissions: frozenset[str]
    device_label: str
    csrf_token: str
    created_at: datetime
    expires_at: datetime
    revoked: bool = False

    def is_expired(self, *, now: datetime | None = None) -> bool:
        return (now or datetime.now(UTC)) >= self.expires_at


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, StoredSession] = {}  # keyed by token hash

    def create(
        self, *, user_id: str, permissions: frozenset[str], device_label: str, ttl: timedelta
    ) -> tuple[str, StoredSession]:
        raw_token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        session = StoredSession(
            user_id=user_id,
            permissions=permissions,
            device_label=device_label,
            csrf_token=secrets.token_urlsafe(24),
            created_at=now,
            expires_at=now + ttl,
        )
        self._sessions[_hash_token(raw_token)] = session
        return raw_token, session

    def lookup(self, raw_token: str) -> StoredSession | None:
        return self._sessions.get(_hash_token(raw_token))

    def revoke(self, raw_token: str) -> bool:
        session = self.lookup(raw_token)
        if session is None:
            return False
        session.revoked = True
        return True

    def rotate(self, raw_token: str, *, ttl: timedelta) -> tuple[str, StoredSession] | None:
        """Issues a fresh token for the same user/permissions and revokes
        the old one - used after a privilege change or as routine
        rotation, never leaving two live tokens for the same login."""
        session = self.lookup(raw_token)
        if session is None or session.revoked or session.is_expired():
            return None
        session.revoked = True
        return self.create(
            user_id=session.user_id, permissions=session.permissions, device_label=session.device_label, ttl=ttl
        )
