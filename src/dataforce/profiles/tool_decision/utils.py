"""LOGIC · the conversions over the shapes in schema.py beside it.

A record turned into a JSON Schema is a conversion, so ``answer_schema`` is here while the models
it constrains are ``schema.py``. ``schema.py`` does not import this module (I4).

**The implementation is here too, for the reason the modality's is** -- ``__init__.py`` is a
``façade ·`` that holds nothing of its own (Requirement 2), and every one of the fifteen members is
a conversion over the shapes beside this line.

**Built with what only the edge can produce.** Identity, the modality it composes with, the source's
vocabulary and the answer's ceiling all come from ``config/profiles/tool_decision.yaml``
(Requirement 40), and the question template comes from ``config/prompts/`` -- read at the edge,
because no engine module opens a file (I1), and handed over the way ``text2text`` is handed its
encoder. That is Requirement 51's split applied one member earlier: policy owns the text, the
profile owns what goes in it.

**An item this cannot read raises, and Requirement 43 says nothing may.** ``build_record`` returns
``Record`` and the signature is § *Profile*'s, so there is no value channel for *this item is
unreadable* -- and ``Record.label`` is required precisely so that a missing label is not defaulted
to *call nothing*. One thing raises ``ConfigError``: an item whose ``meta`` lacks the declared label
key. That is a defect in one item out of twenty thousand, and Requirement 43 permits a
``ConfigError`` only *before any record is read*, so the rule is broken here on purpose (§8) --
``load_data`` is the only caller, it is the only thing that knows the offset, and T14 settled it
there: the raise is caught, counted against the item's offset and handed to the edge as side output,
so a run still completes. ``modalities/text2text/utils.py`` carries the same note for its own two.

A second raise stood here until T14 and is gone rather than caught: provenance arrived under a
magic ``__provenance__`` key on the item and was validated on the way in, which is connascence of
meaning between a stage and one axis (§23). It is a parameter now, so *an item with no provenance*
is unrepresentable and mypy checks what a message used to explain (§32).

**The manifest reader is duplicated from ``text2text/utils.py`` on purpose.** § *Package layout*
says the two axes share ``name``, ``version`` and ``Part`` *and nothing else*; a shared
``declared()`` helper would be a fourth thing, and the first key one axis needed and the other did
not would put a profile's vocabulary in a module the modality imports.
"""

import json
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, final

import jsonschema  # type: ignore[import-untyped]  # guard-exempt: I6 · answer validation with no model call has no owner in the library · the profile · 2026-08-24
from agent_toolkit.string_utils import compute_hash

from dataforce.errors import ConfigError
from dataforce.manifest import Manifest
from dataforce.modalities.text2text import Encoder, Text2Text
from dataforce.profiles.base import AnnotationResponse
from dataforce.profiles.tool_decision.schema import (
    AnswerConfig,
    Call,
    Calls,
    LabelCheck,
    Tool,
)
from dataforce.record import (
    SPOKEN_AND_STATED,
    Branch,
    FinalLabel,
    Part,
    Provenance,
    Record,
    StoredAnswer,
    record_id_for,
    redacted_text,
)

if TYPE_CHECKING:
    from dataforce.modalities import Modality
    from dataforce.profiles import Profile

# What the manifest declares, by key. Identity is `Manifest`'s own three fields and is not here.
ANSWER_CONTROL = "answer_control"
MAX_CALLS = "max_calls"
SHAPE = "shape"
ROLES = "roles"
TARGET = "target"
LABEL = "label"
AT = "at"

# The one declared input shape (Requirement 13). A second one is a manifest line and a reader, and
# the previous tree's second shape -- a catalog rendered into the instruction turn -- is retired.
SHAPES = ("openai_chat_completion",)

# The three surfaces an answer can be captured on. Which one shipped is stamped from the manifest,
# so a measured agreement figure can be read against the surface it was measured on.
CONTROLS = ("names_and_json_arguments", "json_text", "per_name_arguments")

