"""DEFINITION · Record, and Part -- the bus, and the content it carries.

Every stage reads records and returns records. A part belongs to neither axis -- it is a piece of
record content, and both protocols take a sequence of them -- so it lives here, where both can
reach it (Requirement 47).

**Every model here is frozen and every sequence is a tuple**, so a stage cannot edit the record it
was handed: it returns a copy carrying one key more. That is what Requirement 41's ``output ==
input`` *structurally* buys before there is a second stage to assert against. The guarantee stops
at the record's own shape: ``meta``, ``label`` and the resolved configs are free-form JSON the
source or the edge owns, and a dict inside one of them is still a dict.

**``record_id`` is a field and not a validator over ``content``.** ``pii_check`` rewrites
``content`` and bumps ``content_version``, so an id derived on every construction would change
under redaction and take every join in the corpus with it. It is computed once, at load, by
``record_id_for``, which lives here because what an id is made of is part of what a record is
(Requirements 6-8).

**``SPOKEN_AND_STATED`` is the fourth name both axes borrow, and it is here for ``Part``'s reason.**
A turn can both speak and act -- ``"Mình tra cứu ngay nhé."`` plus a ``tool_calls`` entry -- and a
part carries one string, so a modality writing that turn down has to join the two and a profile
comparing the calls against the label has to find them again. § *The two axes* says the contracts
share ``name``, ``version`` and ``Part`` *and nothing else*; that sentence was already false, because
the separator was a convention spelled in one axis and assumed in the other, which is the worst
version of a shared fact. It is the same kind of fact as ``Part``: how a piece of record content is
written down. So it lives here, where both can reach it, and one test crosses the seam so neither
end can move alone.

**``redacted_text`` is here for the same reason as the separator, and it is the sharper case.**
Requirement 17 says ``pii_check`` rewrites ``content`` **and** the label together, under the same
placeholder -- the stage owns the content and the profile's ``redact_label`` owns the label, and the
two may not import each other. If they applied the replacements in different orders they would
disagree: with ``{"480215": "<A_1>", "0215": "<B_1>"}`` a longest-first pass writes ``<A_1>`` and a
shortest-first pass writes ``48<B_1>``, which manufactures exactly the ``label_assistant_mismatch``
Requirement 17 exists to prevent. So *how* a value becomes its placeholder is one function here,
called by both ends, rather than an algorithm spelled twice and agreed by luck (P13, P16).

**A key's model is named for what the key holds, never for the stage that writes it.** ``§5``: a
name shared with a stage makes every sentence about the code ambiguous, and ``LabelCheck`` is
already the profile's word for one of the five checks (Requirement 47). So what
``data_quality.label_check`` holds is a ``LabelVerdict``, and the two never collide in one import.
"""

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal, Self

