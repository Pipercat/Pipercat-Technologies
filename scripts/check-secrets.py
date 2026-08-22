#!/usr/bin/env python3
"""Repository secret scan (S1V2-02-013, DEC-118: "keine Produktionssecrets
in Images/Repository").

Scans every tracked-looking text file for credential-shaped strings
(cloud provider keys, PEM private key blocks, JWTs, a committed `.env`
file) and fails if any are found. Deliberately narrow to *real*
credential shapes rather than generic words like "password"/"secret" -
this codebase's own test suite legitimately contains short fixture
values such as hash_password("admin-password") throughout
apps/customer-backend/tests/*.py (see e.g. test_household_pin.py,
test_admin_area.py), and a scanner that flagged those would be useless
noise on every run rather than a real gate. A line can opt out with a
trailing `# secretscan: allow` comment for a justified, reviewed
exception.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EXCLUDED_DIR_PARTS = {"__pycache__", "build", "dist", ".git", "node_modules"}
EXCLUDED_DIR_PREFIXES = (".venv",)

# High-confidence, real credential shapes only - see module docstring for
# why generic "password="/"secret=" matching is deliberately not done
# here (that job already belongs to app/observability.py::redact for log
# lines, which is applied at emission time, not to source text at rest).
CREDENTIAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS Access Key ID", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("Stripe live key", re.compile(r"sk_live_[0-9a-zA-Z]{20,}")),
    ("PEM private key block", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----")),
    ("JWT-shaped token", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
]

ALLOW_COMMENT = "secretscan: allow"


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_PARTS or part.startswith(EXCLUDED_DIR_PREFIXES) for part in path.parts)


def _iter_candidate_files() -> list[Path]:
    files: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if path.is_dir() or _is_excluded(path):
            continue
        files.append(path)
    return files


def find_committed_env_files(files: list[Path]) -> list[str]:
    violations = []
    for path in files:
        name = path.name
        if name == ".env" or (name.endswith(".env") and name not in {".env.example", ".env.sample"}):
            violations.append(f"{path.relative_to(REPO_ROOT)}: committed .env-style file (see .gitignore rule)")
    return violations


def find_credential_matches(files: list[Path]) -> list[str]:
    violations = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable - not a text secret leak
        for lineno, line in enumerate(text.splitlines(), start=1):
            if ALLOW_COMMENT in line:
                continue
            for label, pattern in CREDENTIAL_PATTERNS:
                if pattern.search(line):
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: possible {label} found")
    return violations


def main() -> int:
    files = _iter_candidate_files()
    violations = find_committed_env_files(files) + find_credential_matches(files)
    if violations:
        print("Mögliche Secrets im Repository gefunden:")
        for violation in violations:
            print(f"  {violation}")
        return 1
    print("Kein Secret-Fund im Repository (Scan abgeschlossen).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
