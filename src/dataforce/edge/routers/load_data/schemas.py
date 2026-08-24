"""DEFINITION · LoadDataRequest and LoadDataResponse — the one route the modality reshapes.

``/load-data`` is the one route that takes no records -- ``items`` inline or a ``source``
reference, resolved per modality. Nothing else speaks these two, so they are here rather than in
``routers/schemas.py`` beside the shared body: no consumer should depend on what it does not use
(AGENTS.md section 6). Every field carries its description: that text is what a caller reads in
``/docs`` (Requirement 1).
"""
