"""TOOL · one subcommand per stage, dispatched over the flow table; JSONL in, JSONL out.

A dispatch over ``pipeline/flow.py``, not fifteen hand-written subcommand bodies: every service
has one signature, so this stays roughly one screen however many stages exist (Requirement 48).
Part of the edge -- it may import the engine, and the engine may not import it.
"""
