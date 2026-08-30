"""I8 and I11 together, over one corpus, through every built stage there is.

Requirement 41 says `output == input` at every stage "structurally — not asserted, because there is
nothing to assert against". Once four stages exist there is: run them in the order the flow declares
and watch the diff. This is the test that catches a stage quietly filtering, which is the failure the
whole precondition design exists to prevent -- a stage that returns `records[:-1]` fails here rather
than being noticed in review, and the scan is proved against exactly that below.

**The stages are discovered from the flow table, not listed.** `pipeline/flow.py` is the one place the
flow exists in code and `stage_module_name` is the derivation the runner itself uses, so a stage added
to a phase is folded here the day it is written -- and if nobody says which paths it may write, this
fails rather than passing vacuously.

**All three built phases are folded, in the flow's order, over one corpus.** Each joined when its
last stage landed, and each belongs in the same fold rather than a second one: every phase's
preconditions read what the one before it wrote, so a `jury` that judged a quarantined record, a
`triage` that ran on a record with no cohesion figure, or a `publish` that published a question
`triage` never selected is caught here against real upstream output instead of a fixture's idea of
it. It also puts `jury` downstream of a `content` rewrite, which is the order a run has.

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
from dataforce.pipeline.ai_review.triage import CELLS
from dataforce.pipeline.flow import STAGES
from dataforce.pipeline.load_data import load_data
from dataforce.pipeline.runner import Service, stage_module_name
from dataforce.ports import QuestionToStore, StoredAnnotation, StoreReceipt
from dataforce.record import DataQuality, Record

from ..stages.test_jury import a_panel_of
from ..stages.test_label_check import written_paths
from ..stages.test_load_data import an_engine
from ..stages.test_pii_check import TYPED, confirming_everything
from ..stages.test_publish import AStore
from ..stages.test_tool_decision import SENT, an_annotation, an_item

# Every phase whose stages are built, in the flow's order. `load_data` is not one: it mints the
# records this fold starts from and its input is not the bus (`flow.py`'s `FROM_SOURCE`).
PHASES = ("data_quality", "ai_review", "human_review")

# Requirement 5, as data: the paths each stage may change, and no others. Keyed by stage rather
# than by phase because a stage name is unique in the flow -- and the order is the flow's, which
# is what the assertion below compares the fold against.
PERMITTED = {
    "label_check": {"data_quality.label_check"},
    "pii_check": {"data_quality.pii_check", "content", "content_version", "label"},
    "duplicate_check": {"data_quality.duplicate_check"},
    "jury": {"ai_review.jury"},
    "cohesion": {"ai_review.cohesion"},
    "triage": {"ai_review.triage"},
    "question_generate": {"human_review.question_generate"},
    "publish": {"human_review.publish"},
    "annotator_answers": {"human_review.annotator_answers"},
    "aggregate": {"human_review.aggregate"},
    "curate": {"human_review.curate"},
}


class AnAnsweringStore(AStore):
    """A store where a person answers the moment a question reaches it.

    The one fixture in this file that models something a fold cannot contain: `publish` and
    `annotator_answers` are two stages *because a person answers in between* (Decision 22), so a
    single fold over the phase would otherwise stop at a store nobody had visited. Answering on
    write is the shortest honest stand-in, and it is what lets all five stages run over one corpus
    against real upstream output rather than a fixture's idea of it.
    """

    def __init__(self) -> None:
        super().__init__()
        self.answers: list[StoredAnnotation] = []

    def stored_questions(self, questions: Sequence[QuestionToStore]) -> StoreReceipt:
        receipt = super().stored_questions(questions)
        self.answers.extend(
            StoredAnnotation(
                answer_id=f"a_{question.question_id}",
                question_id=question.question_id,
                annotator_id="u_14",
                result=tuple(an_annotation()),
                was_skipped=False,
                lead_time_seconds=41.5,
                submitted_at=datetime(2026, 8, 25, tzinfo=UTC),
            )
            for question in questions
        )
        return receipt

    def answers_to(self, question_ids: Sequence[str]) -> Sequence[StoredAnnotation]:
        wanted = set(question_ids)
        return [answer for answer in self.answers if answer.question_id in wanted]


class Step(NamedTuple):
    """One stage of the fold: what it was given, and what it gave back."""

    stage: str  # the flow's name for it, which is also the key it owns
    before: tuple[Record, ...]  # the bus on the way in
    after: tuple[Record, ...]  # the bus on the way out


def an_engine_for_a_run() -> Engine:
    """One engine for the whole fold: redaction on, layer two answering, a panel behind `jury`.

    The triage declarations are written here rather than read out of `params.yaml`, because what
    this file asserts is the bus and not the file -- `tests/stages/test_triage.py` is where the
    shipped declarations are run. Every quota is full so nothing is sampled away: a record the
    sampling skipped still has a `triage` key, but a fold that selected none of them would be a
    weaker fixture for no reason.
    """
    from dataclasses import replace

    return replace(
        an_engine(
            {
                "enable_redact": True,
                "thresholds": {
                    "duplicate_check": {"near_duplicate_cosine": 0.95},
                    "triage": {
                        "self_agreement_floor": 0.7,
                        "label_agreement_floor": 0.7,
                        "buckets": {
                            cell: {"stratum": "flagged", "quota": 1.0}
                            for cell in CELLS.values()
                        },
                    },
                    "aggregate": {"overlap_floor": 1},
                },
            }
        ),
        personal_data_verifier=confirming_everything(),
        jury_panel=a_panel_of((SENT,), (SENT,)),
        question_store=AnAnsweringStore(),
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


def services_of(*phases: str) -> list[tuple[str, Service]]:
    """Every built stage of those phases, in the flow's order, found the way the runner finds them."""
    return [
        (
            row.stage,
            getattr(import_module(stage_module_name(row.phase, row.stage)), row.stage),
        )
        for row in STAGES
        if row.phase in phases
    ]


