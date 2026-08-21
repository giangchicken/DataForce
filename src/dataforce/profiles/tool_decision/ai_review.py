"""STEP · ai_review (stages 5-6) · one answer out of several jurors' answers.

Stage 5 has a panel answer the same record independently and needs one answer out of
what they said; stage 6 ranks records for review and needs nothing from a profile that
`utils.answer_distance` does not already give it. So this phase asks a profile for
exactly one thing, and this module is that one thing.

The distance between two answers is not here even though this phase computes it three
times over. Stage 10 computes it too, in `human_review`, and a phase module that
imported a sibling phase would be the one coupling this layout exists to prevent --
so δ is `utils.py`, which both phases may read.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from dataforce.profiles.base import Answer
from dataforce.profiles.tool_decision.schema import Catalog
from dataforce.profiles.tool_decision.utils import named_calls

__all__ = ["vote_consensus"]


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
    read = [named_calls(vote) for vote in votes]
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