from agent_toolkit.string_utils import compute_hash
from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecordModel(BaseModel):
    """What every piece of the record has in common: frozen, and an unknown key is an error.

    ``extra="forbid"`` is what makes I10 structural. ``Record(answer_space=[...])`` raises rather
    than quietly carrying a second copy of the catalog -- and a stored space is a copy that can
    disagree with `answer_schema`, which materialises one from the record when asked.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


# Which kind of turn a part is. The four are the vocabulary modality names are built from --
# `text2text`, `speech2text` -- and are not themselves registrable (spec.md § *The two axes*).
PartType = Literal["text", "audio", "image", "video"]

# An answer as the record stores it: one entry per call. What is inside a call is the profile's
# (Requirement 47); the record knows only that an answer is a list of them, and that the empty
# answer -- call nothing -- is a member of the type rather than a missing value.
#
# A bare name string is an entry too, because it *reads as the call with no arguments* (spec.md
# § *The answer*) -- which is what makes a names-only source a special case of this type rather
# than a second type, and what lets a label stay verbatim instead of being normalised at load.
# Nothing the pipeline produces spells one: a jury answers the materialised schema and an
# annotator answers a form, and both of those are objects.
StoredAnswer = tuple[dict[str, Any] | str, ...]


# What separates what a turn said from the calls it made, inside one part's text. Borrowed by both
# axes: `text2text` joins on it, `tool_decision` reads the calls back off it. A turn that only
# speaks or only calls carries no separator at all.
SPOKEN_AND_STATED = "\n"


class Part(RecordModel):
    """One turn of the conversation: text verbatim, media by reference."""

    type: PartType = Field(
        ...,
        description=(
            "Which kind of turn this is: a text part carries `text`, a media part "
            "carries `uri` and `sha256`."
        ),
    )
    role: str = Field(
        ...,
        description=(
            "Who spoke, in the source's own vocabulary. Every turn is context and "
            "none of it is an answer."
        ),
    )
    text: str | None = Field(
        default=None,
        description="The turn's text, verbatim. Set on a text part and on no other.",
    )
    uri: str | None = Field(
        default=None,
        description=(
            "Where the media sits. Never part of `record_id`: moving a file does not "
            "change an id."
        ),
    )
    sha256: str | None = Field(
        default=None,
        description=(
            "The media's content digest. This is what `record_id` covers, never the bytes."
        ),
    )

    @model_validator(mode="after")
    def _carries_what_its_type_declares(self) -> Self:
        """A part hashes through the fields its type names, so a missing one is a silent collision.

        A media part with no `sha256` contributes nothing to `record_id` but its type and role,
        which every other such part also contributes -- two different recordings would share an
        id. Requiring the field is cheaper than detecting the collision downstream (P22).
        """
        needed = ("text",) if self.type == "text" else ("uri", "sha256")
        carried = tuple(
            field
            for field in ("text", "uri", "sha256")
            if getattr(self, field) is not None
        )
        if carried != needed:
            raise ValueError(
                f"a {self.type} part carries {', '.join(needed)}, "
                f"not {', '.join(carried) or 'nothing'}"
            )
        return self


def record_id_for(content: Sequence[Part]) -> str:
    """The 16 lowercase hex a record with this content is joined on (Requirement 6).

    *Canonical* is about the serialisation -- the parts in order, keys sorted, no incidental
    whitespace -- and not about the text: two turns differing by one space are two records, and
    grouping the near-duplicates is `duplicate_check`'s job rather than this function's. Order
    within a record is content (Requirement 7); position in the source file is not, so a shuffled
    re-ingest produces the same set of ids (I9). The three options below are written twice more, as
    `canonical_json` in each axis, and I24 holds the copies to one form -- flipping `ensure_ascii`
    in any one of them re-keys every Vietnamese record there is, and I9 would not notice.

    Two records whose content is identical therefore share an id, which is the design's own
    consequence: `duplicate_check` reports such a pair rather than the id pretending they differ.
    """
    canonical = json.dumps(
        [
            {"type": part.type, "role": part.role, "text": part.text}
            if part.type == "text"
            # Requirement 8: a media part contributes its digest, never its bytes and never its
            # `uri` -- moving a file does not change an id; changing its content does.
            else {"type": part.type, "role": part.role, "sha256": part.sha256}
            for part in content
        ],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return compute_hash(canonical)[:16]


def redacted_text(text: str, replacements: Mapping[str, str]) -> str:
    """One string with every personal-data value replaced by its placeholder, longest first.

    Longest first is the load-bearing half: where one value contains another -- `0215` inside
    `480215` -- replacing the shorter one first leaves `48<PHONE_1>`, and the same text redacted by
    `content` and by `label` in different orders is two strings that no longer match. One function,
    both callers, no order to agree on.

    A value that is no longer in the text is not an error: `pii_check` replaces by value rather than
    by offset, so a hit inside a longer hit is already gone by the time its own turn comes.
    """
    for value in sorted(replacements, key=len, reverse=True):
        text = text.replace(value, replacements[value])
    return text


class Branch(RecordModel):
    """The pair this record was read and answered under."""

    modality: str = Field(
        ..., description="Which modality read this record's content, by name."
    )
    profile: str = Field(
        ..., description="Which profile defines what an answer to it is, by name."
    )


class Provenance(RecordModel):
    """What made this record, travelling with it (Requirement 12, Decision 4)."""

    source_file_sha256: str = Field(
        ...,
        description="Which file this came out of, by content rather than by name.",
    )
    offset: int = Field(
        ...,
        description="Its position in that file, so one item can be re-read on its own.",
    )
    ingested_at: datetime = Field(
        ...,
        description="When `load_data` ran. The edge supplies it; the engine has no clock.",
    )
    modality: str = Field(
        ...,
        description=(
            "The stamped modality version, `name@version`, so a bump is visible per record."
        ),
    )
    profile: str = Field(
        ...,
        description="The stamped profile version, `name@version`, for the same reason.",
    )
    run_id: str = Field(
        ...,
        description="Joins this record to the manifest of the run that produced it.",
    )


# --- data_quality ---


class LabelVerdict(RecordModel):
    """What the five checks that need no opinion found. `data_quality.label_check` holds one."""

    passed: bool = Field(..., description="Did every check on the label hold.")
    failed_checks: tuple[str, ...] = Field(
        default=(),
        description=(
            "Which named checks did not. Read by whoever reads the quarantine tier: "
            "`triage` never sees a quarantined record, because it has no jury."
        ),
    )
    quarantined: bool = Field(
        ...,
        description=(
            "Downstream services skip this record; it is marked, never removed "
            "(Requirement 41)."
        ),
    )


class PersonalDataSpan(RecordModel):
    """One hit: where it is, what it is, and what replaced it."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    part: int = Field(
        ..., description="Index into `content` of the part the hit is in."
    )
    start: int = Field(..., description="Character offset of the hit, inclusive.")
    end: int = Field(..., description="Character offset of the hit's end, exclusive.")
    # `class` is a keyword, so the field is named for what it is and aliased to the key the
    # record is written with. The alias is on both sides: a record reads and writes `class`.
    personal_data_class: str = Field(
        ...,
        alias="class",
        description="The typed class of the hit, which is what picks the placeholder.",
    )
    verified: bool = Field(
        ..., description="Did layer two confirm layer one's hit, or only flag it."
    )
    placeholder: str = Field(
        ...,
        description="What stands in the text instead; the same value gets the same one.",
    )


