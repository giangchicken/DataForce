"""I8 and I11 together, over one corpus, through every built stage of `data_quality`.

Requirement 41 says `output == input` at every stage "structurally — not asserted, because there is
nothing to assert against". Once four stages exist there is: run them in the order the flow declares
and watch the diff. This is the test that catches a stage quietly filtering, which is the failure the
whole precondition design exists to prevent -- a stage that returns `records[:-1]` fails here rather
than being noticed in review, and the scan is proved against exactly that below (P29).

**The stages are discovered from the flow table, not listed.** `pipeline/flow.py` is the one place the
flow exists in code and `stage_module_name` is the derivation the runner itself uses, so a stage added
to the phase is folded here the day it is written -- and if nobody says which paths it may write, this
fails rather than passing vacuously.

**`PERMITTED` is Requirement 5, as data.** One key, and one exception: `pii_check` also rewrites
`content` and the `label` and bumps `content_version`. Writing the exception down as a set is what
makes it an exception rather than a hole -- a stage that touched `label` would fail this test, and
`pii_check` touching a fifth path would too.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from importlib import import_module
from typing import Any, NamedTuple

from dataforce.engine import Engine, ServiceResult
from dataforce.pipeline.flow import STAGES
from dataforce.pipeline.load_data import load_data
from dataforce.pipeline.runner import Service, stage_module_name
from dataforce.record import DataQuality, Record

from ..stages.test_label_check import written_paths
from ..stages.test_load_data import an_engine
from ..stages.test_pii_check import TYPED, confirming_everything
from ..stages.test_tool_decision import SENT, an_item

PHASE = "data_quality"

# Requirement 5, as data: the paths each stage may change, and no others.
PERMITTED = {
    "label_check": {"data_quality.label_check"},
    "pii_check": {"data_quality.pii_check", "content", "content_version", "label"},
    "duplicate_check": {"data_quality.duplicate_check"},
}


class Step(NamedTuple):
    """One stage of the fold: what it was given, and what it gave back."""

    stage: str  # the flow's name for it, which is also the key it owns
    before: tuple[Record, ...]  # the bus on the way in
    after: tuple[Record, ...]  # the bus on the way out


def an_engine_for_a_run() -> Engine:
    """One engine for the whole fold, with redaction on and layer two answering."""
    from dataclasses import replace

    return replace(
        an_engine(
            {
                "enable_redact": True,
                "thresholds": {"duplicate_check": {"near_duplicate_cosine": 0.95}},
            }
        ),
        personal_data_verifier=confirming_everything(),
    )


def a_corpus(engine: Engine) -> tuple[Record, ...]:
    """Every state the fold has to survive, loaded the way a run loads it.

    A duplicate pair (two items whose turns are identical, so they share a `record_id`), a record
    that `label_check` will quarantine (nothing was offered, so nothing could be chosen), a record
    carrying personal data in both its content and its label, and one item that cannot be read at
    all -- which never becomes a record, and is here to show that the conservation property starts
    where the bus does.
    """
    items: list[dict[str, Any]] = [
        an_item(id="s1"),
        an_item(id="s2"),
        an_item(
            id="s3",
            tools=[],
            messages=[{"role": "user", "content": "Mình muốn hỏi một chuyện."}],
        ),
        an_item(
            id="s4",
            messages=[{"role": "user", "content": f"Mã của mình là {TYPED}."}],
            meta={"label": [SENT]},
        ),
        an_item(id="s5", messages="không phải một danh sách"),
    ]
    return load_data(
        engine,
        items,
        source_file_sha256="d" * 64,
        ingested_at=datetime(2026, 8, 24, tzinfo=UTC),
        run_id="r_2026-08-24T00:00:00Z_bus",
    ).records


def services_of(phase: str) -> list[tuple[str, Service]]:
    """Every built stage of that phase, in the flow's order, found the way the runner finds them."""
    return [
        (
            row.stage,
            getattr(import_module(stage_module_name(row.phase, row.stage)), row.stage),
        )
        for row in STAGES
        if row.phase == phase
    ]


def a_fold(
    engine: Engine,
    corpus: Sequence[Record],
    stages: Sequence[tuple[str, Service]] | None = None,
) -> list[Step]:
    """The phase's stages over one corpus, keeping what each step was given and gave back.

    `stages` is a way to fold *part* of a phase, which is what `POST /data-quality/pii-check` is:
    the whole phase is the default and the only thing that overrides it is the precondition test
    below, where the record has to arrive without the first stage's key.
    """
    steps: list[Step] = []
    running = tuple(corpus)
    for stage, service in stages if stages is not None else services_of(PHASE):
        result: ServiceResult = service(engine, running)
        steps.append(Step(stage, running, result.records))
        running = result.records
    return steps


