"""CSRF protection for cookie-based sessions (S1V2-02-008).

Only relevant when a session is carried via a browser cookie - a bearer
token in an Authorization header (the Flutter app's normal path) is not
subject to CSRF, since browsers don't attach custom headers cross-site.
Double-submit pattern: the session carries a csrf_token
(app/auth/sessions.py); a state-changing cookie-authenticated request must
echo it back in a header, proving the caller can read the session's own
data (impossible for a cross-site attacker who only has the ambient
cookie).
"""

import secrets


class CsrfValidationError(PermissionError):
    def __init__(self) -> None:
        super().__init__("CSRF token missing or invalid for a cookie-authenticated request.")


def validate_csrf(*, session_csrf_token: str, provided_token: str | None) -> None:
    if not provided_token or not secrets.compare_digest(provided_token, session_csrf_token):
        raise CsrfValidationError()
