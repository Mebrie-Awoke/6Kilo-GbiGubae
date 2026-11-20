"""Tests for admin access decisions."""
import unittest

from db.permissions import is_admin_user


class AdminPermissionTests(unittest.TestCase):
    def test_regular_user_is_denied(self):
        self.assertFalse(is_admin_user(123, False, 999))

    def test_registered_admin_is_allowed(self):
        self.assertTrue(is_admin_user(123, True, 999))

    def test_super_admin_is_allowed_even_without_admin_flag(self):
        self.assertTrue(is_admin_user(999, False, 999))

    def test_missing_super_admin_configuration_does_not_grant_access(self):
        self.assertFalse(is_admin_user(123, False, None))


if __name__ == "__main__":
    unittest.main()
