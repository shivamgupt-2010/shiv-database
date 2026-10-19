import re
from typing import Set
from app.core.exceptions import AuthenticationError

RESERVED_USERNAMES: Set[str] = {
    "admin",
    "administrator",
    "root",
    "system",
    "superuser",
    "support",
    "security",
    "oauth",
    "oidc",
    "well-known",
    "api",
    "auth",
    "login",
    "register",
    "logout",
    "shiv",
    "shivdb",
    "shividentity",
    "settings",
    "profile",
    "account",
    "dashboard",
    "help",
    "terms",
    "privacy",
    "billing",
    "null",
    "undefined",
    "test",
    "dev",
    "developer",
    "portal",
    "docs",
    "status",
    "bot",
    "daemon",
}

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9_-]{1,28}[a-zA-Z0-9])?$")


def normalize_username(username: str) -> str:
    """Normalize a username to lowercase without leading/trailing whitespace."""
    if not username:
        return ""
    return username.strip().lower()


def validate_username(username: str, allow_reserved: bool = False) -> str:
    """
    Validates username against SHIV Identity rules:
    - 3 to 30 characters
    - Must start and end with an alphanumeric character
    - Allowed characters: a-z, A-Z, 0-9, underscore, hyphen
    - No consecutive underscores or hyphens
    - Cannot match reserved names (unless explicitly allowed for internal bootstrap)
    """
    if not username:
        raise AuthenticationError("Username is required")

    trimmed = username.strip()
    if len(trimmed) < 3:
        raise AuthenticationError("Username must be at least 3 characters long")
    if len(trimmed) > 30:
        raise AuthenticationError("Username cannot exceed 30 characters")

    if not USERNAME_REGEX.match(trimmed):
        raise AuthenticationError(
            "Username can only contain letters, numbers, underscores, and hyphens, and must start/end with a letter or number"
        )

    if "--" in trimmed or "__" in trimmed or "-_" in trimmed or "_-" in trimmed:
        raise AuthenticationError("Username cannot contain consecutive special characters")

    normalized = normalize_username(trimmed)
    if not allow_reserved and normalized in RESERVED_USERNAMES:
        raise AuthenticationError(f"Username '{trimmed}' is reserved by the SHIV platform")

    return trimmed
