"""facade · what a finished text2text review becomes once it is kept."""

from .duplicate_data_checking import duplicate_groups
from .schema import DuplicateGroups, StoredSample

__all__ = [
    "DuplicateGroups",
    "StoredSample",
    "duplicate_groups",
]