def a_fold(
    engine: Engine,
    corpus: Sequence[Record],
    stages: Sequence[tuple[str, Service]] | None = None,
) -> list[Step]:
    """The phase's stages over one corpus, keeping what each step was given and gave back.

    `stages` is a way to fold *part* of the flow, which is what `POST /data-quality/pii-check` is:
    every built phase is the default and the only thing that overrides it is the precondition test
    below, where the record has to arrive without the first stage's key.
    """
    steps: list[Step] = []
    running = tuple(corpus)
    for stage, service in stages if stages is not None else services_of(*PHASES):
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
    """I8 and I11, per step, over a corpus that exercises every state either phase has."""
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
    assert any(
        record.ai_review.triage and record.ai_review.jury for record in written
    ), "a record the whole of ai_review ran on"
    assert any(
        record.data_quality.label_check
        and record.data_quality.label_check.quarantined
        and record.ai_review.jury is None
        and record.ai_review.triage is None
        for record in written
    ), "a quarantined record that no stage of ai_review touched"
    assert any(
        record.content_version == 2 and record.ai_review.jury for record in written
    ), "a record judged on content pii_check had already rewritten"
    assert any(record.human_review.curate for record in written), (
        "a record that reached the end of the flow with a label that ships"
    )
    assert any(
        record.ai_review.triage is None and record.human_review.publish is None
        for record in written
    ), "a record no stage of human_review touched, for the absence upstream"


def test_a_record_that_meets_no_precondition_travels_the_whole_flow() -> None:
    """The other half of Requirement 41: a skipped record is passed on, never dropped.

    A record with no `label_check` key is what a caller produces by posting straight to
    `POST /data-quality/pii-check`. `pii_check` skips it and writes nothing; `duplicate_check` has no
    precondition and still groups it, because a quarantined or unchecked record is still a duplicate
    of something.
    """
    engine = an_engine_for_a_run()
    unchecked = a_corpus(engine)[0].model_copy(update={"data_quality": DataQuality()})

    steps = a_fold(engine, [unchecked], services_of("data_quality")[1:])

    assert [finding for step in steps for finding in bus_findings(step)] == []
    assert steps[-1].after[0].data_quality.pii_check is None
    assert steps[-1].after[0].data_quality.duplicate_check is not None


# --- the scan itself, proved red ---


def test_the_scan_rejects_a_step_that_dropped_a_record() -> None:
    """Proved red, and T18's own verification step, as a test rather than as an instruction to try it."""
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
