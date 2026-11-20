"""Small, testable authorization helpers."""


def is_admin_user(user_id: int, is_admin_flag: bool, super_admin_id: int | None) -> bool:
    """Check admin status without implicitly granting access to new users."""
    return user_id == super_admin_id or bool(is_admin_flag)
