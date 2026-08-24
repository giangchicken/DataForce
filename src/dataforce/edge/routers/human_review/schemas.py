"""DEFINITION · SyncResponse — the one model /human-review adds to the shared body.

``POST /human-review/publish/sync`` is the one route that is not a record-bus service, so it is
the one shape no other router speaks. Everything else this router serves takes and returns the
shared pair in ``routers/schemas.py``. It stays here because no consumer should depend on what it
does not use (AGENTS.md section 6). Every field carries its description: that text is what a
caller reads in ``/docs`` (Requirement 1).
"""
