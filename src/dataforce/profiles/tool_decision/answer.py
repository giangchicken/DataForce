"""DEFINITION · everything the pipeline computes from an answer.

An answer is a set of **calls** drawn from the record's own catalog, and a call is a
name *and* the arguments it is called with. It is carried as a JSON array because an
artifact is JSONL and a set is not JSON; δ reads it as the set it means, so two votes
listing the same calls in different orders agree exactly.

Four things, because each is the answer in a different position: the calls an answer
means, the distance between two answers, the consensus of several, and the answer as a
training example states it. What an answer *looks like* -- the type, and one record's
space built from its own catalog -- is `schema.py`.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from dataforce.profiles.base import Answer
from dataforce.shared.errors import InvariantError
from dataforce.shared.record import Record, TextPart

__all__ = ["answer_distance", "calls_by_name", "training_example", "vote_consensus"]


def calls_by_name(answer: Answer) -> dict[str, dict[str, Any]]:
    """The calls an answer means, keyed by tool name, the first spelling of a name winning.

    A bare string entry is the call with no arguments. That is what makes a names-only
    source a special case of this answer type rather than a second one, and requirement
    72's reduction -- δ equals Jaccard over names when arguments agree -- is asserted on
    exactly it.

    A bare *answer* is rejected rather than iterated: `set("SendMail")` is a set of
    characters, and a δ that accepted it would silently compare spellings.

    A repeated name collapses here. Requirement 73 declares the multiset out and
    `label_names_one_tool_twice` finds one by comparing this length against the
    answer's, so nothing downstream has to decide which of two calls to one tool won.
    """
    if isinstance(answer, str) or not isinstance(answer, Iterable):
        raise TypeError(f"an answer is an array of calls, not {type(answer).__name__}")
    calls: dict[str, dict[str, Any]] = {}
    for entry in answer:
        if isinstance(entry, str):
            calls.setdefault(entry, {})
            continue
        if not isinstance(entry, Mapping) or not isinstance(entry.get("name"), str):
            raise TypeError(f"a call is a name and its arguments, not {entry!r}")
        arguments = entry.get("arguments") or {}
        if not isinstance(arguments, Mapping):
            raise TypeError(
                f"the arguments of {entry['name']!r} are an object, not {arguments!r}"
            )
        calls.setdefault(entry["name"], dict(arguments))
    return calls


def answer_distance(a: Answer, b: Answer) -> float:
    """Jaccard distance over the names called, with two empty answers agreeing perfectly.

    `answer_distance(∅, ∅) = 0` is returned before the division, and it is load-bearing:
    35.4% of the reference source is the empty answer, so a `0/0` would make the
    population carrying the real difficulty look like the one with least agreement.

    Arguments are read but not yet compared: this is names-only, so a call carrying the
    wrong arguments to the right tool still reads as agreement. Requirement 72 makes it
    soft, and C3 is where that lands -- keeping it here would mean changing δ in the
    same commit that changed what an answer is, and only one of the two could then be
    bisected to.
    """
    left, right = calls_by_name(a).keys(), calls_by_name(b).keys()
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
    counted = Counter(name for vote in votes for name in calls_by_name(vote))
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