def bus_findings(step: Step) -> list[str]:
    """Every way one step broke the bus: a record lost, an id moved, or a key it does not own."""
    found = []
    if len(step.after) != len(step.before):
        found.append(
            f"{step.stage}: {len(step.before)} records in, {len(step.after)} out"
        )
    if {record.record_id for record in step.after} != {
        record.record_id for record in step.before
    }:
        found.append(f"{step.stage}: the record_id set moved")
    permitted = PERMITTED.get(step.stage)
    if permitted is None:
        return [*found, f"{step.stage}: nothing says which paths it may write"]
    for before, after in zip(step.before, step.after, strict=False):
        written = written_paths(before.model_dump(), after.model_dump())
        if not written <= permitted:
            found.append(f"{step.stage}: wrote {sorted(written - permitted)}")
    return found


# --- the two properties, over the whole fold ---


def test_every_step_writes_only_what_it_owns_and_returns_every_record() -> None:
    """I8 and I11, per step, over a corpus that exercises every state `data_quality` has."""
    engine = an_engine_for_a_run()

    steps = a_fold(engine, a_corpus(engine))

    assert [stage for stage, _, _ in steps] == list(PERMITTED)
    assert [finding for step in steps for finding in bus_findings(step)] == []


def test_the_id_set_is_the_same_at_the_last_step_as_at_the_first() -> None:
    """I11 end to end, and the reason `record_id` is a field: `pii_check` rewrote content.

    An id derived on every construction would move under redaction and take every join in the corpus
    with it -- so this asserts both that nothing was dropped and that nothing was renamed.
    """
    engine = an_engine_for_a_run()
    corpus = a_corpus(engine)

    steps = a_fold(engine, corpus)

    assert {record.record_id for record in steps[-1].after} == {
        record.record_id for record in corpus
    }
    assert any(
        step.stage == "pii_check" and step.after != step.before for step in steps
    )


def test_every_state_the_corpus_was_built_to_hold_is_in_it() -> None:
    """Guards the fixture: a corpus with none of these states would make the fold vacuous."""
    engine = an_engine_for_a_run()
    corpus = a_corpus(engine)
    written = a_fold(engine, corpus)[-1].after

    assert len(corpus) == 4, "one of the five items is unreadable and becomes no record"
    assert len({record.record_id for record in corpus}) == 3, "the duplicate pair"
    assert any(
        record.data_quality.label_check and record.data_quality.label_check.quarantined
        for record in written
    )
    assert any(
        record.data_quality.pii_check
        and record.data_quality.pii_check.decision == "redacted"
        and record.content_version == 2
        for record in written
    )
    assert any(
        record.data_quality.duplicate_check
        and record.data_quality.duplicate_check.duplicate_content_same_label
        for record in written
    )


def test_a_record_that_meets_no_precondition_travels_the_whole_flow() -> None:
    """The other half of Requirement 41: a skipped record is passed on, never dropped.

    A record with no `label_check` key is what a caller produces by posting straight to
    `POST /data-quality/pii-check`. `pii_check` skips it and writes nothing; `duplicate_check` has no
    precondition and still groups it, because a quarantined or unchecked record is still a duplicate
    of something.
    """
    engine = an_engine_for_a_run()
    unchecked = a_corpus(engine)[0].model_copy(update={"data_quality": DataQuality()})

    steps = a_fold(engine, [unchecked], services_of(PHASE)[1:])

    assert [finding for step in steps for finding in bus_findings(step)] == []
    assert steps[-1].after[0].data_quality.pii_check is None
    assert steps[-1].after[0].data_quality.duplicate_check is not None


# --- the scan itself, proved red ---


def test_the_scan_rejects_a_step_that_dropped_a_record() -> None:
    """P29, and T18's own verification step, as a test rather than as an instruction to try it."""
    engine = an_engine_for_a_run()
    corpus = a_corpus(engine)

    dropped = Step("label_check", corpus, corpus[:-1])

    assert bus_findings(dropped) != []


def test_the_scan_rejects_a_step_that_wrote_a_key_it_does_not_own() -> None:
    """The I8 half: `label_check` bumping `content_version` is not a smaller version of one key."""
    engine = an_engine_for_a_run()
    corpus = a_corpus(engine)
    meddled = tuple(
        record.model_copy(update={"content_version": 7}) for record in corpus
    )

    assert bus_findings(Step("label_check", corpus, meddled)) != []


def test_the_scan_rejects_a_stage_nobody_declared_the_paths_of() -> None:
    """A stage added to the phase and not to `PERMITTED` fails rather than passing vacuously."""
    engine = an_engine_for_a_run()
    corpus = a_corpus(engine)

    assert bus_findings(Step("a_new_stage", corpus, corpus)) != []
