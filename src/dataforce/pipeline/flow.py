"""DEFINITION · PHASES and STAGES — the flow table, in code, once.

The one place in code that this table exists. ``tests/guards/test_flow_table.py`` parses the same
table out of ``docs/annotation-pipeline/spec.md`` and compares the two, so neither side can move
alone (I3, P31).

Fifteen stages. Stages 0-11 have a module; ``release`` is declared here so the flow is complete
and the record's ``release`` key has an owner, and is specified in a follow-up.
"""

from typing import NamedTuple


class Stage(NamedTuple):
    """One row of the flow: what runs, where in the order, and which phase it belongs to."""

    number: int  # its position in the whole flow, 0-14; the number a `STEP ·` docstring names
    phase: (
        str  # the main endpoint it runs under, and the record key its output lands in
    )
    stage: str  # the service: its module name, its sub-endpoint, its CLI subcommand
    summary: str  # what it does, in the words spec.md § *The flow* uses


STAGES: tuple[Stage, ...] = (
    Stage(
        0,
        "load_data",
        "load_data",
        "every source item becomes one record with identity, content and provenance",
    ),
    Stage(
        1,
        "data_quality",
        "label_check",
        "the five checks on the label that need no opinion",
    ),
    Stage(
        2,
        "data_quality",
        "pii_check",
        "two-layer detection, typed placeholders, content rewritten",
    ),
    Stage(
        3,
        "data_quality",
        "duplicate_check",
        "exact and near-duplicate groups, split by label agreement",
    ),
    Stage(4, "ai_review", "jury", "N independent models answer the record's own task"),
    Stage(
        5,
        "ai_review",
        "cohesion",
        "how much the jury agrees with itself, and with the existing label",
    ),
    Stage(
        6,
        "ai_review",
        "triage",
        "the two numbers become a bucket, a stratum and a review quota",
    ),
    Stage(
        7,
        "human_review",
        "question_generate",
        "one answerable question per flagged record, with its evidence",
    ),
    Stage(
        8,
        "human_review",
        "publish",
        "questions written to the question store, ready for the annotation tool",
    ),
    Stage(
        9,
        "human_review",
        "annotator_answers",
        "responses read back out of the store onto the record",
    ),
    Stage(
        10,
        "human_review",
        "aggregate",
        "overlap becomes one verdict with a confidence and an agreement statistic",
    ),
    Stage(
        11,
        "human_review",
        "curate",
        "the verdict becomes the record's final label, or an adjudication",
    ),
    Stage(
        12,
        "release",
        "split",
        "train / validation / test, with no scenario on both sides",
    ),
    Stage(13, "release", "export", "the trainer-shaped artifact, per profile"),
    Stage(14, "release", "datasheet", "one document stating how the dataset was made"),
)

# The distinct phases of the flow, in the flow's order. Derived rather than listed, because a
# phase written down twice is a phase that can disagree with itself (P16: one key, one writer).
PHASES: tuple[str, ...] = tuple(dict.fromkeys(stage.phase for stage in STAGES))

# The last stage with a module. Above it is `release`, declared and unbuilt; the guard reads the
# same boundary out of the spec's own "Stages 0-11 are in scope" and compares the two.
LAST_IN_SCOPE_STAGE = 11
