"""T14 · load_data: what one source item becomes, and what an unreadable one becomes instead.

The first stage, and the only one whose input is not the bus -- so the row it is asserted against
is § *Per-service contracts*' row 0 rather than a reads/writes/skips-when triple: it writes the
whole record, it skips nothing, and the one thing that stops it is a source digest that is not the
declared one.

**Two things are proved here that no other module can prove.** That provenance is the edge's and
travels with the record (Requirement 12, Decision 4) -- nothing in the engine has a clock, so a
record's `ingested_at` is only ever what a caller handed over, and that is what makes HTTP and an
in-process call produce the same record (Requirement 46). And that an item which cannot be read is
*counted*, which is the decision T44 deferred to this task: `build_record` and `content_parts` both
raise while records are being read, Requirement 43 permits that only before, and this is the only
caller that knows the offset.

The axes are the real ones, built through the fixtures in `test_tool_decision.py`: a stage that
reads content through a double would prove the double. Every fixture is invented.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from dataforce.engine import Engine, Registry
from dataforce.errors import ConfigError
from dataforce.pipeline.load_data import load_data
from dataforce.pipeline.runner import run_phase
from dataforce.record import Record, record_id_for

from .test_tool_decision import (
    CATALOG,
    LOOKED_UP,
    SENT,
    TURNS,
    a_profile,
    a_text2text,
    an_item,
)

DIGEST = "b" * 64
INGESTED = datetime(2026, 8, 24, tzinfo=UTC)
RUN = "r_2026-08-24T00:00:00Z_9f3c"


def an_engine(thresholds: Mapping[str, Any] | None = None, **declared: Any) -> Engine:
    """What `edge/bootstrap.py` will hand this stage: both axes resolved, and `params.yaml`."""
    modality = a_text2text()
    profile = a_profile(**declared)
    registry = Registry()
    registry.register_modality(modality.modality_name, modality)
    registry.register_profile(profile.profile_name, profile)
    return Engine(
        modality=modality,
        profile=profile,
        registry=registry,
        thresholds=thresholds if thresholds is not None else {},
        policy_digests={"params.yaml": "a1b2c3d4"},
    )


def loaded(
    *items: Mapping[str, Any], engine: Engine | None = None
) -> tuple[tuple[Record, ...], Mapping[str, Any]]:
    """One call, with the three things only the edge knows, and both halves of what came back."""
    ran = load_data(
        engine or an_engine(),
        items,
        source_file_sha256=DIGEST,
        ingested_at=INGESTED,
        run_id=RUN,
    )
    return ran.records, ran.side_output


def a_conversation_that_already_called(name: str) -> list[dict[str, Any]]:
    """Turns holding a completed `tool_call`, which is context and not an answer (Requirement 13)."""
    return [
        *({"role": role, "content": text} for role, text in TURNS),
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"function": {"name": name, "arguments": '{"ma_khach": "480215"}'}}
            ],
        },
    ]


# --- one item, one record ---


def test_every_source_item_becomes_one_record() -> None:
    """Row 0: the whole record, one per item, in the order they were handed over."""
    records, _ = loaded(an_item(id="s1"), an_item(id="s2"), an_item(id="s3"))

    assert [record.source_id for record in records] == ["s1", "s2", "s3"]


def test_the_record_is_joined_on_its_content_and_nothing_else() -> None:
    """Requirement 6: `record_id` is over the content the modality read (I9 proves the rest)."""
    item = an_item()
    records, _ = loaded(item)

    assert records[0].record_id == record_id_for(a_text2text().content_parts(item))
    assert records[0].content_version == 1


def test_provenance_carries_what_only_the_edge_could_know() -> None:
    """Requirement 12 and Decision 4, field by field: the engine has no clock and no path."""
    records, _ = loaded(an_item())

    assert records[0].provenance.source_file_sha256 == DIGEST
    assert records[0].provenance.ingested_at == INGESTED
    assert records[0].provenance.run_id == RUN
    assert records[0].provenance.modality == "text2text@1"
    assert records[0].provenance.profile == "tool_decision@1"


def test_the_offset_is_the_item_s_position_in_what_this_call_was_handed() -> None:
    """What makes one item re-readable on its own. A shuffle moves it; `record_id` ignores it."""
    records, _ = loaded(an_item(id="s1"), an_item(id="s2"))

    assert [record.provenance.offset for record in records] == [0, 1]


def test_two_calls_with_one_stamp_produce_the_same_record() -> None:
    """Requirement 46: nothing here reads a clock, so both shells can produce one record."""
    first, _ = loaded(an_item())
    again, _ = loaded(an_item())

    assert first == again


# --- the answer is the declared key, and never a call in the conversation ---


def test_a_completed_tool_call_in_the_conversation_is_not_the_answer() -> None:
    """`meta.label` is the answer and nothing else is: an extractor scraping the turns is wrong.

    The fixture is the case that makes the two disagree -- the conversation ends by calling
    `LookupBalance` and the declared label names `SendStatement` -- so a record whose label came
    from the turns would be visible here rather than only in a corpus nobody has yet.
    """
    item = an_item(messages=a_conversation_that_already_called("LookupBalance"))

    records, _ = loaded(item)

    assert records[0].label == (SENT,)
    assert records[0].label != (LOOKED_UP,)


def test_the_catalog_stays_source_data_and_is_never_an_answer_space() -> None:
    """I10: `answer_schema` materialises one from the record; a stored space is the stale copy."""
    records, _ = loaded(an_item())

    assert records[0].meta["tools"] == CATALOG
    assert "answer_space" not in Record.model_fields


# --- an item that cannot be read ---


def test_an_item_that_cannot_be_read_is_counted_and_the_others_still_load() -> None:
    """T44's deferred decision, settled here: a run of twenty thousand does not stop for one."""
    unlabelled = an_item(id="s2", meta={"target": [SENT]})

    records, written = loaded(an_item(id="s1"), unlabelled, an_item(id="s3"))

    assert [record.source_id for record in records] == ["s1", "s3"]
    assert written["load_data"]["unreadable"] == (
        {
            "offset": 1,
            "reason": (
                "config/profiles/tool_decision.yaml declares the answer at meta.label; "
                "the item at offset 1 carries ['target']"
            ),
        },
    )


