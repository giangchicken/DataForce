"""DEFINITION · ConfigError -- the one exception this codebase defines.

A declaration that is wrong or missing, raised before any record is read. Everything that goes
wrong about a single record is a value on that record instead (Requirement 43).
"""


class ConfigError(Exception):
    """A declaration is wrong or missing, and no record has been read yet."""
