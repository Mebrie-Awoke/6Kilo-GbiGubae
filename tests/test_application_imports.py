"""Smoke test application imports with non-production configuration."""
import os
import unittest


os.environ.setdefault("BOT_TOKEN", "123456:TEST_TOKEN")
os.environ.setdefault("SUPER_ADMIN_ID", "1")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/test_db")
os.environ.setdefault("WEBHOOK_SECRET", "ci-secret")
os.environ.setdefault("RENDER_EXTERNAL_URL", "https://example.onrender.com")


class ApplicationImportTests(unittest.TestCase):
    def test_postgres_fsm_storage_can_be_instantiated(self):
        from storage.postgres import PostgresStorage
        storage = PostgresStorage()
        self.assertIsNotNone(storage)

    def test_webhook_application_imports(self):
        import main
        self.assertEqual(main.WEBHOOK_PATH, "/telegram/webhook")


if __name__ == "__main__":
    unittest.main()
