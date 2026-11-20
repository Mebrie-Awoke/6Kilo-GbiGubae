"""Database URL helpers shared by the application and Alembic."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_async_database_url(url: str) -> str:
    """Return a SQLAlchemy asyncpg URL for common PostgreSQL provider formats."""
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

    if normalized.startswith("postgresql+asyncpg://"):
        parts = urlsplit(normalized)
        query = parse_qsl(parts.query, keep_blank_values=True)
        normalized_query = []
        sslmode = None
        for key, value in query:
            if key == "sslmode":
                sslmode = value
            else:
                normalized_query.append((key, value))
        if sslmode and not any(key == "ssl" for key, _ in normalized_query):
            normalized_query.append(("ssl", sslmode))
        normalized = urlunsplit(
            (
                parts.scheme,
                parts.netloc,
                parts.path,
                urlencode(normalized_query),
                parts.fragment,
            )
        )

    return normalized
