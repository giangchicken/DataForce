"""STEP · aggregate · overlap becomes one verdict with a confidence and an agreement statistic.

Arithmetic over what ``annotator_answers`` wrote, and it asks nobody anything -- the same reason
``cohesion`` is not folded into ``jury``: people are expensive and re-reading what they said is free.

**Three numbers, and they answer three different questions.** ``overlap`` is how many people saw
this record. ``confidence`` is how much *they* agreed about it, which is a fact about one record.
``alpha`` is Krippendorff's α over the whole batch, which is a fact about the annotation *design* --
whether the question is answerable consistently at all -- and it is the same number on every record
this run aggregated. A record aggregated alone therefore carries the α of a corpus of one, and two
records are comparable on it only within one run. That is what a corpus statistic is; it is on the
record because the records are the report (Requirement 44).

**All three are folded over one answer per person** (``one_answer_each``). Two rows from one
annotator are a revision and not a second opinion, and every number above is about independent
observers -- so the later answer stands and the earlier one is not counted beside it. The store
permits the second row on purpose, because a person correcting themselves is legitimate; what is
not is a self-pair scoring as a corroboration.

**α is over the verdict and not over the correction, and that is a real choice.** α compares every
value to every other to estimate what disagreement chance alone would produce, so it needs one value
space every unit shares. The three verdicts are that space. A *correction* is an answer to one
record's own catalog, and a coincidence matrix over answers from different records would be pricing
the chance of agreeing about two different questions. What the corrections feed instead is
``confidence``, per record, where both answers are about the same thing.

**Where δ is used, it is the profile's** (Requirement 34's acceptance). Two responses are apart by
their verdicts first and by ``answer_distance`` between their corrections second, so two people who
both said the label is wrong and named the same tool with one argument different are nearly agreed
rather than simply disagreed -- which string equality cannot express and is the whole reason δ is
soft (Decision 15).

**Absent evidence reads as absent agreement.** One response has no pair to measure and gets a
confidence of ``0.0`` rather than ``1.0``, for ``cohesion``'s reason: a single annotator scored as
unanimous is a record wearing a corroboration it does not have. ``overlap`` sits beside it and is
what tells a reader which. Whether one is enough is not this number's business -- it is the declared
overlap floor's, and at the Smoke rung one *is* the design.

**A record under the floor keeps its answers and gets no verdict.** Raising the floor loses nothing:
the responses stay on the record and the next run with more of them folds them.
"""

from collections.abc import Iterable, Sequence
from itertools import combinations

from dataforce.engine import Engine, ServiceResult
from dataforce.record import AnnotatorResponse, OverlapVerdict, Record

from ..params import declared_count

# The key this stage owns, under `human_review`: one key, one writer.
STAGE = "aggregate"

# The estimator, named so that two runs producing different numbers can be told apart from two runs
# measuring different things -- `cohesion`'s reason for carrying one. It names the verdict rule and
# the confidence fold; `alpha` names its own statistic.
METHOD = "plurality_verdict_mean_1_minus_delta"

# Where `params.yaml` declares how many people must have answered. The same number as the annotation
# project's `maximum_annotations`, so the two cannot drift.
OVERLAP_FLOOR = ("thresholds", "aggregate", "overlap_floor")

# The smallest unit α can measure: one value has nothing to disagree with.
MEASURABLE = 2


def one_answer_each(
    responses: Sequence[AnnotatorResponse],
) -> tuple[AnnotatorResponse, ...]:
    """One answer per annotator -- the last each of them submitted -- in the order they first appear.

    **An overlap is a number of people and not a number of submissions**, and nothing upstream
    enforces that: the store has no unique `(question_id, annotator_id)` and the sync writes every
    annotation the tool returned. Deduplicated here rather than forbidden there, because a person
    revising their own answer is legitimate and the second row *is* the revision -- what is not
    legitimate is counting it as a second opinion.

    Every number this stage writes is about independent observers, which is why the fold and not
    just `overlap` reads this: `confidence` would take a self-pair for a corroboration, a floor of
    two would be cleared by one person twice, and α is **defined** over coders -- a unit holding
    one person twice is not a weak measurement of agreement but not a measurement of one.

    First-appearance order is kept so `agreed_verdict`'s tiebreak stays *whoever answered first*,
    which is a person rather than a row.
    """
    latest: dict[str, AnnotatorResponse] = {}
    for response in responses:
        held = latest.get(response.annotator_id)
        if held is None or held.submitted_at <= response.submitted_at:
            latest[response.annotator_id] = response
    return tuple(latest.values())


def responses_to_fold(record: Record) -> tuple[AnnotatorResponse, ...]:
    """This stage's precondition, as the value it needs: what each person said about this record.

    Absent and empty are one fact -- *nobody has answered* -- which is the shape `publish` uses and
    not `cohesion`'s. A record whose every answer was a skip has the key with nothing in it, and it
    reaches the floor test as the zero responses it is.
    """
    returned = record.human_review.annotator_answers
    return one_answer_each(returned.responses) if returned else ()


