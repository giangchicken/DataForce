"""TOOL · the Label Studio sync: questions out, annotations back, idempotent in both directions.

Decision 6's other half. ``publish`` writes to a database we own and never talks to an annotation
tool; this moves rows between that database and one, and **running it is optional** -- every other
endpoint works with no instance anywhere, which is what makes the pipeline testable without one.

**Nothing here touches a record.** The sync reads and writes the store's own three tables and the
bus never enters it, so a failed sync cannot leave a record saying something that did not happen.
That is most of why the two directions are safe to retry.

**Idempotency is two unique constraints, not two flags.** A question already pushed has a
``publication`` row for ``(question_id, external_system)`` and is not offered again; an annotation
already pulled has its ``external_annotation_id`` and is not written again. Both are enforced by the
database rather than by a check this module makes, because a check races with a second sync and a
constraint does not.

**A ``publication`` row is committed as soon as its task exists, one at a time.** Batching the
writes into one transaction would be faster and wrong: a failure at question five rolls back rows
one to four, whose tasks are already sitting in Label Studio, and the next sync creates them a
second time -- which no constraint can catch, because the thing that would have caught it is the row
that was rolled back. The row *is* the record that the task exists.

**The SDK is imported inside the builder, not at the top of this module.** ``label-studio-sdk`` is
an optional extra and ``edge/main.py`` imports this module to hang a route on it, so a top-level
import would make an install without the extra fail at startup rather than at the one endpoint that
needs it. Anything that cannot reach the tool is a ``ConfigError``: a missing extra, a missing URL
and an unreachable host are all *a human must change something* (P23).

**``AnnotationTool`` is declared here and not in ``ports.py``**, because the engine never calls it.
A port is what the engine demands of the edge; this is the edge talking to the outside, so its
abstraction belongs to the module that consumes it (P18) and that module is this one. It has two
adapters -- the SDK client and the double the tests run -- which is what makes it a seam (P20).
"""

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from agent_toolkit.string_utils import compute_hash
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from dataforce.errors import ConfigError

from .store.models import AnnotatorAnswer, Publication, Question

# Which annotation tool a `publication` row belongs to. One value today, and a column rather than an
# assumption: the row's uniqueness is per system, so a second tool is a row and not a migration.
EXTERNAL_SYSTEM = "label_studio"

# What a pushed task's row says happened. One word, in the sync's own vocabulary.
PUSHED = "pushed"

# Where a deployment says which instance, and which project inside it. Read here and nowhere else
# (P25); a key is never written to a file (AGENTS.md §9).
BASE_URL = "DATAFORCE_LABEL_STUDIO_URL"
API_KEY = "DATAFORCE_LABEL_STUDIO_API_KEY"
PROJECT_ID = "DATAFORCE_LABEL_STUDIO_PROJECT"

# How an `answer_id` is minted from the annotation it came out of: deterministic, so a re-pull that
# somehow got past the unique constraint would collide on the primary key too.
ANSWER_PREFIX = "a_"
ANSWER_LENGTH = 16
ID_SEPARATOR = "|"


@dataclass(frozen=True)
class ReturnedAnnotation:
    """One annotation as the tool returned it: the control values, and the envelope around them.

    The same split `StoredAnnotation` makes and for the same reason -- `result` is the capture
    half's and only the profile reads its shape (Requirement 49), while `was_cancelled` and
    `lead_time` are the tool's own metadata and mean the same thing whatever the profile is.
    """

    annotation_id: str  # the tool's id for it; what makes pulling twice a no-op
    task_id: str  # which task it answers, joined back through `publication`
    annotator_id: str  # who answered, in the tool's own vocabulary
    result: tuple[Mapping[str, Any], ...]  # the control values, verbatim
    was_cancelled: bool  # the annotator saw it and declined; stored as `was_skipped`
    lead_time_seconds: float | None  # how long they took, where the tool reported it
    submitted_at: datetime  # when they submitted it, by the tool's clock


