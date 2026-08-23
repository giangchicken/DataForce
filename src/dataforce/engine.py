"""DEFINITION · Engine and Registry -- a resolved pair, held; no I/O.

The type is the engine's because every service names it in its signature; the reader that fills
one from files is ``edge/bootstrap.py``, because reading is the edge's job. A registry is instance
state: two in one process hold different implementations (Requirement 39).
"""
