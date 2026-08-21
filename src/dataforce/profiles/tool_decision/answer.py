"""DEFINITION · everything the pipeline computes from an answer.

An answer is a set of **calls** drawn from the record's own catalog, and a call is a
name *and* the arguments it is called with. It is carried as a JSON array because an
artifact is JSONL and a set is not JSON; δ reads it as the set it means, so two votes
listing the same calls in different orders agree exactly.

Four things, because each is the answer in a different position: the calls an answer
means, the distance between two answers, the consensus of several, and the answer as a
training example states it. What an answer *looks like* -- the type, and one record's
space built from its own catalog -- is `schema.py`.

δ is soft and consensus is per-argument, both by requirement 72 and 74, and the reason
they live together is that the second must not produce a call the first would then have
to score against a schema it fails.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from dataforce.profiles.base import Answer
from dataforce.profiles.tool_decision.schema import Catalog
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


def _argument_agreement(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    """How far two calls to one tool agree: the share of keys present in both and equal.

    Over the *union* of keys, so a key present in only one is a disagreement. That is
    why it is not `len(shared) / len(left)`, which would call a one-argument call a
    perfect match for the same call carrying five. Two calls with no arguments agree
    perfectly, which is what makes a names-only answer reduce exactly. Both are
    requirement 72.
    """
    keys = left.keys() | right.keys()
    if not keys:
        return 1.0
    agreed = sum(
        1 for key in keys if key in left and key in right and left[key] == right[key]
    )
    return agreed / len(keys)


def answer_distance(a: Answer, b: Answer) -> float:
    """Name-first: a different tool disagrees fully, a differing argument only partly.

    Requirement 72. Over the union of names in the two answers, a name in both
    contributes how far its arguments agree and a name in only one contributes zero;
    δ is one minus the mean of those contributions. So naming a different tool is full
    disagreement and naming the same tool with one differing argument is *partial*,
    which is the whole point: the two failures are not equally wrong and a jury that
    scored them the same would rank them the same.

    `answer_distance(∅, ∅) = 0` is returned before the division, and it is load-bearing:
    35.4% of the reference source is the empty answer, so a `0/0` would make the
    population carrying the real difficulty look like the one with least agreement.

    When every matched call has identical arguments this **is** Jaccard over names --
    two argument-less calls agree perfectly, so each matched name contributes exactly 1
    -- so a names-only profile is the special case rather than a different formula, and
    every measurement taken before arguments existed still describes it.

    The mean over the union of names is a *choice*, recorded as one in requirement 72:
    it weights every named tool equally, so a record whose answer is one call and a
    record whose answer is four are scored on the same scale. Changing it is a threshold
    decision with its own task.
    """
    left, right = calls_by_name(a), calls_by_name(b)
    names = left.keys() | right.keys()
    if not names:
        return 0.0
    agreement = sum(
        _argument_agreement(left[name], right[name])
        for name in names
        if name in left and name in right
    )
    return 1.0 - agreement / len(names)


def _agreed_arguments(calls: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Each argument key's majority value among the votes that named this tool.

    A key with no strict majority is *absent* rather than guessed -- requirement 74 --
    and the caller then decides whether the call survives without it. Values are counted
    through their canonical JSON because an argument may be an object or an array, which
    a `Counter` cannot key on directly.
    """
    majority = len(calls) / 2
    agreed: dict[str, Any] = {}
    for key in sorted({key for call in calls for key in call}):
        counted = Counter(
            json.dumps(call[key], sort_keys=True) for call in calls if key in call
        )
        value, count = counted.most_common(1)[0]
        if count > majority:
            agreed[key] = json.loads(value)
    return agreed


def vote_consensus(votes: list[Answer], catalog: Catalog) -> Answer | None:
    """The calls a strict majority agreed on, assembled only where they assemble fully.

    Requirement 74, in two passes. A name is in the consensus when a strict majority of
    all votes included it. Each of that name's argument keys then takes the value a
    strict majority of the votes *naming it* gave -- naming it, not voting at all, since
    a juror who did not call the tool has no opinion about its arguments.

    A call missing a key the tool declares `required` is dropped entirely rather than
    completed. Never a partially-invented call: a consensus call that would fail
    requirement 71's validation is not a consensus, and shipping one would put a value
    no juror proposed into a ranking signal.

    The catalog is a parameter because `required` is the tool's own declaration and
    nothing else can answer it. That is why this signature takes more than the votes.

    May be a set no individual juror proposed -- three jurors voting AB, BC, AC give
    ABC -- which is acceptable for a ranking signal and is exactly why the core forbids
    it from becoming a label on its own. No votes means no consensus, which is not the
    same answer as the empty set.
    """
    if not votes:
        return None
    read = [calls_by_name(vote) for vote in votes]
    majority = len(votes) / 2
    required_by_name = {tool.name: set(tool.required) for tool in catalog.tools}

    agreed: list[dict[str, Any]] = []
    for name in sorted({name for vote in read for name in vote}):
        naming = [vote[name] for vote in read if name in vote]
        if len(naming) <= majority:
            continue
        arguments = _agreed_arguments(naming)
        if required_by_name.get(name, set()) - arguments.keys():
            continue
        agreed.append({"name": name, "arguments": arguments})
    return agreed


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
