"""STEP · question_generate · one answerable question per flagged record, with its evidence.

The first stage of the phase a person is in, and the only one in it that invents anything -- every
other stage moves a value between the record and the store. What it invents is one question and the
id that question is joined on for the rest of its life: through ``publish``, through the store's
three tables, and back through the annotation that answers it (Requirement 29).

**``triage`` is read for the decision and for nothing else** (Requirement 30, I12). That is
structural here rather than promised: ``needs_a_question`` returns a ``bool``, so the selection
never becomes a value in this module and no bucket, no vote and no agreement figure has a path into
a question. It is the one precondition in this phase that *should* be a predicate --
``votes_to_fold`` and ``scores_to_place`` hand their value on because their caller needs it, and
this caller must not have it.

**The evidence is the record's own content, and it does not travel inside the question.**
Requirement 29 says the question carries the evidence and the glossary. The conversation reaches the
annotator as task *data*, composed by ``publish`` out of the modality's display half; the glossary
is a written document rather than a field, and a precondition on *opening the engine* checked once
at composition. ``edge/bootstrap.py`` is still a docstring, so **nothing enforces the glossary
yet** -- T27 is where that check lands, and saying so is cheaper than implying it is there.

**The permitted answers are copied onto the record, and the copy is the point.** They are the
profile's capture half, read through ``answer_config(record).verdicts``, and an answer read a year
from now has to be legible against what was askable when it was asked -- a live reference would
re-read a question answered under three verdicts as one that offered four. The cost is two
statements of one tuple, and the record's is the one that stays right about the past. Reading a
*field* off a type this module may not import is the connascence ``label_check`` already carries on
``LabelCheck.name``, named here because the two ends sit far apart, rather than left to be noticed.

The call is per record and was hoisted out of the fold until T24, when the capture half gained the
task data it owns and therefore a record to read it from. The verdicts are the same tuple every
time; what moved is that the member answering for them now answers for a per-record thing too.

**The id covers the words, not only the record.** Idempotency downstream is a unique constraint on
``question_id`` (§ *The question store*), so an id that did not move when a question was reworded
would make the republish a no-op and the new wording would never reach a person -- the annotator
answers the old question and nothing anywhere says so. So the id is minted over the record, the
question's name, its words, and the answers it permits: change any of those and it is a different
question, which is what it then is.
"""

from collections.abc import Iterable, Sequence

from agent_toolkit.string_utils import compute_hash

from dataforce.engine import Engine, ServiceResult
from dataforce.record import Question, Record

# The key this stage owns, under `human_review`: one key, one writer.
STAGE = "question_generate"

# The one question this phase asks, under the name the panel's own vote already gives it
# (`JurorVote.label_is_right`): the jury and the annotator are asked the same question, and only the
# answerer differs. `Question.question_name` is drawn as *the short label an annotator sees* and no
# annotator sees this one -- the payload carries the words, under `question`. What the field is for
# is telling two *kinds* of question apart, there is one kind, so what it has to be is stable: the
# id below is minted over it.
QUESTION_NAME = "label_is_right"

# How a `question_id` is written. Sixteen hex is `record_id`'s own length (Requirement 6) for
# `record_id`'s own reason: both are read by people, in a store row and in a task payload.
ID_PREFIX = "q_"
ID_LENGTH = 16

# What a question's fields are joined with before they are hashed, as `scenario_hash` joins tool
# names. A separator and not an escape: a `|` inside a question's own words could in principle join
# to the same string as some other question, and what that would take is someone writing this
# module's field order into a question on purpose.
FIELD_SEPARATOR = "|"


def needs_a_question(record: Record) -> bool:
    """This stage's precondition: `triage` picked this record out for a person to look at.

    Two absences and one decision, and only the decision is § *Per-service contracts*' cell. A
    record `triage` never reached carries no selection to read, and it is skipped for `pii_check`'s
    reason rather than for this one -- nothing has placed it, so nothing has said a person should
    see it.
    """
    selection = record.ai_review.triage
    return selection is not None and selection.selected_for_review


def question_id_for(
    record_id: str, name: str, content: str, permitted: Sequence[str]
) -> str:
    """The id this exact question is joined on, everywhere, for as long as it exists.

    A pure function of the question, so two runs over one corpus mint one id and the store's unique
    constraint makes the second publish a no-op (Requirement 23). Everything the question *is* goes
    in, which is what makes a rewording a new question rather than a silent no-op.
    """
    fields = (record_id, name, content, *permitted)
    return ID_PREFIX + compute_hash(FIELD_SEPARATOR.join(fields))[:ID_LENGTH]


def question_about(engine: Engine, record: Record) -> Question:
    """One record's question: the words, the answers it permits, and the id that joins both."""
    permitted: tuple[str, ...] = engine.profile.answer_config(record).verdicts
    content = engine.profile.question_text(record)
    return Question(
        question_id=question_id_for(
            record.record_id, QUESTION_NAME, content, permitted
        ),
        question_name=QUESTION_NAME,
        content=content,
        enum=permitted,
    )


def question_generate(engine: Engine, records: Iterable[Record]) -> ServiceResult:
    """Every flagged record, one key richer: the one question a person will be asked about it.

    One question, in a tuple of one (Requirement 29). The tuple is the record's shape and not this
    stage's ambition: a second *kind* of question is a change to this module and to nothing else,
    which is what the shape leaves room for.
    """
    written: list[Record] = []
    for record in records:
        if not needs_a_question(record):
            written.append(record)
            continue
        written.append(
            record.model_copy(
                update={
                    "human_review": record.human_review.model_copy(
                        update={STAGE: (question_about(engine, record),)}
                    )
                }
            )
        )
    return ServiceResult(records=tuple(written))