class PersonalDataScan(RecordModel):
    """What the two layers found and what was done about it. `data_quality.pii_check` holds one."""

    decision: Literal["redacted", "reported", "withheld"] = Field(
        ...,
        description=(
            "What happened to the content. `redacted`: rewritten, and every hit was "
            "confirmed -- which is also a record with no hits at all, since `export`'s "
            "precondition reads this. `reported`: left alone under "
            "`enable_redact: false`. `withheld`: rewritten as far as layer two "
            "confirmed, and held out of a release because something was not."
        ),
    )
    content_version_scanned: int = Field(
        ..., description="Which `content` the spans below index into."
    )
    spans: tuple[PersonalDataSpan, ...] = Field(
        default=(), description="Every hit, in the order the scan found it."
    )
    classes: tuple[str, ...] = Field(
        default=(),
        description="The distinct classes found, for the corpus-level report.",
    )
    unverified: int = Field(
        ...,
        description=(
            "Hits layer two could not confirm. `export`'s precondition reads this number."
        ),
    )


class DuplicateGroups(RecordModel):
    """Which records this one repeats, split by whether they agree on the answer."""

    duplicate_content_same_label: tuple[str, ...] = Field(
        default=(),
        description=(
            "`record_id`s with this content and this label: safe to drop one of them."
        ),
    )
    duplicate_content_diff_label: tuple[str, ...] = Field(
        default=(),
        description=(
            "`record_id`s with this content and a different label: one of them is wrong."
        ),
    )


class DataQuality(RecordModel):
    """The `data_quality` phase's key: its resolved config, and one key per stage that ran."""

    data_quality_config: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "The resolved config and its digest. Written by the edge, read by the "
            "services (Decision 5)."
        ),
    )
    label_check: LabelVerdict | None = Field(
        default=None, description="What `label_check` wrote; absent until it has run."
    )
    pii_check: PersonalDataScan | None = Field(
        default=None, description="What `pii_check` wrote; absent until it has run."
    )
    duplicate_check: DuplicateGroups | None = Field(
        default=None,
        description="What `duplicate_check` wrote; absent until it has run.",
    )


# --- ai_review ---


class JurorVote(RecordModel):
    """One model's answer to the record's own task, and whether it was usable."""

    model_name: str = Field(..., description="Which juror produced this vote.")
    label_is_right: bool = Field(
        ..., description="Its verdict on the label the record already carries."
    )
    answer: StoredAnswer = Field(
        default=(), description="Its own answer, in the profile's answer shape."
    )
    reasoning: str = Field(
        ..., description="Why, for the human who reads a disagreement."
    )
    valid: bool = Field(
        ...,
        description=(
            "Is its answer in this record's answer space. An invalid vote is kept "
            "and counted, never dropped."
        ),
    )