@dataclass(frozen=True)
class SyncCounts:
    """What one sync did, in both directions. The route's response is built from it (T28)."""

    pushed: int  # questions that became tasks on this run
    already_pushed: int  # questions a previous run had already pushed
    pulled: int  # annotations written to the store on this run
    already_pulled: int  # annotations a previous run had already written


class AnnotationTool(Protocol):
    """What the sync needs of an annotation tool, and nothing else it happens to offer."""

    def posted_task(self, project_id: str, payload: Mapping[str, Any]) -> str:
        """One task created from that payload, and the id the tool gave it."""
        ...

    def annotations_on(self, task_id: str) -> Sequence[ReturnedAnnotation]:
        """Every annotation that task has, including the cancelled ones."""
        ...


class LabelStudioTool:
    """The `AnnotationTool` over `label-studio-sdk`, and the only place that library is used.

    Thin on purpose: the shape it converts to is `ReturnedAnnotation`, so the sync below reads one
    vocabulary and a change to the SDK's is an edit here. It is also what makes a test double
    possible without pretending to be a third-party client.
    """

    def __init__(self, client: Any) -> None:
        """Built with a client rather than a URL: `label_studio_tool` is the one that reads those."""
        self._client = client

    def posted_task(self, project_id: str, payload: Mapping[str, Any]) -> str:
        """One task in that project, carrying the payload `publish` composed."""
        created = self._client.tasks.create(project=int(project_id), data=dict(payload))
        return str(created.id)

    def annotations_on(self, task_id: str) -> Sequence[ReturnedAnnotation]:
        """Every annotation on that task, per task rather than per project.

        One call per published question, which is the cost of not depending on how a project-wide
        listing paginates or which fields it inlines. A sync is a batch of the questions one run
        published, not of a whole corpus, so the count is bounded by the run.
        """
        return tuple(
            ReturnedAnnotation(
                annotation_id=str(annotation.id),
                task_id=task_id,
                annotator_id=str(annotation.completed_by),
                result=tuple(annotation.result or ()),
                was_cancelled=bool(annotation.was_cancelled),
                lead_time_seconds=annotation.lead_time,
                submitted_at=annotation.created_at or datetime.now(UTC),
            )
            for annotation in self._client.annotations.list(int(task_id))
        )


def declared_at(variable: str) -> str:
    """One value the environment must carry, or a `ConfigError` naming the variable."""
    value = os.environ.get(variable)
    if not value:
        raise ConfigError(
            f"{variable} names no Label Studio; the sync is the one endpoint that needs "
            "an instance, and every other one runs without it"
        )
    return value


def label_studio_tool() -> LabelStudioTool:
    """A client onto the instance this deployment attached, built from the environment.

    The import is here rather than at the top of the module: `label-studio-sdk` is the
    `[label-studio]` extra, and an install without it should fail at this call and not at startup.
    """
    try:
        from label_studio_sdk.client import LabelStudio
    except (
        ImportError
    ) as missing:  # pragma: no cover - exercised by installing without the extra
        raise ConfigError(
            "the sync needs the `label-studio` extra: `uv sync --extra label-studio`"
        ) from missing
    # The SDK ships no type information for its constructor, and this is the one line that
    # touches it -- everything below reads `ReturnedAnnotation`, which is ours.
    client = LabelStudio(  # type: ignore[no-untyped-call]
        base_url=declared_at(BASE_URL), api_key=declared_at(API_KEY)
    )
    return LabelStudioTool(client)


def answer_id_for(annotation_id: str) -> str:
    """The store's own id for an annotation that came from outside it."""
    joined = ID_SEPARATOR.join((EXTERNAL_SYSTEM, annotation_id))
    return ANSWER_PREFIX + compute_hash(joined)[:ANSWER_LENGTH]


