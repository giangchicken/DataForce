"""STEP · duplicate_check · exact and near-duplicate groups, split by label agreement.

Two records that say the same thing are two answers to one question, and which of them is right
matters differently depending on whether they agree: *same content, same label* is a record to drop
one of, and *same content, different label* means one of them is wrong. So the report is two groups
per record and nothing is removed (Requirement 41) -- dropping a duplicate is a decision for
``split`` and for a person, made once, with both groups on the record to make it from.

**What counts as a duplicate needs both axes, and this is where the plan said to settle it.** The
content side is the modality's: an identical ``record_id`` for the same content, and the modality's
static ``embedding`` for near-identical content, which is what makes two runs group identically
(Requirement 23). The answer side is the profile's δ: ``answer_distance(a, b) == 0`` is *the same
answer* by the profile's own definition, including the argument-order and bare-name cases a ``==``
would miss. **No new member was needed for either**, and ``scenario_hash`` is not the answer side --
it names the task a record poses, which is the third thing:

**Near-duplicates are only compared within one scenario.** Two identical prompts offering different
tools are not duplicates *for this task*: the answer space differs, so a model choosing between them
is being asked two different questions, and ``scenario_hash`` is already the name for *these two
records pose the same task*. Using it as the blocking key is that fact read a second time, and it is
the one thing keeping the comparison affordable -- pairwise cosine over one batch is quadratic, and
the block is what a corpus of twenty thousand records divides it by. **The cost, stated:** a corpus
where every record offers one catalog is one block and the quadratic comes back. The exit, when that
day comes, is a signature to block on or an index -- not a smaller batch.

**An exact-content pair is compared regardless of scenario**, because ``record_id`` is over content
alone (Requirement 6) and two records that share one are already a fact the corpus has to answer for.
Which means a record in such a pair lists **its own id** in one of the two groups: the id of the other
record *is* its own. That reads oddly and is the honest report -- the alternative, excluding an id
equal to one's own, would hide exactly the pair that most needs finding.
"""

from collections.abc import Iterable, Sequence
from itertools import combinations
from math import sqrt

from dataforce.engine import Engine, ServiceResult
from dataforce.record import DuplicateGroups, Record

from ..params import declared_ratio

# Where `params.yaml` declares how alike two records' content has to be.
NEAR = ("thresholds", "duplicate_check", "near_duplicate_cosine")


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    """How alike two vectors point, from -1 to 1, and 0 where either has no direction at all.

    `strict=True` is an assertion rather than an error path: both vectors came from the one encoder
    this engine was built with, so a length mismatch is not a state a caller can reach (§2).
    """
    scale = sqrt(sum(value * value for value in left)) * sqrt(
        sum(value * value for value in right)
    )
    if not scale:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / scale


def positions_by(keys: Sequence[str]) -> list[list[int]]:
    """The positions sharing each key, as blocks -- by position, because two records share an id."""
    blocks: dict[str, list[int]] = {}
    for position, key in enumerate(keys):
        blocks.setdefault(key, []).append(position)
    return list(blocks.values())


def duplicate_positions(
    engine: Engine, records: Sequence[Record], near: float
) -> set[tuple[int, int]]:
    """Every pair of positions holding the same content, exactly or nearly.

    Exact first and by grouping rather than by comparison, so the common case costs one pass. The
    near pass is where the vectors are needed, and it is skipped for a scenario nothing shares.
    """
    paired = {
        pair
        for block in positions_by([record.record_id for record in records])
        for pair in combinations(block, 2)
    }
    scenarios = positions_by(
        [engine.profile.scenario_hash(record) for record in records]
    )
    vectors = {
        position: engine.modality.embedding(records[position].content)
        for block in scenarios
        if len(block) > 1
        for position in block
    }
    return paired | {
        pair
        for block in scenarios
        for pair in combinations(block, 2)
        if cosine(vectors[pair[0]], vectors[pair[1]]) >= near
    }


def duplicate_groups(
    engine: Engine, records: Sequence[Record], paired: set[tuple[int, int]], of: int
) -> DuplicateGroups:
    """The two groups for one record: the duplicates that agree with its label, and the rest.

    Sorted, so two runs over one corpus write byte-identical groups (Requirement 23), and over
    `record_id`s rather than positions: a position is this batch's and an id is the corpus's.
    """
    partners = [
        left if right == of else right for left, right in paired if of in (left, right)
    ]
    agreeing: set[str] = set()
    differing: set[str] = set()
    for other in partners:
        same = (
            engine.profile.answer_distance(records[of].label, records[other].label)
            == 0.0
        )
        (agreeing if same else differing).add(records[other].record_id)
    return DuplicateGroups(
        duplicate_content_same_label=tuple(sorted(agreeing)),
        duplicate_content_diff_label=tuple(sorted(differing)),
    )


def duplicate_check(engine: Engine, records: Iterable[Record]) -> ServiceResult:
    """Every record, one key richer: which records repeat it, split by whether they agree.

    No precondition (P12) and no skip: a quarantined record is still a duplicate of something, and
    knowing that is part of deciding which of a pair to keep. There is no side output -- a group is a
    value on the record, which is what keeps `output == input` structural (Requirement 41).
    """
    running = tuple(records)
    paired = duplicate_positions(engine, running, declared_ratio(engine, *NEAR))
    return ServiceResult(
        records=tuple(
            record.model_copy(
                update={
                    "data_quality": record.data_quality.model_copy(
                        update={
                            "duplicate_check": duplicate_groups(
                                engine, running, paired, position
                            )
                        }
                    )
                }
            )
            for position, record in enumerate(running)
        )
    )
