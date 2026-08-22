"""Engine/session construction. No global singleton engine at import time —
tests and Alembic each need their own DATABASE_URL, and constructing an
engine has no side effects until a connection is actually used."""

import os
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. See infrastructure/docker-compose/.env.example."
        )
    return url


@lru_cache
def get_engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True)


def get_sessionmaker() -> sessionmaker:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)
