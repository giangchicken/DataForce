"""T26 · the Label Studio sync: questions out, annotations back, and neither twice.

Not a stage. It is the one thing in this repository that talks to an annotation tool, and it is
tested here because what it moves is the store's rows and `tests/stages` is where the store's tests
already run — on SQLite in `make check` and on a real Postgres under `-m integration`, through
`conftest.py`'s `sessions`.

**The tool is a double, and the constraints are real.** What a fake client cannot prove is
idempotency, because idempotency here is two unique constraints in a database rather than a check in
this code — so every test below runs against the actual schema, and the second sync's no-op is the
database's answer and not the double's.

**One test says what a partial failure must leave behind.** A tool that dies at question two has
already created question one's task, and the row for it has to survive: no constraint can catch a
task nobody recorded, so the row is the record that it exists.

Every fixture is invented (AGENTS.md §9).
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from dataforce.edge.label_studio import (
    BASE_URL,
    EXTERNAL_SYSTEM,
    PUSHED,
    ReturnedAnnotation,
    answer_id_for,
    declared_at,
    label_studio_tool,
    synced_with_label_studio,
)
from dataforce.edge.store.models import AnnotatorAnswer, Publication
from dataforce.edge.store.repository import SqlQuestionStore
from dataforce.errors import ConfigError
from dataforce.pipeline.human_review.annotator_answers import annotator_answers
from dataforce.pipeline.human_review.publish import publish
from dataforce.record import Record

from .test_question_generate import an_engine_asking, another_record, asked
from .test_tool_decision import SENT, a_record, an_annotation

PROJECT = "7"
ANSWERED_AT = datetime(2026, 8, 25, 16, 0, tzinfo=UTC)


class AToolThatAnswers:
    """An `AnnotationTool` that accepts every task and answers each one once.

    It keeps the port's two promises and nothing else: a task gets an id, and the annotations it
    hands back carry the ids it minted. What each answer *says* is a parameter, because the tests
    that care are about the envelope — cancelled or not — rather than about the control values.
    """

    def __init__(self, *, was_cancelled: bool = False, answers: bool = True) -> None:
        self.posted: list[tuple[str, Mapping[str, Any]]] = []
        self._was_cancelled = was_cancelled
        self._answers = answers

    def posted_task(self, project_id: str, payload: Mapping[str, Any]) -> str:
        self.posted.append((project_id, payload))
        return f"t_{len(self.posted)}"

    def annotations_on(self, task_id: str) -> Sequence[ReturnedAnnotation]:
        if not self._answers:
            return ()
        return (
            ReturnedAnnotation(
                annotation_id=f"ls_{task_id}",
                task_id=task_id,
                annotator_id="14",
                result=tuple(an_annotation()),
                was_cancelled=self._was_cancelled,
                lead_time_seconds=41.5,
                submitted_at=ANSWERED_AT,
            ),
        )


class AToolThatDies(AToolThatAnswers):
    """A tool that accepts the first task and then stops answering: an instance going away."""

    def posted_task(self, project_id: str, payload: Mapping[str, Any]) -> str:
        if self.posted:
            raise ConnectionError("the instance is not answering")
        return super().posted_task(project_id, payload)


def a_published_corpus(
    sessions: sessionmaker[Session], *records: Record
) -> tuple[Record, ...]:
    """Records through the phase up to `publish`, so the store holds their questions."""
    engine = replace(an_engine_asking(), question_store=SqlQuestionStore(sessions))
    return publish(engine, asked(engine, *(records or (a_record(),)))).records


def rows_of(sessions: sessionmaker[Session], model: Any) -> list[Any]:
    """Every row of one table, read in a session that does not commit and so expires nothing."""
    with sessions() as session:
        return list(session.scalars(select(model)).all())


# --- questions out ---


def test_a_question_becomes_a_task_and_the_row_that_records_it(
    sessions: sessionmaker[Session],
) -> None:
    """The push, and the row that is the only evidence the task exists."""
    a_published_corpus(sessions)
    tool = AToolThatAnswers()

    counts = synced_with_label_studio(sessions, tool, PROJECT)

    assert counts.pushed == 1
    published = rows_of(sessions, Publication)
    assert [(row.external_system, row.status) for row in published] == [
        (EXTERNAL_SYSTEM, PUSHED)
    ]
    assert published[0].external_project_id == PROJECT
    assert published[0].external_task_id == "t_1"


def test_the_task_carries_the_payload_publish_composed(
    sessions: sessionmaker[Session],
) -> None:
    """The sync moves a payload; it does not build one. Requirement 30 was asserted upstream."""
    a_published_corpus(sessions)
    tool = AToolThatAnswers()

    synced_with_label_studio(sessions, tool, PROJECT)

    project_id, payload = tool.posted[0]
    assert project_id == PROJECT
    assert payload["question_id"].startswith("q_")
    assert "conversation" in payload and "tool_names" in payload


def test_syncing_twice_pushes_nothing_the_second_time(
    sessions: sessionmaker[Session],
) -> None:
    """The acceptance criterion, and the row rather than a flag is what makes it so."""
    a_published_corpus(sessions)
    tool = AToolThatAnswers()
    synced_with_label_studio(sessions, tool, PROJECT)

    counts = synced_with_label_studio(sessions, tool, PROJECT)

    assert (counts.pushed, counts.already_pushed) == (0, 1)
    assert len(tool.posted) == 1
    assert len(rows_of(sessions, Publication)) == 1


def test_a_tool_that_dies_partway_keeps_the_row_for_the_task_that_exists(
    sessions: sessionmaker[Session],
) -> None:
    """No constraint can catch a task nobody recorded, so the row is committed as it is created."""
    a_published_corpus(sessions, a_record(), another_record())
    tool = AToolThatDies()

    with pytest.raises(ConnectionError):
        synced_with_label_studio(sessions, tool, PROJECT)

    assert len(rows_of(sessions, Publication)) == 1


def test_a_tool_that_never_answered_writes_no_row_at_all(
    sessions: sessionmaker[Session],
) -> None:
    """Label Studio unreachable: the sync fails and the store is exactly as it was."""
    a_published_corpus(sessions)

    class ADeadTool(AToolThatAnswers):
        def posted_task(self, project_id: str, payload: Mapping[str, Any]) -> str:
            raise ConnectionError("the instance is not answering")

    with pytest.raises(ConnectionError):
        synced_with_label_studio(sessions, ADeadTool(), PROJECT)

    assert rows_of(sessions, Publication) == []


# --- annotations back ---


def test_an_annotation_becomes_an_answer_row(sessions: sessionmaker[Session]) -> None:
    """The pull, and the envelope the store keeps beside the control values."""
    a_published_corpus(sessions)

    counts = synced_with_label_studio(sessions, AToolThatAnswers(), PROJECT)

    assert counts.pulled == 1
    answered = rows_of(sessions, AnnotatorAnswer)
    assert answered[0].annotator_id == "14"
    assert answered[0].external_annotation_id == "ls_t_1"
    assert answered[0].lead_time_seconds == 41.5
    assert not answered[0].was_skipped


def test_the_control_values_are_written_verbatim(
    sessions: sessionmaker[Session],
) -> None:
    """Requirement 49: only `annotation_response` reads this shape, so the sync may not touch it."""
    a_published_corpus(sessions)

    synced_with_label_studio(sessions, AToolThatAnswers(), PROJECT)

    assert rows_of(sessions, AnnotatorAnswer)[0].result == an_annotation()


def test_a_cancelled_annotation_is_stored_as_a_skip(
    sessions: sessionmaker[Session],
) -> None:
    """Requirement 50: a person declining is evidence about the question, so it is pulled and kept."""
    a_published_corpus(sessions)

    counts = synced_with_label_studio(
        sessions, AToolThatAnswers(was_cancelled=True), PROJECT
    )

    assert counts.pulled == 1
    assert rows_of(sessions, AnnotatorAnswer)[0].was_skipped


def test_syncing_twice_pulls_nothing_the_second_time(
    sessions: sessionmaker[Session],
) -> None:
    """The unique `external_annotation_id`, which is what makes the second pull a no-op."""
    a_published_corpus(sessions)
    tool = AToolThatAnswers()
    synced_with_label_studio(sessions, tool, PROJECT)

    counts = synced_with_label_studio(sessions, tool, PROJECT)

    assert (counts.pulled, counts.already_pulled) == (0, 1)
    assert len(rows_of(sessions, AnnotatorAnswer)) == 1


def test_a_task_nobody_has_answered_pulls_nothing(
    sessions: sessionmaker[Session],
) -> None:
    """An unanswered task is the ordinary state of a task, not an empty answer."""
    a_published_corpus(sessions)

    counts = synced_with_label_studio(
        sessions, AToolThatAnswers(answers=False), PROJECT
    )

    assert (counts.pushed, counts.pulled) == (1, 0)
    assert rows_of(sessions, AnnotatorAnswer) == []


def test_an_empty_store_is_an_ordinary_sync(sessions: sessionmaker[Session]) -> None:
    """Nothing published, nothing to push, nothing to pull, and no call made."""
    tool = AToolThatAnswers()

    counts = synced_with_label_studio(sessions, tool, PROJECT)

    assert (counts.pushed, counts.pulled) == (0, 0)
    assert tool.posted == []


# --- the join back to the bus ---


def test_a_synced_answer_reaches_the_record_through_annotator_answers(
    sessions: sessionmaker[Session],
) -> None:
    """The whole loop: published, pushed, answered by a person, pulled, and read onto the record."""
    engine = replace(an_engine_asking(), question_store=SqlQuestionStore(sessions))
    published = publish(engine, asked(engine, a_record())).records
    synced_with_label_studio(sessions, AToolThatAnswers(), PROJECT)

    written = annotator_answers(engine, published).records[0]

    responses = written.human_review.annotator_answers
    assert responses is not None
    assert [said.corrected_value for said in responses.responses] == [(SENT,)]
    assert responses.responses[0].submitted_at == ANSWERED_AT


# --- the ids, and the environment ---


def test_an_answer_id_is_a_pure_function_of_the_annotation() -> None:
    """Deterministic, so a re-pull that got past the unique constraint collides on the key too."""
    assert answer_id_for("ls_88") == answer_id_for("ls_88")
    assert answer_id_for("ls_88") != answer_id_for("ls_89")


def test_an_unnamed_instance_is_a_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """P23: a human must change something, and the message says which variable."""
    monkeypatch.delenv(BASE_URL, raising=False)

    with pytest.raises(ConfigError, match=BASE_URL):
        declared_at(BASE_URL)


@pytest.mark.integration
def test_the_sdk_client_builds_against_a_declared_instance() -> None:
    """The one thing a double cannot check: that the extra is installed and the URL is reachable.

    Skipped rather than passed where no instance is declared — *not run* and *passed* are different
    claims, and this is the only test in the file that needs `deploy/docker-compose.yml` up.
    """
    import os

    if not os.environ.get(BASE_URL):
        pytest.skip(
            f"{BASE_URL} names no Label Studio; the sync was not run against one"
        )

    assert label_studio_tool() is not None
