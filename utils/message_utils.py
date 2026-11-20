"""Message personalization utilities."""
from html import escape


def personalize_message(message: str, full_name: str) -> str:
    """Prepend a safely escaped greeting to an HTML-formatted broadcast."""
    if not full_name:
        return message
    safe_name = escape(full_name)
    return f"ሰላም {safe_name}\n{message}"
