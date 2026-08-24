"""DEFINITION · RecordsRequest and RecordsResponse — the body every record route shares.

Every route but ``/load-data`` takes records and returns records, so this is one module rather than
four copies of one model. One ``schemas.py`` per router was the plan, on the grounds that each router
needs a quarter of what a single module would hold; counting the routes retired it. Three of the four
would have imported this pair from somewhere anyway, and "somewhere" had no home in the layout
(Decision 20).

What one router alone speaks stays with that router -- ``load_data/schemas.py`` and
``human_review/schemas.py`` -- because no consumer should depend on what it does not use
(AGENTS.md section 6). Every field carries its description: that text is what a caller reads in
``/docs`` (Requirement 1).
"""