# The source item's own keys. What `load_data` knows and the item does not is a parameter.
ID = "id"
META = "meta"
TOOLS = "tools"
MESSAGES = "messages"
FUNCTION = "function"

# A tool's JSON Schema, by key, and the two keys a call is made of.
NAME = "name"
ARGUMENTS = "arguments"
PARAMETERS = "parameters"
DESCRIPTION = "description"
PROPERTIES = "properties"
REQUIRED = "required"
ADDITIONAL_PROPERTIES = "additionalProperties"

# One annotation's `result` list, by key (spec.md § *The annotation config, and what comes back*).
FROM_NAME = "from_name"
VALUE = "value"
CHOICES = "choices"
TEXT = "text"
VERDICT = "verdict"
# The payload key the capture half owns, read by `$tool_names` in the fragment above it.
TOOL_NAMES = "tool_names"
CORRECTED_NAMES = "corrected_names"
CORRECTED_ARGUMENTS = "corrected_arguments"
NOTE = "note"
INCORRECT = "incorrect"

# The permitted answers to a question. `unsure` is a real answer and not a skip: a skip is
# `was_skipped` and is counted separately (Requirement 50). The first is the one that says the
# label as it stands is right, which `curate` reads off `answer_config` rather than naming.
CORRECT = "correct"
VERDICTS = (CORRECT, INCORRECT, "unsure")

# The capture half of the annotation config. `visibleWhen` + `required` is how Requirement 29 --
# answering `incorrect` requires the corrected value -- becomes something the tool enforces rather
# than something we hope for. `$tool_names` is a dynamic choice list because the catalog is per
# record and a Label Studio project holds one config for every task (Requirement 52).
CAPTURE_TAGS = (
    '<Choices name="verdict" toName="conversation" choice="single-radio"\n'
    '         required="true" requiredMessage="Answer the question before submitting.">\n'
    '  <Choice value="correct"/><Choice value="incorrect"/><Choice value="unsure"/>\n'
    "</Choices>\n"
    '<View visibleWhen="choice-selected" whenTagName="verdict" whenChoiceValue="incorrect">\n'
    '  <Choices name="corrected_names" toName="conversation" choice="multiple"\n'
    '           value="$tool_names" required="true"/>\n'
    '  <TextArea name="corrected_arguments" toName="conversation" rows="4"/>\n'
    "</View>\n"
    '<TextArea name="note" toName="conversation" rows="2"/>'
)

# What two records of one scenario share, in hex characters (`scenario_hash`).
SCENARIO_LENGTH = 16


def canonical_json(value: Any) -> str:
    """One JSON value as the one string that means it.

    Argument values are compared through this rather than with `==` because an argument may itself
    be an object or an array, and two dicts that differ only in key order are one value.

    The same three options are the modality's and `record_id_for`'s, and I24 is what holds the three
    copies to one form -- a `record_id` is the hash of the string this shape produces.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


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


def declaration(manifest: Manifest, *path: str) -> Any:
    """One value the manifest declares, or a `ConfigError` naming the path and what is there."""
    reached: Any = manifest.declarations
    for key in path:
        if not isinstance(reached, Mapping) or key not in reached:
            held = sorted(reached) if isinstance(reached, Mapping) else reached
            raise ConfigError(
                f"config/profiles/{manifest.name}.yaml declares no "
                f"{'.'.join(path)}: {key!r} is missing from {held!r}"
            )
        reached = reached[key]
    return reached


def declared_text(manifest: Manifest, *path: str) -> str:
    """One declared non-empty string, or a `ConfigError` naming the path and what it holds.

    What it replaced was `str(...)`: `label: {at: [label]}` coerced to `"['label']"`, a key no item
    carries, and the run then failed once per record with a message about the *item* rather than
    about the line that was wrong.
    """
    value = declaration(manifest, *path)
    if not isinstance(value, str) or not value:
        raise ConfigError(
            f"config/profiles/{manifest.name}.yaml declares {'.'.join(path)} as "
            f"{value!r}, which is not a key name"
        )
    return value


def declared_count(manifest: Manifest, *path: str) -> int:
    """One declared whole number of one or more, or a `ConfigError` naming what is there.

    `int()` was doing this and doing it silently: `max_calls: 2.7` truncated to 2 and
    `max_calls: true` became 1, so a mistyped ceiling became `maxItems` and
    `label_cardinality_anomaly`'s boundary without anything to read in a diff. `bool` is excluded
    before `int` because `True` *is* an `int` in Python, which is exactly how the `true` case got
    through.
    """
    value = declaration(manifest, *path)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigError(
            f"config/profiles/{manifest.name}.yaml declares {'.'.join(path)} as "
            f"{value!r}, which is not a whole number of calls"
        )
    return value


def one_role(manifest: Manifest, part: str) -> str:
    """What this source calls one of the pipeline's roles, where a list means its first entry."""
    named = declaration(manifest, ROLES, part)
    first = named[0] if isinstance(named, list) and named else named
    if not isinstance(first, str) or not first:
        raise ConfigError(
            f"config/profiles/{manifest.name}.yaml declares roles.{part} as {named!r}, "
            "which names no role"
        )
    return first


