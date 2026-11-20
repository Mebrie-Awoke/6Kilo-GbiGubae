"""Unit tests for PostgreSQL URL normalization."""
import unittest

from db.url import normalize_async_database_url


class DatabaseUrlTests(unittest.TestCase):
    def test_postgres_scheme_is_upgraded_to_asyncpg(self):
        self.assertEqual(
            normalize_async_database_url("postgres://user:pass@host/db"),
            "postgresql+asyncpg://user:pass@host/db",
        )

    def test_postgresql_scheme_is_upgraded_to_asyncpg(self):
        self.assertEqual(
            normalize_async_database_url("postgresql://user:pass@host/db"),
            "postgresql+asyncpg://user:pass@host/db",
        )

    def test_asyncpg_scheme_is_preserved(self):
        url = "postgresql+asyncpg://user:pass@host/db"
        self.assertEqual(normalize_async_database_url(url), url)

    def test_sslmode_is_converted_for_asyncpg(self):
        self.assertEqual(
            normalize_async_database_url(
                "postgresql://user:pass@host/db?sslmode=require&application_name=bot"
            ),
            "postgresql+asyncpg://user:pass@host/db?application_name=bot&ssl=require",
        )

    def test_empty_url_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_async_database_url("")

    def test_sync_driver_is_replaced(self):
        self.assertEqual(
            normalize_async_database_url("postgresql+psycopg2://user:pass@host/db"),
            "postgresql+asyncpg://user:pass@host/db",
        )


if __name__ == "__main__":
    unittest.main()
