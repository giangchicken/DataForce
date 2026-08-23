"""DataForce -- a raw, model-labelled corpus into a training-ready dataset, and the evidence for it.

**Import direction, stated once, and never reversed.** ``edge/`` and ``cli.py`` may import the
engine; the engine may not import them. Everything that touches a file, a socket or a clock is
the edge; everything else is the engine, and the arrow points one way (Requirement 36). This is
not discipline: ``tests/guards/`` holds the scan, and a subprocess import from a directory with
no ``config/`` proves the engine reads nothing when it is imported (Requirement 37).

**A module's first word says what kind of module it is** (Requirement 2): ``DEFINITION`` one noun
and its shape, ``LOGIC`` the conversions over that noun, ``STEP`` serves exactly one stage of the
flow, ``TOOL`` not in the flow at all. A fifth word, ``façade``, marks an ``__init__.py`` that
re-exports and holds nothing of its own. Requirement 2 names four kinds and the spec's own package
layout writes a fifth over ``pipeline/__init__.py``, because none of the four describes a module
with no content of its own; AGENTS.md section 8 says a rule broken on purpose is recorded where
the next reader will hit it, so it is recorded here and in the spec.
"""