def final_label(record: Record) -> StoredAnswer:
    """The answer that ships: what `curate` decided, or the one the record arrived with.

    A conversion over a record, not a fifteenth member. It was a public method on `ToolDecision` for
    one commit, used no `self`, and appeared in neither § *Profile*'s members nor the plan -- the
    same guess T13 refused to make for `redact_label`, arrived at by accident instead of by argument.
    I23 is the guard that now says so.
    """
    curated: FinalLabel | None = record.human_review.curate
    if curated is None or curated.status == "unresolved":
        return record.label
    return curated.label


def redacted_arguments(value: Any, replacements: Mapping[str, str]) -> Any:
    """One argument value with every personal-data string inside it replaced, at any depth.

    An argument may itself be an object or an array -- the same reason δ compares them through
    canonical JSON -- so a scan that only looked at the top level would rewrite
    `{"ma_khach": "480215"}` and miss `{"khach": {"ma": "480215"}}`, which is the shape a tool with a
    nested parameter schema declares.
    """
    if isinstance(value, str):
        return redacted_text(value, replacements)
    if isinstance(value, Mapping):
        return {
            key: redacted_arguments(item, replacements) for key, item in value.items()
        }
    if isinstance(value, list):
        return [redacted_arguments(item, replacements) for item in value]
    return value


def redact_label(label: StoredAnswer, replacements: Mapping[str, str]) -> StoredAnswer:
    """The label with every value `pii_check` replaced in the content replaced too.

    Requirement 17, and the half of it that is this profile's: the stage owns the content and knows
    nothing about what an answer is, so the shape of the label is read here. Redacting one and not
    the other is worse than redacting neither -- it manufactures a `label_assistant_mismatch` on the
    next run, and `export` emits a training example whose input reads `<CUSTOMER_ID_1>` and whose
    target reads the original, teaching a model to produce an identifier absent from its input.

    **The tool's name is never rewritten and everything else is.** A name is the catalog's, not the
    customer's; rewriting one would invent a tool no record offers and fire `label_not_in_catalog` --
    the same class of defect this exists to prevent, one stage later. A bare-name entry is returned
    untouched for that reason, and a key this profile does not write is rewritten rather than trusted,
    because a value carrying personal data is personal data wherever the source put it.
    """
    return tuple(
        entry
        if isinstance(entry, str)
        else {
            key: value if key == NAME else redacted_arguments(value, replacements)
            for key, value in entry.items()
        }
        for entry in label
    )