def unpushed_questions(session: Session) -> Sequence[tuple[str, dict[str, Any]]]:
    """Every question with no `publication` row for this system, with the payload to push.

    A left join and not a Python filter: the set of already-published questions is the store's to
    know, and reading every question into memory to subtract them is the same query written twice.
    """
    pushed = select(Publication.question_id).where(
        Publication.external_system == EXTERNAL_SYSTEM
    )
    rows = session.execute(
        select(Question.question_id, Question.payload).where(
            Question.question_id.not_in(pushed)
        )
    )
    return [(question_id, payload) for question_id, payload in rows]


def pushed_task_ids(session: Session) -> Sequence[tuple[str, str]]:
    """Every question this system holds a task for, as `(question_id, external_task_id)`."""
    rows = session.execute(
        select(Publication.question_id, Publication.external_task_id).where(
            Publication.external_system == EXTERNAL_SYSTEM,
            Publication.external_task_id.is_not(None),
        )
    )
    return [(question_id, str(task_id)) for question_id, task_id in rows]


def pulled_annotation_ids(session: Session) -> set[str]:
    """Every annotation the store has already written, by the id the tool gave it."""
    return set(
        session.scalars(
            select(AnnotatorAnswer.external_annotation_id).where(
                AnnotatorAnswer.external_annotation_id.is_not(None)
            )
        )
    )


def questions_pushed(
    sessions: sessionmaker[Session], tool: AnnotationTool, project_id: str
) -> tuple[int, int]:
    """Every unpushed question as a task: how many were pushed, and how many already had been.

    Each row is committed the moment its task exists, one at a time. Both counts come out of one
    read block, because the second is the first subtracted from what the store holds and a second
    query for it could be answered after the push had already changed the answer.
    """
    with sessions() as reading:
        waiting = unpushed_questions(reading)
        held = len(list(reading.scalars(select(Question.question_id))))
    for question_id, payload in waiting:
        task_id = tool.posted_task(project_id, payload)
        with sessions.begin() as writing:
            writing.add(
                Publication(
                    question_id=question_id,
                    external_system=EXTERNAL_SYSTEM,
                    external_project_id=project_id,
                    external_task_id=task_id,
                    status=PUSHED,
                    pushed_at=datetime.now(UTC),
                )
            )
    return len(waiting), held - len(waiting)


def answers_pulled(
    sessions: sessionmaker[Session], tool: AnnotationTool
) -> tuple[int, int]:
    """Every annotation on every pushed task, written once: how many were new, how many were not.

    A cancelled annotation is pulled like any other and stored as `was_skipped` (Requirement 50):
    a person declining a question is evidence about that question, and dropping it here would lose
    the rate the pilot reads.
    """
    with sessions() as reading:
        tasks = pushed_task_ids(reading)
        already = pulled_annotation_ids(reading)
    written, seen_before = 0, 0
    for question_id, task_id in tasks:
        for annotation in tool.annotations_on(task_id):
            if annotation.annotation_id in already:
                seen_before += 1
                continue
            with sessions.begin() as writing:
                writing.add(
                    AnnotatorAnswer(
                        answer_id=answer_id_for(annotation.annotation_id),
                        question_id=question_id,
                        annotator_id=annotation.annotator_id,
                        result=list(annotation.result),
                        was_skipped=annotation.was_cancelled,
                        lead_time_seconds=annotation.lead_time_seconds,
                        submitted_at=annotation.submitted_at,
                        external_annotation_id=annotation.annotation_id,
                    )
                )
            already.add(annotation.annotation_id)
            written += 1
    return written, seen_before


def synced_with_label_studio(
    sessions: sessionmaker[Session], tool: AnnotationTool, project_id: str
) -> SyncCounts:
    """Questions out and annotations back, and what each direction did.

    Push before pull, because a task created on this run can already have been answered by the time
    the pull reaches it -- the other order would leave that answer for the next sync for no reason.
    """
    pushed, already_pushed = questions_pushed(sessions, tool, project_id)
    pulled, already_pulled = answers_pulled(sessions, tool)
    return SyncCounts(
        pushed=pushed,
        already_pushed=already_pushed,
        pulled=pulled,
        already_pulled=already_pulled,
    )