class PanelVerdict(RecordModel):
    """What the panel said, and under which composition. `ai_review.jury` holds one."""

    panel_version: int = Field(
        ..., description="Which panel composition produced these votes."
    )
    prompt_version: str = Field(
        ..., description="Which prompt; a change to it invalidates comparison."
    )
    llm_votes: tuple[JurorVote, ...] = Field(
        default=(), description="One entry per juror that answered."
    )
    invalid_votes: int = Field(
        default=0,
        description="How many votes did not validate; a noisy panel is visible here.",
    )
    plurality: StoredAnswer = Field(
        default=(), description="The panel's most-common answer."
    )
    final_prediction: StoredAnswer | None = Field(
        default=None,
        description=(
            "What the panel is taken to have said; `[]` is *agreed to call nothing* "
            "and null is *nothing defensible*."
        ),
    )


class AgreementScores(RecordModel):
    """How much the jury agrees, with itself and with the label. `ai_review.cohesion` holds one."""

    self_agreement: float = Field(
        ..., description="How much the jurors agree with each other."
    )
    label_agreement: float = Field(
        ..., description="How much they agree with the label the record carries."
    )
    method: str = Field(
        ...,
        description="The estimator over δ, so two runs' pairs are comparable.",
    )


class ReviewSelection(RecordModel):
    """Where the two numbers put this record, and whether a person sees it."""

    bucket: str = Field(
        ..., description="Which cell of the two agreement numbers this record falls in."
    )
    stratum: str = Field(..., description="The sampling group that bucket belongs to.")
    selected_for_review: bool = Field(..., description="Does a human see this record.")
    reason: str = Field(
        ..., description="Which rule selected it, so a quota can be audited."
    )


class AiReview(RecordModel):
    """The `ai_review` phase's key: its resolved config, and one key per stage that ran."""

    ai_review_config: dict[str, Any] = Field(
        default_factory=dict,
        description="The resolved panel config and its digest. Written by the edge.",
    )
    jury: PanelVerdict | None = Field(
        default=None, description="What `jury` wrote; absent until it has run."
    )
    cohesion: AgreementScores | None = Field(
        default=None, description="What `cohesion` wrote; absent until it has run."
    )
    triage: ReviewSelection | None = Field(
        default=None, description="What `triage` wrote; absent until it has run."
    )


# --- human_review ---


class Question(RecordModel):
    """One answerable question about this record. `human_review.question_generate` holds a list."""

    question_id: str = Field(
        ..., description="Stable id; the join key to the store and to the answers."
    )
    question_name: str = Field(
        ..., description="The short label an annotator sees beside it."
    )
    content: str = Field(
        ...,
        description="The question itself, in the annotator's language. No model output.",
    )
    enum: tuple[str, ...] = Field(
        default=(),
        description="The permitted answers. Free text is not one of them.",
    )


class PublishedQuestions(RecordModel):
    """Which questions reached the store, and under which run. `human_review.publish` holds one."""

    stored: tuple[str, ...] = Field(
        default=(), description="The `question_id`s written to the question store."
    )
    store_run_id: str = Field(
        ...,
        description="Which publish run wrote them, which is what makes a re-run idempotent.",
    )
    published_at: datetime = Field(
        ..., description="When they were written. The edge supplies the clock."
    )


class AnnotatorResponse(RecordModel):
    """One person's answer to one question."""

    annotator_id: str = Field(..., description="Who answered.")
    question_id: str = Field(
        ..., description="Which question, joined back to `question_generate`."
    )
    verdict: str = Field(
        ...,
        description=(
            "One of that question's `enum` values. The record does not name them: "
            "the permitted answers are the profile's capture half (Decision 22)."
        ),
    )
    corrected_value: StoredAnswer | None = Field(
        default=None,
        description=(
            "The corrected answer, required where the verdict is `incorrect` and "
            "null everywhere else."
        ),
    )
    note: str | None = Field(
        default=None, description="Free text from the annotator; never parsed."
    )
    submitted_at: datetime = Field(..., description="When they submitted it.")


