"""STEP · label_check · the five checks on the label that need no opinion.

The checks are the profile's, not this stage's: `label_checks()` hands back one named predicate per
defect, and every one of the five is provable by counting -- no person decides any of them, which is
what makes them ``data_quality``'s and not ``human_review``'s. This module runs them, in the order
the profile declares, and writes what they found.

**A failing record is marked and travels on** (Requirement 41). Nothing here removes a record,
nothing raises, and the record it hands back carries why -- ``failed_checks`` names the defects and
``quarantined`` is what the stages downstream read.

**Nothing here compares a count to anything.** Requirement 22 reads as though this stage checks each
check's count against ``params.invalid_counts``, and Requirement 44 settles what that means: a
corpus-level number is a fold at the edge, for reading, and *a count that has moved is something a
human sees in a diff, not a crash* (Decision 10). So the counting is ``edge/artifacts.py``'s and the
comparison is a line in ``metrics.json``. A check reading 0 is what tells you when it stops reading 0.
"""

from collections.abc import Iterable

from dataforce.engine import Engine, ServiceResult
from dataforce.record import LabelVerdict, Record


def label_verdict(engine: Engine, record: Record) -> LabelVerdict:
    """What the five checks found on this record's label, in the order the profile declares them.

    **`passed` and `quarantined` are one boolean written twice, and they are two fields because they
    answer different questions.** `passed` is about the label -- did every check on it hold -- and
    `quarantined` is an instruction to the stages after this one. They coincide because all five
    defects are disqualifying; the day a check is added that is advisory rather than disqualifying,
    they part company and nothing else has to move. Collapsing them now would be the cheaper record
    and the one that cannot express that.
    """
    failed = tuple(
        check.name for check in engine.profile.label_checks() if check.defect_in(record)
    )
    return LabelVerdict(
        passed=not failed, failed_checks=failed, quarantined=bool(failed)
    )


def label_check(engine: Engine, records: Iterable[Record]) -> ServiceResult:
    """Every record, one key richer: what the checks that need no opinion found on its label.

    No precondition (P12): this is the first stage of the phase and reads only what `load_data`
    wrote, so every record it is handed gets a verdict. There is no side output -- the records are
    the report.
    """
    return ServiceResult(
        records=tuple(
            record.model_copy(
                update={
                    "data_quality": record.data_quality.model_copy(
                        update={"label_check": label_verdict(engine, record)}
                    )
                }
            )
            for record in records
        )
    )
