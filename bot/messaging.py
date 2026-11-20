"""Shared message formatting helpers."""


def personalize_announcement(name: str | None, message: str) -> str:
    """Add a short Amharic greeting with the recipient's registered name."""
    recipient_name = (name or "").strip() or "there"
    return f"ሰላም {recipient_name}!\n\n{message}"
