"""facade · the one table this service writes."""

from .records import Base, latest_row, stored_row

__all__ = ["Base", "latest_row", "stored_row"]
