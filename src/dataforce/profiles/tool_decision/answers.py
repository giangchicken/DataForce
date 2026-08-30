"""LOGIC · the answer space, and the three operations over an answer: distance, permitted, consensus.

What an answer *is* is ``schema.py``'s; this is everything done with one. The space is materialised
from the record rather than stored on it (I10) -- ``answer_schema`` builds one when asked, so there
is no second copy to disagree with the catalog the source carried verbatim.

**Lenient in one direction and strict in the other.** δ, the five checks and consensus all run over
whatever a source or a juror produced and none of them may raise (Requirement 43), so ``calls_in``
reads what it can and leaves the rest out; what it dropped shows up as a cardinality or catalog
difference in ``label_check`` rather than as a stop. An answer an *annotator* produced is the one
case that must not be lenient, and ``annotations.py`` puts the whole of one through
``answer_is_permitted`` before it can reach a record.

δ has one definition, here, and the protocol member forwards to it. Every stage that asks how far
apart two answers are asks the same question and gets the same arithmetic, which is what makes a
cohesion figure and an agreement statistic comparable at all.
"""

import json
from collections.abc import Mapping, Sequence
from typing import Any

import jsonschema  # type: ignore[import-untyped]  # guard-exempt: I6 · answer validation with no model call has no owner in the library · the profile · 2026-08-24

from dataforce.profiles.tool_decision.schema import Call, Calls, Tool
from dataforce.record import Record, StoredAnswer, canonical_json

# Where a record keeps the catalog its source carried, and the key one entry holds it under.
TOOLS = "tools"
FUNCTION = "function"

# A tool's JSON Schema, by key, and the two keys a call is made of.
NAME = "name"
ARGUMENTS = "arguments"
PARAMETERS = "parameters"
DESCRIPTION = "description"
PROPERTIES = "properties"
REQUIRED = "required"
ADDITIONAL_PROPERTIES = "additionalProperties"


def entries_in(value: Any) -> tuple[Any, ...]:
    """The entries a value holds, where a string holds none.

    `tuple("SendStatement")` is a tuple of thirteen characters, and every place below that reads a
    list out of a source item or a tool's own schema could be handed a string instead. One function
    rather than an `isinstance` beside each of them, because the one that gets forgotten is the one
    that turns a malformed label into thirteen calls.
    """
    if isinstance(value, str) or not isinstance(value, Sequence):
        return ()
    return tuple(value)


def calls_in(stored: StoredAnswer) -> Calls:
    """The answer a record stores, parsed. A bare name reads as the call with no arguments.

    Lenient by design: δ, the five checks and consensus all run over whatever a source or a juror
    produced, and none of them may raise (Requirement 43). An entry this cannot read is left out,
    which shows up as a cardinality or catalog difference in `label_check` rather than as a stop.
    An entry an *annotator* produced is the one case that must not be lenient, and
    `annotation_response` validates the whole answer instead.
    """
    read = []
    for entry in stored:
        if isinstance(entry, str):
            read.append(Call(name=entry))
        elif isinstance(entry, Mapping) and isinstance(entry.get(NAME), str):
            arguments = entry.get(ARGUMENTS)
            read.append(
                Call(
                    name=entry[NAME],
                    arguments=dict(arguments) if isinstance(arguments, Mapping) else {},
                )
            )
    return tuple(read)


def catalog_of(record: Record) -> tuple[Tool, ...]:
    """What this record offered, out of the `tools` its source carried verbatim.

    The catalog is source data kept in `meta` (Requirement 9), never an answer space written onto
    the record (I10): a stored space is a second thing that can disagree with the first, and
    `answer_schema` materialises one from this when asked.
    """
    read = []
    for entry in entries_in(record.meta.get(TOOLS)):
        function = entry.get(FUNCTION) if isinstance(entry, Mapping) else None
        if not isinstance(function, Mapping) or not isinstance(function.get(NAME), str):
            continue
        parameters = function.get(PARAMETERS)
        read.append(
            Tool(
                name=function[NAME],
                description=str(function.get(DESCRIPTION) or ""),
                parameters=dict(parameters) if isinstance(parameters, Mapping) else {},
            )
        )
    return tuple(read)


