from __future__ import annotations

from dataclasses import dataclass

from .config import AUTH_ENABLED, PROTOTYPE_USER


@dataclass(frozen=True)
class CurrentUser:
    """Placeholder user context for future authentication and row-level rules."""

    display_name: str
    roles: tuple[str, ...]
    is_authenticated: bool


def get_current_user() -> CurrentUser:
    """Return a local development user until real authentication is added."""

    return CurrentUser(
        display_name=PROTOTYPE_USER,
        roles=("prototype_admin",),
        is_authenticated=not AUTH_ENABLED,
    )

