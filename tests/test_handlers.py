import unittest

from bot.config import Settings
from bot.handlers import display_batch, normalize_batch, valid_target
from bot.messaging import personalize_announcement


class BatchInputTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            bot_token="test-token",
            super_admin_id=1,
            mongodb_uri="mongodb://localhost:27017",
            mongodb_database="test",
            timezone="Africa/Addis_Ababa",
            batches=("1st Year", "2nd Year", "3rd Year", "4th Year", "5th Year", "6th Year"),
            webhook_secret=None,
            webhook_base_url=None,
            port=8080,
        )

    def test_accepts_canonical_english_labels(self):
        self.assertEqual(normalize_batch("4th Year", self.settings), "4th Year")

    def test_accepts_numeric_year(self):
        self.assertEqual(normalize_batch("4", self.settings), "4th Year")

    def test_accepts_legacy_amharic_button_label(self):
        self.assertEqual(normalize_batch("4ኛ ዓመት", self.settings), "4th Year")

    def test_rejects_unknown_year(self):
        self.assertIsNone(normalize_batch("Graduate", self.settings))

    def test_target_validation_accepts_all_and_batch_aliases(self):
        self.assertTrue(valid_target("all", self.settings))
        self.assertTrue(valid_target("4", self.settings))
        self.assertFalse(valid_target("unknown", self.settings))

    def test_batch_display_is_english(self):
        self.assertEqual(display_batch("4th Year"), "4th Year")
        self.assertEqual(display_batch("all"), "All Members")

    def test_personalized_announcement_includes_amharic_greeting_and_name(self):
        self.assertEqual(
            personalize_announcement("Mebrie Awoke", "Meeting starts at 5 PM."),
            "ሰላም Mebrie Awoke!\\n\\nMeeting starts at 5 PM.",
        )

    def test_personalized_announcement_handles_missing_name(self):
        self.assertEqual(
            personalize_announcement(None, "Important update."),
            "ሰላም there!\\n\\nImportant update.",
        )


if __name__ == "__main__":
    unittest.main()
