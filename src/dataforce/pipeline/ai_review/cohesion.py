"""STEP · cohesion · how much the jury agrees with itself, and with the existing label.

Arithmetic over what ``jury`` wrote, and no model call at all. That is the whole reason it is not
folded into the stage above it (Decision 3): a panel that has answered is never asked again, and
these two numbers can be recomputed for nothing every time the question they feed changes.

**Both numbers are δ, because every number the pipeline produces is** (Decision 15). Agreement is
``1 - answer_distance``, so a jury that called the right tool with one argument wrong scores above
one that called the wrong tool -- which a verdict count would not, and ``label_is_right`` is a
verdict count. The jurors' own opinion of the label is on the record and is not what this measures.

**Only a usable vote is measured.** An invalid vote is an answer outside this record's answer
space, and a distance to a point outside the space is not evidence about the panel; it is evidence
about the panel's *plumbing*, which ``invalid_votes`` already carries. The two numbers stay
comparable between a record whose panel misbehaved and one whose panel did not.

**Absent evidence reads as absent agreement.** A panel with one usable vote has no pair to measure
and a panel with none has nothing at all, and both get ``0.0`` rather than ``1.0``: a single juror
scored as unanimous is a broken panel wearing a confident record's clothes, and ``triage`` would
route it away from the person who should see it. The vote count sits beside the number for whoever
needs to tell the two apart. This is also where ``δ(∅, ∅) = 0`` stops being tidy and starts being
load-bearing -- the empty answer is a large share of a real corpus, and a mean over an empty
sequence is the other way this stage could have produced ``NaN``.

**``method`` is what makes two runs comparable, so a change to what these numbers mean changes
it.** The δ itself is already identified per record, by the profile version in ``provenance``; what
this string names is the estimator over it -- the fold, and which votes went in.
"""

from collections.abc import Iterable, Sequence
from itertools import combinations

from dataforce.engine import Engine, ServiceResult
from dataforce.record import AgreementScores, PanelVerdict, Record, StoredAnswer

# The key this stage owns, under `ai_review` (§26: one key, one writer).
STAGE = "cohesion"

# The estimator, named so that two runs producing different numbers can be told apart from two
# runs measuring different things. It names the fold and the population, because both are choices.
METHOD = "mean_1_minus_delta_over_valid_votes"


def votes_to_fold(record: Record) -> PanelVerdict | None:
    """This stage's precondition, as the value it needs: what `jury` wrote, or None.

    **The key and not the votes in it.** A record whose panel *failed* has a key with no votes and
    is measured -- `0.0` against `0.0` is what a record with no evidence should carry into a
    bucket. A record `jury` *skipped* has no key at all and comes back with none from here either,
    so `triage` reads one absence rather than two.

    A `bool` was the other shape and it is the worse one: it cannot narrow, so the caller reads
    `ai_review.jury` a second time and proves again that it is there -- which is the assert this
    phase just finished deleting (§32). Named for what it returns, beside the signature, once.
    """
    return record.ai_review.jury


def mean(values: Sequence[float]) -> float:
    """The mean of those, and `0.0` over none of them -- never `NaN`, and never `1.0`."""
    return sum(values) / len(values) if values else 0.0


def usable_answers(verdict: PanelVerdict) -> tuple[StoredAnswer, ...]:
    """Every vote the panel cast that this record's answer space accepts, in the panel's order."""
    return tuple(vote.answer for vote in verdict.llm_votes if vote.valid)


def agreement(engine: Engine, a: StoredAnswer, b: StoredAnswer) -> float:
    """How much two answers agree: `1 - δ`, which is `1.0` for two the profile calls identical."""
    return 1.0 - engine.profile.answer_distance(a, b)


def agreement_scores(
    engine: Engine, record: Record, verdict: PanelVerdict
) -> AgreementScores:
    """This record's two numbers: the jurors against each other, and against the label it carries.

    Pairwise for the first, because agreement among N is a property of the pairs and not of any
    one of them; against the label for the second, over the same population, so the two numbers
    are read on one scale.

    The verdict is a parameter rather than read off the record again: `cohesion` has already
    established there is one, and passing it down is what keeps *no votes to fold* out of the
    states anything below this line can be in.
    """
    answers = usable_answers(verdict)
    return AgreementScores(
        self_agreement=mean(
            [agreement(engine, a, b) for a, b in combinations(answers, 2)]
        ),
        label_agreement=mean(
            [agreement(engine, answer, record.label) for answer in answers]
        ),
        method=METHOD,
    )


def cohesion(engine: Engine, records: Iterable[Record]) -> ServiceResult:
    """Every judged record, one key richer: how much its panel agreed, and with what.

    The precondition is `votes_to_fold`, named beside the signature and not spelled inside the
    fold (§22): what it has to make visible is that the *key* is the condition and not the votes
    in it. The loop is `pii_check`'s shape for the same reason -- a skip is one readable statement.
    """
    written: list[Record] = []
    for record in records:
        verdict = votes_to_fold(record)
        if verdict is None:
            written.append(record)
            continue
        written.append(
            record.model_copy(
                update={
                    "ai_review": record.ai_review.model_copy(
                        update={STAGE: agreement_scores(engine, record, verdict)}
                    )
                }
            )
        )
    return ServiceResult(records=tuple(written))