def one_call_schema(tool: Tool) -> dict[str, Any]:
    """One branch of the `oneOf`: this tool's name and this tool's arguments, constrained together.

    `OpenTicket` carrying `LookupBalance`'s argument is two valid halves and one invalid call, which
    an `enum` of names beside a free-form object cannot say. Closing the arguments object is what
    makes that true: an argument a tool does not declare is not a permitted answer. A catalog that
    declares `additionalProperties` itself is left alone -- the tool's own schema wins where it
    speaks.
    """
    arguments = {PROPERTIES: {}, **tool.parameters, "type": "object"}
    arguments.setdefault(ADDITIONAL_PROPERTIES, False)
    return {
        "type": "object",
        PROPERTIES: {NAME: {"const": tool.name}, ARGUMENTS: arguments},
        REQUIRED: [NAME, ARGUMENTS],
        ADDITIONAL_PROPERTIES: False,
    }


def answer_schema(record: Record, max_calls: int) -> dict[str, Any]:
    """This record's permitted answers: `oneOf` per offered tool. Never persisted.

    An empty catalog materialises `maxItems: 0`: there was nothing to choose from, so the empty
    answer is the only valid one. What this schema cannot say is *at most one call per tool name* --
    `uniqueItems` compares whole calls -- so `answer_is_permitted` checks the names beside it and
    `label_names_one_tool_twice` is the check that reports it on a label.

    It also does not accept a bare name, and that is not an asymmetry with `calls_in`: this is what
    a *producer* must satisfy -- a jury answering it, an annotator's form inverted through
    `annotation_response` -- and both of those emit objects. Reading a bare name is a tolerance for
    a names-only source's label, which no producer writes.
    """
    catalog = catalog_of(record)
    if not catalog:
        return {"type": "array", "maxItems": 0}
    return {
        "type": "array",
        "maxItems": max_calls,
        "uniqueItems": True,
        "items": {"oneOf": [one_call_schema(tool) for tool in catalog]},
    }


def answer_is_permitted(record: Record, answer: StoredAnswer, max_calls: int) -> bool:
    """Does this answer validate against this record's own answer schema.

    Validated by `jsonschema` rather than by a second reading of the catalog, which is why the
    import above carries an exemption: `agent-toolkit` owns validation and exposes it only inside
    `complete_structured`, and a hand-written twin of a schema we materialise ourselves is exactly
    the pair of definitions I6 exists to prevent -- the two drift on the first `enum` nobody
    remembered to check.
    """
    named = [call.name for call in calls_in(answer)]
    if len(set(named)) != len(named):
        return False
    schema = answer_schema(record, max_calls)
    return bool(jsonschema.Draft202012Validator(schema).is_valid(list(answer)))


