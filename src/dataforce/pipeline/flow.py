"""DEFINITION · PHASES and STAGES — the flow table, in code, once.

The one place in code that this table exists. ``tests/guards/test_flow_table.py`` parses the same
table out of ``docs/annotation-pipeline/spec.md`` and compares the two, so neither side can move
alone (I3, P31).

**A stage has a name, not a number.** ``STAGES`` is a tuple and a tuple already knows its order, so
a number is the same fact written a second time and the second copy is the one that goes wrong
(P16). It is also a *shared* index: inserting a stage renumbers every stage after it -- here, in
each ``STEP ·`` docstring, and through half the spec -- for a change that is one row. Scope is
named rather than cut at a number: ``DECLARED_ONLY`` holds the phases that are in the flow and
have no module (Decision 19).
"""

from typing import NamedTuple


class Stage(NamedTuple):
    """One row of the flow: what runs, and under which phase. Order is its place in ``STAGES``."""

    phase: (
        str  # the main endpoint it runs under, and the record key its output lands in
    )
    stage: str  # the service: its module name, its sub-endpoint, its CLI subcommand
    summary: str  # what it does, in the words spec.md § *The flow* uses


STAGES: tuple[Stage, ...] = (
    Stage(
        "load_data",
        "load_data",
        "every source item becomes one record with identity, content and provenance",
    ),
    Stage(
        "data_quality",
        "label_check",
        "the five checks on the label that need no opinion",
    ),
    Stage(
        "data_quality",
        "pii_check",
        "two-layer detection, typed placeholders, content rewritten",
    ),
    Stage(
        "data_quality",
        "duplicate_check",
        "exact and near-duplicate groups, split by label agreement",
    ),
    Stage("ai_review", "jury", "N independent models answer the record's own task"),
    Stage(
        "ai_review",
        "cohesion",
        "how much the jury agrees with itself, and with the existing label",
    ),
    Stage(
        "ai_review",
        "triage",
        "the two numbers become a bucket, a stratum and a review quota",
    ),
    Stage(
        "human_review",
        "question_generate",
        "one answerable question per flagged record, with its evidence",
    ),
    Stage(
        "human_review",
        "publish",
        "questions written to the question store, ready for the annotation tool",
    ),
    Stage(
        "human_review",
        "annotator_answers",
        "responses read back out of the store onto the record",
    ),
    Stage(
        "human_review",
        "aggregate",
        "overlap becomes one verdict with a confidence and an agreement statistic",
    ),
    Stage(
        "human_review",
        "curate",
        "the verdict becomes the record's final label, or an adjudication",
    ),
    Stage(
        "release",
        "split",
        "train / validation / test, with no scenario on both sides",
    ),
    Stage("release", "export", "the trainer-shaped artifact, per profile"),
    Stage("release", "datasheet", "one document stating how the dataset was made"),
)

# The distinct phases of the flow, in the flow's order. Derived rather than listed, because a
# phase written down twice is a phase that can disagree with itself (P16: one key, one writer).
PHASES: tuple[str, ...] = tuple(dict.fromkeys(stage.phase for stage in STAGES))

# The one phase whose stage does not read the bus. `load_data` is handed source items and mints
# the records every other stage folds over, so there is nothing for `run_phase` to give it and its
# signature is not § *Shared decisions*' one signature. `POST /load-data` is its own route for the
# same reason, and § *Per-service contracts* records the break where a reader hits it (§8).
FROM_SOURCE: tuple[str, ...] = ("load_data",)

# The phases that are in the flow and have no module -- declared so the record's key has an owner,
# specified in a follow-up. Every other phase's stages are built. The guard reads the same names
# out of the spec's own "Declared, not built" sentence and compares the two.
DECLARED_ONLY: tuple[str, ...] = ("release",)
