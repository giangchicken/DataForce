"""facade · what a finished text2text review becomes once it is kept."""

from .duplicate_data_checking import calculate_duplicates
from .schema import DuplicateGroups, LabelSummary, StoredSample

__all__ = [
    "DuplicateGroups",
    "LabelSummary",
    "StoredSample",
    "calculate_duplicates",
]
