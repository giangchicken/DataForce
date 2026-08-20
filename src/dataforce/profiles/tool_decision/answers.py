"""The answer, δ, and consensus -- the three pieces the whole core is written on.

An answer is a set of tool names drawn from the record's own catalog, carried as a
JSON array because an artifact is JSONL and a set is not JSON. δ reads it as the set
it means, so two votes listing the same tools in different orders agree exactly.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from dataforce.profiles.base import Answer

__all__ = ["ANSWER_SCHEMA", "answer_distance", "vote_consensus"]

# The profile-level shape. The per-record shape adds the catalog as an `enum`, which
# is where requirement 5's constraint is enforced -- inside the library, not here.
ANSWER_SCHEMA: dict[str, Any] = {"type": "array", "items": {"type": "string"}}


def _tools(answer: Answer) -> frozenset[str]:
    """The set an answer means.

    A bare string is rejected rather than iterated: `set("SendMail")` is a set of
    characters, and a δ that accepted it would silently compare spellings.
    """
    if isinstance(answer, str) or not isinstance(answer, Iterable):
        raise TypeError(
            f"an answer is an array of tool names, not {type(answer).__name__}"
        )
    return frozenset(answer)


def answer_distance(a: Answer, b: Answer) -> float:
    """Jaccard distance, with two empty answers agreeing perfectly.

    `answer_distance(∅, ∅) = 0` is returned before the division, and it is load-bearing:
    35.4% of this corpus is the empty set, so a `0/0` would make the population
    carrying the corpus's real difficulty look like the one with least agreement.
    """
    left, right = _tools(a), _tools(b)
    if not left and not right:
        return 0.0
    return 1.0 - len(left & right) / len(left | right)


def vote_consensus(votes: list[Answer]) -> Answer | None:
    """The tools a strict majority of votes included, sorted.

    May be a set no individual juror proposed -- three jurors voting AB, BC, AC
    give ABC -- which is acceptable for a ranking signal and is exactly why the
    core forbids it from becoming a label on its own. No votes means no consensus,
    which is not the same answer as the empty set.
    """
    if not votes:
        return None
    counted = Counter(name for vote in votes for name in _tools(vote))
    majority = len(votes) / 2
    return sorted(name for name, count in counted.items() if count > majority)