@pytest.mark.parametrize(
    ("item", "reason"),
    [
        pytest.param(an_item(messages="xin chào"), "messages", id="turns-not-a-list"),
        pytest.param(
            an_item(messages=[{"content": "xin chào"}]), "role", id="turn-with-no-role"
        ),
        pytest.param(an_item(meta={}), "meta.label", id="no-declared-label"),
    ],
)
def test_all_three_raises_below_this_stage_become_counted_items(
    item: Mapping[str, Any], reason: str
) -> None:
    """The three § *Error Behavior* names, each caught where the offset is known."""
    records, written = loaded(item)

    assert records == ()
    assert reason in written["load_data"]["unreadable"][0]["reason"]


def test_a_batch_that_reads_cleanly_leaves_the_edge_nothing_to_write() -> None:
    """Side output is what the edge must *persist*; an empty quarantine file says nothing."""
    _, written = loaded(an_item(), an_item())

    assert written == {}


# --- the one thing that stops a run before it starts ---


def test_a_source_that_is_not_the_declared_one_refuses_to_run() -> None:
    """§ *Error Behavior* row 1, and the one place Requirement 43 permits a stop."""
    declared = an_engine({"source": {"path": "", "sha256": "c" * 64}})

    with pytest.raises(ConfigError, match="params.yaml declares"):
        loaded(an_item(), engine=declared)


def test_no_declared_source_is_not_a_mismatch() -> None:
    """`params.source` is empty until a corpus is declared, which is every run built so far."""
    undeclared = an_engine({"source": {"path": "", "sha256": ""}})

    records, _ = loaded(an_item(), engine=undeclared)

    assert len(records) == 1


def test_a_declared_digest_that_is_not_a_digest_is_refused_before_any_item() -> None:
    """The params reader's own rule: a wrong *type* is a `ConfigError` where it is read."""
    mistyped = an_engine({"source": {"sha256": ["b" * 64]}})

    with pytest.raises(ConfigError, match="source.sha256"):
        loaded(an_item(), engine=mistyped)


def test_the_run_refuses_to_read_this_stage_off_the_bus() -> None:
    """`flow.FROM_SOURCE`: a phase endpoint folding this one would hand it records."""
    with pytest.raises(ConfigError, match="source items"):
        run_phase(an_engine(), "load_data", [])
