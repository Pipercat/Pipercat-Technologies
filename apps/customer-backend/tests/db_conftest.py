"""Shared fixtures for tests that need a real PostgreSQL database.

Not named conftest.py on purpose: importing it is opt-in (only the two
test modules that need Postgres import from here), so the rest of the
customer-backend suite (which is fast and dependency-free) is unaffected
if no database is reachable.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

APP_ROOT = Path(__file__).resolve().parent.parent

requires_database = pytest.mark.skipif(
    "DATABASE_URL" not in os.environ,
    reason="DATABASE_URL not set - PostgreSQL integration tests need a real database "
    "(see infrastructure/docker-compose/.env.example or run one locally).",
)


def alembic_config() -> Config:
    cfg = Config(str(APP_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(APP_ROOT / "alembic"))
    return cfg


@pytest.fixture
def migrated_db():
    """Runs the full migration stack against DATABASE_URL, yields a
    connected session, then tears the schema back down. Every test using
    this fixture starts from a clean, freshly migrated database."""
    cfg = alembic_config()
    command.upgrade(cfg, "head")

    engine = create_engine(os.environ["DATABASE_URL"])
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        command.downgrade(cfg, "base")
