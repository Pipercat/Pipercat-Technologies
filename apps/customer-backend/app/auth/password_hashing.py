"""Password/PIN hashing (S1V2-02-008): "Moderner adaptiver Passwort-Hash".

Argon2id via argon2-cffi - the current OWASP-recommended default for new
applications (memory-hard, tunable, side-channel resistant variant).
Never store or compare plaintext passwords/PINs anywhere (also enforced
structurally: app/db/models.py::User only has *_hash columns, S1V2-02-001).
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True if the hash was created with older/weaker parameters than the
    current default - lets a login flow transparently upgrade it."""
    return _hasher.check_needs_rehash(password_hash)