def restated_answer(record: Record, role: str) -> StoredAnswer | None:
    """The answer as this record's own final turn states it, or None if it does not.

    The **final** part, and only that one. An earlier target-role turn is history -- a tool called
    before the customer supplied what was missing, and then called again on the result -- so
    comparing the label against the last one *of that role* reports a mismatch on every multi-turn
    record; a fixture caught exactly that. Where the conversation ends with the customer, the label
    answers that turn and nothing restates it, which is the declared shape's ordinary case. Prose is
    not a restatement either.

    **The calls are the segment after the last `record.SPOKEN_AND_STATED`**, because a turn that both
    speaks and acts is written down as both and this check went silent on exactly those turns until a
    review found it -- a `data_quality` check reading 0 on the common shape is worse than no check,
    since Requirement 22 compares its count against `params.invalid_counts` and a zero reads as
    health. The separator is the record's constant rather than a copy of the modality's, and a
    crossing test builds the turn through `text2text` and reads it here, so neither end can move
    alone. Splitting on it costs nothing where there is no separator: `rsplit` returns the whole
    text, which is what a calls-only turn carries.
    """
    if not record.content or record.content[-1].role != role:
        return None
    tail = (record.content[-1].text or "").rsplit(SPOKEN_AND_STATED, 1)[-1]
    try:
        stated = json.loads(tail)
    except json.JSONDecodeError:
        return None
    return tuple(stated) if isinstance(stated, list) else None


def typed_arguments(written: Sequence[Any]) -> dict[str, Any] | None:
    """The arguments an annotator typed, keyed by tool name, or None if any of it is malformed.

    A `textarea` value is a list because `maxSubmissions` permits more than one, so every entry is
    read and later entries win. Malformed is never coerced (Requirement 49): a human's malformed
    answer is evidence about the question, and half-parsing it would put a value nobody typed into a
    shipped label.
    """
    keyed: dict[str, Any] = {}
    for entry in written:
        if not isinstance(entry, str):
            return None
        try:
            read = json.loads(entry)
        except json.JSONDecodeError:
            return None
        if not isinstance(read, Mapping):
            return None
        keyed.update(read)
    return keyed


