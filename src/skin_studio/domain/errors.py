"""Domain-level errors."""


class SkinStudioError(Exception):
    """Base error safe to present after translation."""


class DuplicateProfileError(SkinStudioError):
    """Raised when a profile name is already in use."""


class InvalidProfileError(SkinStudioError):
    """Raised when a profile name is empty or too long."""


class InvalidProfileImportError(SkinStudioError):
    """Raised when an imported profile is malformed or outside allowed limits."""