def argument_agreement(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    """The share of argument keys present in both and equal, over the **union** of keys.

    Over the union and never the left side: `len(shared) / len(left)` would call a one-argument call
    a perfect match for the same call carrying five. Two argument-less calls agree perfectly, which
    is what makes the reduction to Jaccard exact.
    """
    keys = left.keys() | right.keys()
    if not keys:
        return 1.0
    shared = sum(
        1
        for key in keys
        if key in left
        and key in right
        and canonical_json(left[key]) == canonical_json(right[key])
    )
    return shared / len(keys)


def answer_distance(a: StoredAnswer, b: StoredAnswer) -> float:
    """δ: 0.0 identical, 1.0 unrelated. Name-first, soft over arguments. `δ(∅, ∅) = 0`.

    Over the union of names: a name in both contributes its argument agreement, a name in one
    contributes zero, and δ is one minus the mean. `δ(∅, ∅) = 0` is returned before the division and
    is load-bearing rather than tidy -- the empty answer is a large share of a real corpus, and a δ
    that returned `NaN` there would take every cohesion figure, every bucket and every α with it.

    With every matched call argument-less the expression collapses to `1 − |A∩B| / |A∪B|` exactly,
    so every number measured before arguments existed still describes this δ.
    """
    left = {call.name: call.arguments for call in calls_in(a)}
    right = {call.name: call.arguments for call in calls_in(b)}
    names = left.keys() | right.keys()
    if not names:
        return 0.0
    agreements = [
        argument_agreement(left[name], right[name])
        if name in left and name in right
        else 0.0
        for name in names
    ]
    return 1.0 - sum(agreements) / len(agreements)


def agreed_arguments(called: Sequence[Call]) -> dict[str, Any]:
    """Each argument key's value where a strict majority of the votes naming that tool gave it.

    Naming it, not voting at all: a juror who did not call the tool has no opinion about its
    arguments. A key with no majority is absent, and what happens to a call missing a `required` one
    is `vote_consensus`'s to decide.

    Sorted twice, and neither is cosmetic: iterating a set of strings is hash-ordered, and this runs
    in the process that produces the record. A tie cannot win a strict majority -- two values at
    count `c` need `2c` votes, so `c` is at most the floor -- so the tie-break below decides nothing;
    sorting is what makes that true of the *output* rather than only of the arithmetic.
    """
    floor = len(called) / 2
    agreed = {}
    for key in sorted({key for call in called for key in call.arguments}):
        stated = [
            canonical_json(call.arguments[key])
            for call in called
            if key in call.arguments
        ]
        top = max(sorted(set(stated)), key=stated.count)
        if stated.count(top) > floor:
            agreed[key] = json.loads(top)
    return agreed


def vote_consensus(
    votes: Sequence[StoredAnswer], record: Record, max_calls: int
) -> StoredAnswer | None:
    """What N answers about one record come to; `()` where none; None where none is defensible.

    Two callers, and they are a panel and a room of people: `jury` folds model votes and `curate`
    folds the corrections annotators typed. The fold is the same question either way -- given
    several answers to one record, which one is defensible -- and having one owner for it is what
    keeps the two from drifting into two ideas of what agreement means.

    Per name, then per argument. Step 1 -- a strict majority voting the empty answer *is* the empty
    answer -- is what keeps `()` and `None` apart: *the panel agreed to call nothing* and *the panel
    produced nothing defensible* stay two values rather than one value read two ways.

    A call is **dropped, not completed**, where the tool declares an argument no majority gave, or
    where no such tool is in the catalog at all. Half-building one puts a value no juror proposed
    into a ranking signal, and it would fail this record's own `answer_schema` -- which is also why
    the assembled answer is validated before it is returned rather than asserted about afterwards.
    """
    if not votes:
        return None
    cast = [calls_in(vote) for vote in votes]
    floor = len(cast) / 2
    if sum(1 for vote in cast if not vote) > floor:
        return ()

    named: dict[str, list[Call]] = {}
    for vote in cast:
        for call in {call.name: call for call in vote}.values():
            named.setdefault(call.name, []).append(call)

    catalog = {tool.name: tool for tool in catalog_of(record)}
    agreed = []
    for name, called in sorted(named.items()):
        tool = catalog.get(name)
        if len(called) <= floor or tool is None:
            continue
        arguments = agreed_arguments(called)
        if any(
            key not in arguments for key in entries_in(tool.parameters.get(REQUIRED))
        ):
            continue
        agreed.append(Call(name=name, arguments=arguments))

    answer = tuple(
        {NAME: call.name, ARGUMENTS: dict(call.arguments)} for call in agreed
    )
    if not answer or not answer_is_permitted(record, answer, max_calls):
        return None
    return answer