def response_distance(
    engine: Engine, a: AnnotatorResponse, b: AnnotatorResponse
) -> float:
    """How far apart two people's answers are: their verdicts first, then their corrections.

    Different verdicts are simply apart -- the values are an enum and there is no order on them, so
    *correct* is no closer to *unsure* than to *incorrect*. Same verdict, and what remains is what
    they proposed instead, which is δ's own question.

    **No verdict value is named here** (Decision 22). A response that carries no correction carries
    the empty answer, and `δ(∅, ∅) = 0`, so two people who agreed the label is right compare equal
    without this module knowing which value means that.
    """
    if a.verdict != b.verdict:
        return 1.0
    return engine.profile.answer_distance(
        a.corrected_value or (), b.corrected_value or ()
    )


def agreed_verdict(responses: Sequence[AnnotatorResponse]) -> str:
    """The verdict most of them chose, ties going to whoever answered first in the store's order.

    The verdicts are an enum, so this is a count and not a δ fold: two people choosing *correct*
    chose the same value, and there is no *nearly correct*.
    """
    counted = [response.verdict for response in responses]
    return max(
        counted, key=lambda verdict: (counted.count(verdict), -counted.index(verdict))
    )


def confidence_in(engine: Engine, responses: Sequence[AnnotatorResponse]) -> float:
    """How much the people who saw this record agreed about it: `1 - δ`, meaned over their pairs.

    Pairwise, because agreement among N is a property of the pairs and not of any one of them --
    `cohesion.agreement_scores` measures the panel the same way, so the two numbers are read on one
    scale. `0.0` over no pair at all.
    """
    apart = [response_distance(engine, a, b) for a, b in combinations(responses, 2)]
    return 1.0 - sum(apart) / len(apart) if apart else 0.0


def coincidences(units: Sequence[Sequence[str]]) -> dict[tuple[str, str], float]:
    """α's coincidence matrix: how often each ordered pair of verdicts co-occurred in one record.

    Each unit's ordered pairs are weighted `1 / (m - 1)`, which is what makes a record two people
    answered and a record five people answered contribute comparably -- and is the whole of how α
    handles an *incomplete* overlap design, where not every annotator sees every record.
    """
    matrix: dict[tuple[str, str], float] = {}
    for unit in units:
        weight = 1.0 / (len(unit) - 1)
        for first, second in combinations(unit, 2):
            matrix[(first, second)] = matrix.get((first, second), 0.0) + weight
            matrix[(second, first)] = matrix.get((second, first), 0.0) + weight
    return matrix


def krippendorff_alpha(units: Sequence[Sequence[str]]) -> float:
    """α over those units: 1 is perfect agreement, 0 is chance, and below 0 is systematic disagreement.

    The nominal form, over the three verdicts. `0.0` where no record has two answers, on the
    stage's *absent evidence* rule; `1.0` where every answer everywhere was the same value, because
    the expected disagreement is then zero and so is the observed -- a corpus nobody disagreed about
    is not a corpus α has nothing to say about.
    """
    measured = [unit for unit in units if len(unit) >= MEASURABLE]
    total = sum(len(unit) for unit in measured)
    if total < MEASURABLE:
        return 0.0
    matrix = coincidences(measured)
    per_value: dict[str, float] = {}
    for (first, second), count in matrix.items():
        per_value[first] = per_value.get(first, 0.0) + count
    observed = sum(count for (a, b), count in matrix.items() if a != b)
    expected = sum(
        held * per_value[other]
        for value, held in per_value.items()
        for other in per_value
        if other != value
    )
    return 1.0 if not expected else 1.0 - (total - 1) * observed / expected


def overlap_verdict(
    engine: Engine, responses: Sequence[AnnotatorResponse], alpha: float
) -> OverlapVerdict:
    """One record's verdict: what the overlap said, how much it agreed, and how many said it.

    `alpha` is handed in rather than computed here, because it is the batch's and computing it per
    record would be computing the same number once per record out of the same data.
    """
    return OverlapVerdict(
        verdict=agreed_verdict(responses),
        method=METHOD,
        confidence=confidence_in(engine, responses),
        overlap=len(responses),
        alpha=alpha,
    )


def aggregate(engine: Engine, records: Iterable[Record]) -> ServiceResult:
    """Every record enough people answered, one key richer: the verdict their overlap agreed on.

    The floor is read before the first record, on `triage`'s line: a `params.yaml` this stage
    cannot run on stops the run rather than half of it. α is computed once over the batch, before
    any verdict is written, because it is the same number on every record that gets one.
    """
    floor = declared_count(engine, *OVERLAP_FLOOR)
    running = tuple(records)
    alpha = krippendorff_alpha(
        [
            [response.verdict for response in responses_to_fold(record)]
            for record in running
        ]
    )
    written: list[Record] = []
    for record in running:
        responses = responses_to_fold(record)
        if len(responses) < floor:
            written.append(record)
            continue
        written.append(
            record.model_copy(
                update={
                    "human_review": record.human_review.model_copy(
                        update={STAGE: overlap_verdict(engine, responses, alpha)}
                    )
                }
            )
        )
    return ServiceResult(records=tuple(written))
