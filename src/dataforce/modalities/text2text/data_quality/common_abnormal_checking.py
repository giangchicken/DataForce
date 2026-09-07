"""LOGIC · the base every common check shares, held open until the two shapes are decided.

`Check` and `CheckVerdict` are gone from `schema.py` and nothing has replaced them, so neither what
a common check is handed nor what it reports has a shape yet. The class holds the place and says
so; `verdict` returns None until they are decided, and it returns None rather than an invented
shape because a placeholder shape is the one thing a caller would start depending on.
"""

from collections.abc import Sequence


class CommonAbnormalChecking:
    def check_verdict(self, turns: Sequence[str]) -> None:
        """What the checks that need no opinion found. Undecided -- returns nothing yet."""