def control_values(
    result: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    """One annotation's controls, by the name the config gave each.

    By name and not by position, because a control the annotator never touched is absent from the
    list rather than present and empty -- there are no positions to read. An entry that is not a
    mapping, or whose `value` is not one, is not a control and is left out rather than raising: this
    is what a person's tool sent, and Requirement 43 gives it no channel to stop a run through.
    """
    return {
        str(entry[FROM_NAME]): value
        for entry in result
        if isinstance(entry, Mapping) and FROM_NAME in entry
        for value in [entry.get(VALUE)]
        if isinstance(value, Mapping)
    }


def corrected_answer(
    answered: Mapping[str, Mapping[str, Any]], record: Record, max_calls: int
) -> StoredAnswer | None:
    """The correction those controls carry, or None where it is not an answer this record permits.

    `None` for every way it can fail -- a control absent, a `textarea` that is a string, arguments
    that are not JSON, a name outside the catalog -- because the record has one place to put a
    correction and a half-parsed one is a value nobody typed (Requirement 49).
    """
    names = answered.get(CORRECTED_NAMES, {}).get(CHOICES)
    written = answered.get(CORRECTED_ARGUMENTS, {}).get(TEXT, [])
    if not isinstance(names, list) or not isinstance(written, list):
        return None
    arguments = typed_arguments(written)
    if arguments is None:
        return None
    answer = tuple(
        {NAME: str(name), ARGUMENTS: arguments.get(str(name)) or {}} for name in names
    )
    return answer if answer_is_permitted(record, answer, max_calls) else None


def one_written_line(written: Any) -> str | None:
    """The one thing a `textarea` holds, or None where it holds nothing.

    A `textarea` value is a list because `maxSubmissions` permits more than one; a note is one
    piece of free text, so the first entry is it. Never parsed and never joined -- what a person
    typed reaches the record as what they typed.
    """
    if not isinstance(written, list) or not written:
        return None
    return str(written[0])


@final
class ToolDecision(Text2Text):
    """Tool selection over Vietnamese call-centre text: one module inside `text2text`.

    Everything a stage knows about this task comes from here: what an answer is, how two of them
    differ, what makes one invalid, what a person is asked and what comes back. None of it is
    assigned in this class body (I5) -- identity, the source's vocabulary and the answer's ceiling
    are the manifest's, and the question is a policy file's.

    **The containment is the base class, and that is what T52 bought.** § *The two axes* has always
    said a modality is a concept and a profile is one module inside it; until T52 that was
    `modality: text2text` in a manifest and two unrelated objects at runtime, and a reader of the
    classes alone could not see the relationship at all. It is `class ToolDecision(Text2Text)` now,
    so the four modality members arrive by inheritance rather than by a second implementation, and
    `summarize` beside this one would share them without redeclaring one.

    **Two manifests, because there are two declarations and they are not interchangeable.**
    `config/modalities/text2text.yaml` says how content is read; `config/profiles/tool_decision.yaml`
    says what an answer to it is. One object holds both identities under prefixed names -- the base
    writes `modality_name`, this writes `profile_name` -- which is what keeps
    `Branch(modality=…, profile=…)` able to say which concept read a record and which module answered
    it. The pair itself is still checked at composition (`edge/bootstrap.py`), because a request body
    full of declarations may name a pair no class hierarchy was consulted about.
    """

    def __init__(
        self,
        modality: Manifest,
        manifest: Manifest,
        encode: Encoder,
        question_template: str,
    ) -> None:
        super().__init__(modality, encode)
        shape = declaration(manifest, SHAPE)
        if shape not in SHAPES:
            raise ConfigError(
                f"config/profiles/{manifest.name}.yaml declares shape {shape!r}, "
                f"which is not one of {list(SHAPES)}"
            )
        # `answer_control` is read to be refused and not to be stored: `CAPTURE_TAGS` implements
        # exactly one surface, and a manifest naming another must fail at composition rather than
        # emit tags that collect something else. What a measured agreement figure was measured on is
        # stamped by the manifest itself (§ *Configuration*), not carried onward from here.
        control = declaration(manifest, ANSWER_CONTROL)
        if control not in CONTROLS:
            raise ConfigError(
                f"config/profiles/{manifest.name}.yaml declares answer_control "
                f"{control!r}, which is not one of {list(CONTROLS)}"
            )
        if "{{" in question_template:
            raise ConfigError(
                f"the question template for {manifest.name} names a slot this profile "
                "cannot fill; one question is asked per record and nothing else goes in it"
            )
        self.profile_name = manifest.name
        self.profile_version = manifest.version
        self._max_calls = declared_count(manifest, MAX_CALLS)
        self._label_at = declared_text(manifest, LABEL, AT)
        self._target_role = one_role(manifest, TARGET)
        self._question = question_template.strip()

    def answer_schema(self, record: Record) -> dict[str, Any]:
        """This record's permitted answers: `oneOf` per offered tool. Never persisted."""
        return answer_schema(record, self._max_calls)

    def answer_config(self, record: Record) -> AnswerConfig:
        """The capture half: the fragment that collects an answer, and the task data it owns.

        The tool names are objects and not strings -- `{"value": "SendStatement"}` -- because that
        is what a dynamic choice list reads, and it is the kind of detail a parser written from
        memory gets wrong. In the catalog's own order, which is the order the record was answered
        under and the order `scenario_hash` is taken over.
        """
        return AnswerConfig(
            verdicts=VERDICTS,
            tags=CAPTURE_TAGS,
            data={TOOL_NAMES: [{VALUE: tool.name} for tool in catalog_of(record)]},
            endorsing_verdict=CORRECT,
        )

    def build_record(
        self, item: Mapping[str, Any], parts: Sequence[Part], provenance: Provenance
    ) -> Record:
        """One source item into one record. The only place a source shape is *validated*.

        § *Profile* used to say *read* and that was not quite true: `content_parts` reads the item's
        `messages` too, because turns are content. What is exclusive is the validation -- `shape:`
        is checked here and nowhere else -- and every key other than `messages`.

        `meta` keeps every key the source presented (Requirement 9), the label included: nothing
        writes to `meta`, so the copy cannot go stale, and `training_example` puts the record back
        into the shape it arrived in. What `load_data` knows and this does not -- the file's digest,
        the offset, the clock, the run -- is the third argument, already validated by being a
        `Provenance` at all.
        """
        carried = item.get(META)
        source_meta = dict(carried) if isinstance(carried, Mapping) else {}
        if self._label_at not in source_meta:
            raise ConfigError(
                f"config/profiles/{self.profile_name}.yaml declares the answer at "
                f"{META}.{self._label_at}; the item at offset {provenance.offset} "
                f"carries {sorted(source_meta)}"
            )
        return Record(
            record_id=record_id_for(parts),
            source_id=str(item.get(ID) or provenance.offset),
            branch=Branch(modality=self.modality_name, profile=self.profile_name),
            provenance=provenance,
            content=tuple(parts),
            label=entries_in(source_meta[self._label_at]),
            meta={
                **{
                    key: value
                    for key, value in item.items()
                    if key not in (MESSAGES, META)
                },
                **source_meta,
            },
        )

    def label_checks(self) -> list[LabelCheck]:
        """The checks that need no opinion, each named for the defect it finds."""

        def label_assistant_mismatch(record: Record) -> bool:
            """The label and the turn that restates it disagree.

            A record whose two statements of the answer differ would train a model on the losing
            side of two disagreeing sources. Where nothing restates the label there is no
            disagreement to find, which is the declared shape's ordinary case and is why this reads
            0 until it does not.
            """
            restated = restated_answer(record, self._target_role)
            return (
                restated is not None and answer_distance(restated, record.label) != 0.0
            )

        def label_not_in_catalog(record: Record) -> bool:
            """The label names a tool this record never offered -- unlearnable, and it teaches
            hallucination. Never truncated to the catalog: that would be a guess about which of two
            disagreeing sources is right, applied invisibly at scale."""
            offered = {tool.name for tool in catalog_of(record)}
            return any(call.name not in offered for call in calls_in(record.label))

        def empty_catalog(record: Record) -> bool:
            """There was nothing to choose from. A quarantine for triage, not a verdict."""
            return not catalog_of(record)

        def label_cardinality_anomaly(record: Record) -> bool:
            """The label names more tools than this profile permits."""
            return len(record.label) > self._max_calls

        def label_names_one_tool_twice(record: Record) -> bool:
            """A target of `["X", "X"]` trains a model to call X twice, and makes the answer a
            multiset -- which would force δ to pairwise-match two calls to one tool and silently
            pick a pairing no source proposed."""
            named = [call.name for call in calls_in(record.label)]
            return len(set(named)) != len(named)

        return [
            LabelCheck("label_assistant_mismatch", label_assistant_mismatch),
            LabelCheck("label_not_in_catalog", label_not_in_catalog),
            LabelCheck("empty_catalog", empty_catalog),
            LabelCheck("label_cardinality_anomaly", label_cardinality_anomaly),
            LabelCheck("label_names_one_tool_twice", label_names_one_tool_twice),
        ]

    def redact_label(
        self, label: StoredAnswer, replacements: Mapping[str, str]
    ) -> StoredAnswer:
        """The label with every value `pii_check` replaced in the content replaced too."""
        return redact_label(label, replacements)

    def answer_distance(self, a: StoredAnswer, b: StoredAnswer) -> float:
        """δ: 0.0 identical, 1.0 unrelated. Name-first, soft over arguments. `δ(∅, ∅) = 0`."""
        return answer_distance(a, b)

    def answer_is_permitted(self, answer: StoredAnswer, record: Record) -> bool:
        """Does this answer belong to this record's answer space: the schema, and what it
        cannot say. The ceiling is this profile's, which is why the free function takes it and
        the member does not -- a caller counting a jury's invalid votes has no business knowing
        it."""
        return answer_is_permitted(record, answer, self._max_calls)

    def vote_consensus(
        self, votes: Sequence[StoredAnswer], record: Record
    ) -> StoredAnswer | None:
        """The panel's answer; `()` where it agreed on none; None where none is defensible."""
        return vote_consensus(votes, record, self._max_calls)

    def question_text(self, record: Record) -> str:
        """What an annotator is asked, in their language. No model output may appear in it.

        The record picks no words: one question is asked per record and the record's own specifics
        reach the annotator as task data -- the conversation from the modality's display half, the
        catalog as the dynamic choice list. Prompt text in code is a prompt change no run manifest
        records (Requirement 51), so this is a policy file the edge read.
        """
        return self._question

    def annotation_response(
        self, result: Sequence[Mapping[str, Any]], record: Record
    ) -> AnnotationResponse:
        """What one annotation said: its verdict, its correction where it validates, its note.

        The only place an annotation tool's shape is read (Requirement 49), the way `build_record`
        is the only place a source shape is read. It answers for all three controls the capture
        half emits, because a caller reading one of them itself would be a second place that knew
        this shape -- and the caller is a pipeline stage, which may not know it at all.

        A verdict outside `VERDICTS` is no verdict: the control offers three values and anything
        else came from a config this profile did not compose. A correction is read only where the
        verdict says the label is wrong, and one that does not validate against this record's own
        `answer_schema` is `None` and never coerced.
        """
        answered = control_values(result)
        chosen = answered.get(VERDICT, {}).get(CHOICES)
        verdict = chosen[0] if isinstance(chosen, list) and chosen else None
        return AnnotationResponse(
            verdict=str(verdict) if verdict in VERDICTS else None,
            corrected_value=corrected_answer(answered, record, self._max_calls)
            if verdict == INCORRECT
            else None,
            note=one_written_line(answered.get(NOTE, {}).get(TEXT)),
        )

    def jury_slots(self, record: Record) -> Mapping[str, Any]:
        """What the jury prompt's slots are filled with. The template is policy's, not this."""
        return {
            # The turns as a juror reads them, and the catalog with each tool's arguments named.
            "conversation": "\n".join(
                f"{part.role}: {part.text or ''}" for part in record.content
            ),
            "catalog": "\n".join(
                f"- {tool.name}({', '.join(sorted(tool.parameters.get(PROPERTIES) or {}))})"
                f"{': ' + tool.description if tool.description else ''}"
                for tool in catalog_of(record)
            ),
            "label": canonical_json(list(record.label)),
        }

    def scenario_hash(self, record: Record) -> str:
        """What must not straddle a split -- two records of one scenario share it.

        The catalog it was offered, in order, because the catalog is presented in order and two
        orderings are two prompts. Never the offset: that is unique per record and so gives no
        leakage protection at all.
        """
        names = "|".join(tool.name for tool in catalog_of(record))
        return compute_hash(names)[:SCENARIO_LENGTH]

    def training_example(self, record: Record) -> Mapping[str, Any]:
        """The record in the shape a trainer expects.

        The shape it arrived in, which makes an export re-readable by the same loader: `messages`,
        `tools`, and the answer back under the key the manifest declares. The answer is the curated
        one where review reached a decision -- `curate` writes what ships -- and the record's own
        otherwise.
        """
        carried = dict(record.meta)
        carried.pop(ID, None)
        tools = carried.pop(TOOLS, [])
        carried[self._label_at] = list(final_label(record))
        return {
            ID: record.source_id,
            MESSAGES: [
                {"role": part.role, "content": part.text or ""}
                for part in record.content
            ],
            TOOLS: tools,
            META: carried,
        }


if TYPE_CHECKING:

    def _answers_its_protocol(
        modality: Manifest, manifest: Manifest, encode: Encoder, question: str
    ) -> "Profile":
        """`mypy --strict` checks this return, so a member that stops matching fails the build.

        The same check `text2text/utils.py` carries, and for the same reason: mypy reads `src/`
        alone, and `edge/bootstrap.py` types the pair only as far as the protocols do.
        """
        return ToolDecision(modality, manifest, encode, question)

    def _is_also_its_concept(
        modality: Manifest, manifest: Manifest, encode: Encoder, question: str
    ) -> "Modality":
        """The other half of the containment, checked the same way.

        One object answers both protocols, and this is what says so to mypy rather than to a reader.
        A `Text2Text` member renamed out from under this class fails here rather than at the first
        record `duplicate_check` tries to embed.
        """
        return ToolDecision(modality, manifest, encode, question)