class ReturnedAnswers(RecordModel):
    """What came back out of the store. `human_review.annotator_answers` holds one."""

    responses: tuple[AnnotatorResponse, ...] = Field(
        default=(),
        description="One entry per answer read back, in no particular order.",
    )


class OverlapVerdict(RecordModel):
    """The one verdict the overlap agreed on. `human_review.aggregate` holds one."""

    verdict: str = Field(..., description="The verdict the overlap agreed on.")
    method: str = Field(
        ..., description="How it was reached, since more than one way is arguable."
    )
    confidence: float = Field(
        ..., description="How much to trust that verdict downstream."
    )
    overlap: int = Field(..., description="How many annotators saw this record.")
    alpha: float = Field(
        ...,
        description="Krippendorff's alpha for the incomplete-overlap design.",
    )


class FinalLabel(RecordModel):
    """The label that ships, and how it was decided. `human_review.curate` holds one."""

    status: Literal["original", "corrected", "unresolved"] = Field(
        ...,
        description="Whether the label survived review, was replaced, or is still open.",
    )
    label: StoredAnswer = Field(
        default=(), description="The final label. This is what ships."
    )
    validators: tuple[str, ...] = Field(default=(), description="Who produced it.")
    adjudicated_by: str | None = Field(
        default=None, description="Who broke a tie, where there was one."
    )
    decided_at: datetime = Field(..., description="When it was decided.")


class HumanReview(RecordModel):
    """The `human_review` phase's key: its resolved config, and one key per stage that ran."""

    human_config: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "The resolved annotator and question-generator config, and its digest. "
            "Written by the edge."
        ),
    )
    question_generate: tuple[Question, ...] | None = Field(
        default=None,
        description="What `question_generate` wrote; absent until it has run.",
    )
    publish: PublishedQuestions | None = Field(
        default=None, description="What `publish` wrote; absent until it has run."
    )
    annotator_answers: ReturnedAnswers | None = Field(
        default=None,
        description="What `annotator_answers` wrote; absent until it has run.",
    )
    aggregate: OverlapVerdict | None = Field(
        default=None, description="What `aggregate` wrote; absent until it has run."
    )
    curate: FinalLabel | None = Field(
        default=None, description="What `curate` wrote; absent until it has run."
    )


class Record(RecordModel):
    """The bus. Every stage reads one and returns one, exactly one key richer (Requirement 5)."""

    # --- Identity ---
    record_id: str = Field(
        ...,
        description=(
            "16 lowercase hex over the canonicalised content; the join key everywhere."
        ),
    )
    source_id: str = Field(
        ...,
        description=(
            "The id the source gave this item. For tracing back to it, never for joining."
        ),
    )
    branch: Branch = Field(
        ..., description="Which pair read this record's content and defines its answer."
    )

    # --- Provenance: what made this record, travelling with it ---
    provenance: Provenance = Field(
        ..., description="The file, the offset, the run and both axis versions."
    )

    # --- Content: the conversation, in order ---
    content: tuple[Part, ...] = Field(
        ...,
        description=(
            "The turns, in order. Order is content, so `record_id` covers it "
            "(Requirement 7)."
        ),
    )
    content_version: int = Field(
        default=1,
        description=(
            "Bumped only by `pii_check`; says which text a span offset points into."
        ),
    )

    # --- The answer, and everything else the source carried ---
    label: StoredAnswer = Field(
        ...,
        description=(
            "The training target and nothing else is. Required, because `[]` means "
            "*call nothing* and would hide a missing label as a default."
        ),
    )
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "The source's own keys, verbatim, including ones no code recognises "
            "(Requirement 9). Read only where a manifest declares them."
        ),
    )

    # --- What each phase wrote: one key per stage, and the config the edge resolved ---
    data_quality: DataQuality = Field(
        default_factory=DataQuality,
        description="The `data_quality` phase's three keys, as they are written.",
    )
    ai_review: AiReview = Field(
        default_factory=AiReview,
        description="The `ai_review` phase's three keys, as they are written.",
    )
    human_review: HumanReview = Field(
        default_factory=HumanReview,
        description="The `human_review` phase's five keys, as they are written.",
    )
    release: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Declared and not yet specified: `release` is in the flow and has no "
            "module, so its shape is not this document's to state yet."
        ),
    )
