"""Database URL helpers shared by the application and Alembic."""
from __future__ import annotations


def normalize_async_database_url(url: str) -> str:
    """Return a SQLAlchemy async-compatible PostgreSQL URL."""
    if not url or not url.strip():
        raise ValueError("DATABASE_URL is required.")

    normalized = url.strip()
    if normalized.startswith("postgres://"):
        normalized = "postgresql://" + normalized[len("postgres://") :]

    if normalized.startswith("postgresql://"):
        normalized = "postgresql+asyncpg://" + normalized[len("postgresql://") :]
    elif normalized.startswith("postgresql+psycopg2://"):
        normalized = "postgresql+asyncpg://" + normalized[len("postgresql+psycopg2://") :]
    elif normalized.startswith("postgresql+psycopg://"):
        normalized = "postgresql+asyncpg://" + normalized[len("postgresql+psycopg://") :]

    if normalized.startswith("postgresql+") and not normalized.startswith("postgresql+asyncpg://"):
        raise ValueError("DATABASE_URL must use the asyncpg PostgreSQL driver.")
    return normalized
