#!/usr/bin/env python3
"""Enforce the module import boundaries from S1V2-01-002 / ADR-0002.

Scans Python source under apps/ and services/ for import statements that
cross a forbidden boundary (e.g. apps/customer-backend importing from
apps/hq-backend). Exits non-zero and prints every violation found.

Rules (see docs/architecture/repo-structure.md):
  - apps/customer-backend must not import apps.hq_backend or the
    provisioning service (no HQ secrets/admin logic in customer packages).
  - apps/hq-backend must not import apps.customer_backend internals.
  - services/home-assistant-adapter must not import from any app (it is a
    leaf dependency, consumed by apps, never the other way around).
  - packages/shared-contracts is Python-schema-free today (OpenAPI only),
    kept out of scope until it gains Python code.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (source directory, forbidden import prefixes)
RULES: list[tuple[Path, list[str]]] = [
    (REPO_ROOT / "apps" / "customer-backend", ["hq_backend", "app_hq", "provisioning"]),
    (REPO_ROOT / "apps" / "hq-backend", ["customer_backend"]),
    (
        REPO_ROOT / "services" / "home-assistant-adapter",
        ["apps", "customer_backend", "hq_backend"],
    ),
]

IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([\w\.]+)")


def find_violations() -> list[str]:
    violations: list[str] = []
    for source_dir, forbidden_prefixes in RULES:
        if not source_dir.exists():
            continue
        for py_file in source_dir.rglob("*.py"):
            if ".venv" in py_file.parts:
                continue
            for lineno, line in enumerate(py_file.read_text().splitlines(), start=1):
                match = IMPORT_RE.match(line)
                if not match:
                    continue
                module = match.group(1)
                for forbidden in forbidden_prefixes:
                    if module == forbidden or module.startswith(forbidden + "."):
                        violations.append(
                            f"{py_file.relative_to(REPO_ROOT)}:{lineno}: "
                            f"forbidden import '{module}' (boundary rule for {source_dir.name})"
                        )
    return violations


def main() -> int:
    violations = find_violations()
    if violations:
        print("Import-Grenzverletzungen gefunden:")
        for violation in violations:
            print(f"  {violation}")
        return 1
    print("Import-Grenzen eingehalten (keine Verletzung gefunden).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
