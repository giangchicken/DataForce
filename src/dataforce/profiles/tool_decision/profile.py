"""LOGIC · ToolDecision -- the object that answers the Profile protocol.

**The implementation is here and not in ``__init__.py``**, which is a ``façade ·`` that holds nothing
of its own (Requirement 2). Every one of the fifteen members is a conversion over the shapes in
``schema.py``, and each is assembled from the module that owns it: the answer space and δ from
``answers.py``, what one annotation said from ``annotations.py``, the label a record carries from
``records.py``, and what the manifest declares through ``dataforce/declarations.py``.

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
``ConfigError`` only *before any record is read*, so the rule is broken here on purpose --
``load_data`` is the only caller, it is the only thing that knows the offset, and T14 settled it
there: the raise is caught, counted against the item's offset and handed to the edge as side output,
so a run still completes. ``modalities/text2text/modality.py`` carries the same note for its own two.

A second raise stood here until T14 and is gone rather than caught: provenance arrived under a
magic ``__provenance__`` key on the item and was validated on the way in, which is connascence of
meaning between a stage and one axis. It is a parameter now, so *an item with no provenance*
is unrepresentable and mypy checks what a message used to explain.
"""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, final

from agent_toolkit.string_utils import compute_hash

from dataforce.declarations import declaration, declared_count, declared_name
from dataforce.errors import ConfigError
from dataforce.manifest import Manifest
from dataforce.modalities.text2text import Encoder, Text2Text
from dataforce.profiles.base import AnnotationResponse
from dataforce.profiles.tool_decision.annotations import (
    CHOICES,
    NOTE,
    TEXT,
    VALUE,
    VERDICT,
    control_values,
    corrected_answer,
    one_written_line,
)
from dataforce.profiles.tool_decision.answers import (
    PROPERTIES,
    TOOLS,
    answer_distance,
    answer_is_permitted,
    answer_schema,
    calls_in,
    catalog_of,
    entries_in,
    vote_consensus,
)
from dataforce.profiles.tool_decision.records import (
    final_label,
    part_with_calls,
    redact_label,
    restated_answer,
)
from dataforce.profiles.tool_decision.schema import AnswerConfig, LabelCheck
from dataforce.record import (
    Branch,
    Part,
    Provenance,
    Record,
    StoredAnswer,
    canonical_json,
    record_id_for,
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
MESSAGES = "messages"

# The payload key the capture half owns, read by `$tool_names` in the fragment above it.
TOOL_NAMES = "tool_names"
# The verdict that says the label is wrong, and the three a person may choose between.
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
        self._label_at = declared_name(manifest, LABEL, AT)
        self._target_role = one_role(manifest, TARGET)
        self._question = question_template.strip()

    def _turn_part(self, turn: Mapping[str, Any]) -> Part:
        """The concept's turn, with what this task's turns also *do* written onto it.

        The one seam `Text2Text` leaves for a module in its family (Decision 24). The concept reads a
        role and a `content`; `tool_calls` is what *this* task answers with, so the profile that
        declares what a call is is the profile that writes one onto a part and reads it back off --
        and the separator between the two is `records.py`'s constant rather than a convention held in
        a module both axes import. § *The two axes* is the argument: a concept may not hold a
        convention only one of its modules speaks.

        Private for I23's reason: an implementation's public surface is exactly its protocol's
        members, and a seam a subclass overrides is not one of them.
        """
        return part_with_calls(super()._turn_part(turn), turn)

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

        The same check `text2text/modality.py` carries, and for the same reason: mypy reads `src/`
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
