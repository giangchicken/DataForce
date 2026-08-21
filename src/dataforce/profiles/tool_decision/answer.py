"""DEFINITION · everything the pipeline computes from an answer.

An answer is a set of tool names drawn from the record's own catalog, carried as a
JSON array because an artifact is JSONL and a set is not JSON. δ reads it as the set
it means, so two votes listing the same tools in different orders agree exactly.

Three things, because each is the answer in a different position: the distance between
two answers, the consensus of several, and the answer as a training example states it.
What an answer *looks like* -- the profile-level schema, and one record's answer space
with its own catalog as an `enum` -- is `schema.py`.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from typing import Any

from dataforce.profiles.base import Answer
from dataforce.shared.errors import InvariantError
from dataforce.shared.record import Record, TextPart

__all__ = ["answer_distance", "training_example", "vote_consensus"]


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


def training_example(record: Record) -> dict[str, Any]:
    """The record as a training example. Invariant 4 is asserted here, not downstream.

    SFT JSONL: the same `messages` list, with the label the record ended up with in both
    the assistant message and `meta.label`. Asserted equal on the way out, because that
    assertion is the one that counted 48 disagreeing records before the source was fixed.
    """
    label = record.label or []
    assistant = json.dumps(label, ensure_ascii=False)
    messages = [
        {
            "role": part.role,
            "content": assistant if part.role == "assistant" else part.text,
        }
        for part in record.content
        if isinstance(part, TextPart)
    ]
    meta = {**record.meta, "label": label}
    if json.loads(assistant) != meta["label"]:
        raise InvariantError(
            f"record {record.rid}: the assistant message and meta.label disagree "
            f"on export -- {assistant} against {meta['label']!r}"
        )
    return {"messages": messages, "meta": meta}
