"""LOGIC · open_engine -- the composition root; the only builder of an Engine.

Exactly one place constructs concrete dependencies and wires them together (P19). It reads the two
manifests, the thresholds and the prompt templates, registers both axes, and returns one Engine.
An engine can also be built with no filesystem anywhere, which is what makes a web handler and an
in-process caller the same caller.
"""
