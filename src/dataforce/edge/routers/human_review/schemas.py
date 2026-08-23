"""DEFINITION · the request and response models the /human-review handlers speak.

One schemas module per router rather than one for all four, because each router needs a
quarter of what a single module would hold and no consumer should depend on what it does
not use (AGENTS.md section 6). Every field carries its description: that text is what a
caller reads in /docs (Requirement 1).
"""
