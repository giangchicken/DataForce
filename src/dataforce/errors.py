"""DEFINITION · ConfigError -- the one exception this codebase defines.

A declaration that is wrong or missing, raised before any record is read. Everything that goes
wrong about a single record is a value on that record instead (Requirement 43).
"""


class ConfigError(Exception):
    """A declaration is wrong or missing, and no record has been read yet.

    It carries nothing but its message, because every raiser needs a different sentence and the
    § *Error Behavior* table says what each must contain: the manifest, the key and what *is*
    declared for an undeclared label key; the registered names for an unknown axis, with "none"
    where the registry is empty; the modality a profile composes with, where the two disagree.
    A field per case would be a shape the caller has to switch on for a message it only prints.

    The edge turns it into a 400 (spec.md § *Request and response models*). It is the only
    exception the engine raises: a bad *record* is marked on that record and travels on, which is
    the scope split -- configuration stops the run, one item never does.
    """
