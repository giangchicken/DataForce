"""The input this pipeline is *for*, taken from the spec's own worked example.

Every other test in this directory reads a fixture shaped like the reference source --
one whose catalog is rendered into a system prompt and whose answer is a bare array of
names. That source is what Phases 1 and 2 were verified against; it is **not** the
input. `docs/annotation-pipeline/spec.md` § *One item, all the way through* declares
what is: `tools` as data, a conversation of as many turns as it takes, and an answer
that is a set of calls with the arguments they are called with.

`declared_input.json` is that item, copied from the document so the two cannot drift.
Invented, like every fixture here -- the reference corpus is call-centre transcript
carrying spoken personal data, and this repository is public.

What the tests below assert is the whole path over that shape: the two call turns render
canonically and the string turns do not move, the catalog is read from `tools` without a
parse, the label is a call, the five checks read it, and the answer space accepts the
target and rejects each way of getting it wrong.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import TEXT, TOOL_DECISION
from jsonschema import Draft202012Validator

from dataforce.profiles.tool_decision import build_record, schema, utils
from dataforce.profiles.tool_decision.source_contract import (
    OPENAI_TOOLS,
    SourceContract,
    read_source_contract,
)
from dataforce.shared.manifest import Manifest
from dataforce.shared.record import Record, TextPart

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "tool_decision"

PROVENANCE = {
    "source": {
        "file_sha256": "7c0d4e19b2a8f3" + "0" * 50,
        "offset": 4471,
        "ingested_at": "2026-08-21T09:14:02Z",
    },
    "producer": {"modality": "text@1", "profile": "tool_decision@1"},
}

# The two calls as requirement 70 renders them, quoted from the spec's § 3 canonical
# record. Written out rather than computed: a test that rendered them the same way the
# code does would agree with a bug.
LOOKUP_TURN = '[{"arguments":{"ma_khach":"480215"},"name":"LookupBalance"}]'
TARGET_TURN = (
    '[{"arguments":{"ky":"thang_nay","ma_khach":"480215"},"name":"SendStatement"}]'
)

OFFERED = ["LookupBalance", "SendStatement", "OpenTicket"]
TARGET = [
    {"name": "SendStatement", "arguments": {"ma_khach": "480215", "ky": "thang_nay"}}
]


CANONICAL = read_source_contract(
    Manifest(
        name="declared_input",
        version="1",
        declared={
            "shape": OPENAI_TOOLS,
            "roles": {
                "instruction": "system",
                "conversation": ["user"],
                "target": "assistant",
            },
            "label": {"at": "label"},
            "meta": {},
        },
    )
)


def declared_item() -> dict[str, Any]:
    loaded: list[dict[str, Any]] = json.loads(
        (FIXTURES / "declared_input.json").read_text(encoding="utf-8")
    )
    return loaded[0]


@pytest.fixture
def record() -> Record:
    raw = {**declared_item(), build_record.PROVENANCE_KEY: PROVENANCE}
    return build_record.build_record(raw, TEXT.content_parts(raw), CANONICAL)


@pytest.fixture
def contract() -> SourceContract:
    return CANONICAL


# --- the turns ----------------------------------------------------------------


def test_nine_turns_become_nine_parts_in_order(record: Record) -> None:
    """Multi-turn is the normal case, and `tool` is a role like any other."""
    assert [part.role for part in record.content] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
        "tool",
        "assistant",
        "user",
        "assistant",
    ]
    assert all(part.type == "text" for part in record.content)


def test_the_two_call_turns_are_the_canonical_json_the_spec_prints(
    record: Record,
) -> None:
    parts = [part for part in record.content if isinstance(part, TextPart)]

    assert parts[4].text == LOOKUP_TURN
    assert parts[8].text == TARGET_TURN


def test_the_tool_result_is_copied_byte_for_byte(record: Record) -> None:
    """It was already a string, so requirement 70 does not touch it -- and the space
    after the colon is the proof, because normalising would have closed it."""
    parts = [part for part in record.content if isinstance(part, TextPart)]

    assert parts[5].text == '{"so_du": 1250000}'


def test_no_call_turn_carries_the_provider_s_request_id(record: Record) -> None:
    """`c1` and `c2` are per-request. In `rid` they would make two ingests two records."""
    assert not any(
        "c1" in part.text or "c2" in part.text
        for part in record.content
        if isinstance(part, TextPart)
    )


def test_rid_is_stable_across_a_reordered_spelling_of_the_same_calls() -> None:
    """Invariant 2 over the declared shape, not just over a single synthetic turn."""
    item = declared_item()
    reordered = json.loads(json.dumps(item))
    for turn in reordered["messages"]:
        for call in turn.get("tool_calls") or []:
            given = json.loads(call["function"]["arguments"])
            call["function"]["arguments"] = json.dumps(
                dict(reversed(list(given.items()))), indent=2
            )

    first = {**item, build_record.PROVENANCE_KEY: PROVENANCE}
    second = {**reordered, build_record.PROVENANCE_KEY: PROVENANCE}

    assert (
        build_record.build_record(first, TEXT.content_parts(first), CANONICAL).rid
        == build_record.build_record(second, TEXT.content_parts(second), CANONICAL).rid
    )


# --- the catalog and the answer -----------------------------------------------


def test_the_catalog_is_read_from_tools_with_no_parse(
    record: Record, contract: SourceContract
) -> None:
    assert utils.catalog_names(record, contract) == OFFERED
    assert utils.CATALOG_HEADER not in record.content[0].text


def test_each_offered_tool_keeps_its_own_parameters(
    record: Record, contract: SourceContract
) -> None:
    """What an argument is checked against, and the reason no answer space is stored."""
    catalog = utils.record_catalog(record, contract)
    statement = next(tool for tool in catalog.tools if tool.name == "SendStatement")

    assert statement.required == ("ma_khach", "ky")
    assert statement.properties["ky"]["enum"] == ["thang_nay", "thang_truoc"]


def test_the_label_is_a_call_with_the_arguments_it_teaches(record: Record) -> None:
    assert record.label == TARGET


def test_the_record_carries_no_answer_space(record: Record) -> None:
    assert "answer_space" not in record.model_dump()


def test_the_scenario_hash_is_the_hash_of_this_record_s_catalog(
    record: Record, contract: SourceContract
) -> None:
    assert build_record.scenario_hash(record, contract) == utils.catalog_hash(OFFERED)


# --- the five checks over the declared shape ----------------------------------


def test_the_declared_input_passes_every_validity_check(record: Record) -> None:
    """The point of the fixture: a well-formed item in the shape the spec declares is
    not quarantined by a check written when the answer was an array of names."""
    checks = build_record.validity_checks(CANONICAL, answer_ceiling=3)

    fired = [name for name, check in checks.items() if check(record)]

    assert fired == []


def test_the_target_turn_and_the_label_are_compared_through_delta(
    record: Record,
) -> None:
    """`label_assistant_mismatch` reads the canonical call turn and the label field.

    They agree here, which is what makes the check able to say when they do not: the
    turn is rendered JSON and the label is the source's own field, so the two are
    genuinely independent statements of one answer.
    """
    checks = build_record.validity_checks(CANONICAL, answer_ceiling=3)
    disagreeing = record.model_copy(
        update={"label": [{"name": "OpenTicket", "arguments": {"ly_do": "khác"}}]}
    )

    assert not checks["label_assistant_mismatch"](record)
    assert checks["label_assistant_mismatch"](disagreeing)


# --- the answer space over the declared shape ---------------------------------


def accepts(space: dict[str, Any], answer: Any) -> bool:
    return Draft202012Validator(space).is_valid(answer)


def space_for(record: Record) -> dict[str, Any]:
    """This record's answer space, read under the contract it was built with.

    Not `TOOL_DECISION.answer_schema_for` -- see the test below for why that would
    quietly return the empty-catalog schema here.
    """
    return schema.answer_schema_for(utils.record_catalog(record, CANONICAL))


def test_the_configured_profile_reads_one_shape_and_it_is_not_this_one(
    record: Record,
) -> None:
    """A profile object carries one source contract, and the committed one declares the
    *reference* source's shape -- `legacy_system_prompt`, catalog rendered into a prompt.

    Pointed at a declared-input record it finds no `TOOLS:` block and reports an empty
    catalog, which is honest rather than wrong: a run declares one source, and moving to
    the real input is a change to `config/profiles/tool_decision.yaml` and `params.yaml`
    together. What matters is that it is only those two -- no module spells either shape,
    so nothing in this phase has to change when the input arrives. This test is here so
    that fact is asserted rather than rediscovered.
    """
    assert TOOL_DECISION.contract.shape != OPENAI_TOOLS
    assert TOOL_DECISION.answer_schema_for(record) == {"type": "array", "maxItems": 0}

    assert accepts(space_for(record), TARGET)


def test_the_target_is_inside_the_space_this_record_derives(record: Record) -> None:
    assert accepts(space_for(record), TARGET)


@pytest.mark.parametrize(
    ("why", "answer"),
    [
        (
            "a name no tool in this catalog has",
            [{"name": "DeleteAccount", "arguments": {}}],
        ),
        (
            "a required argument missing",
            [{"name": "SendStatement", "arguments": {"ma_khach": "480215"}}],
        ),
        (
            "an argument outside the enum the tool declares",
            [
                {
                    "name": "SendStatement",
                    "arguments": {"ma_khach": "480215", "ky": "nam_nay"},
                }
            ],
        ),
        (
            "the right name carrying another tool's arguments",
            [{"name": "OpenTicket", "arguments": {"ma_khach": "480215"}}],
        ),
        ("a bare name, which is not the answer type", ["SendStatement"]),
    ],
)
def test_each_way_of_being_outside_the_space_is_outside_it(
    record: Record, why: str, answer: Any
) -> None:
    """Invariant 5. The pull gate rejects rather than truncating, so what "outside"
    means has to be exact for every one of these, not just for a wrong name."""
    assert not accepts(space_for(record), answer), why
