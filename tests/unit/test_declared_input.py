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

from dataforce.core.manifest import Manifest
from dataforce.core.record import Record, TextPart
from dataforce.profiles.tool_decision import (
    data_quality,
    human_review,
    release,
    schema,
    utils,
)
from dataforce.profiles.tool_decision.ai_review import vote_consensus
from dataforce.profiles.tool_decision.schema import OPENAI_TOOLS, SourceContract
from dataforce.profiles.tool_decision.utils import answer_distance, read_source_contract

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


def declared_record() -> Record:
    raw = {**declared_item(), data_quality.PROVENANCE_KEY: PROVENANCE}
    return data_quality.build_record(raw, TEXT.content_parts(raw), CANONICAL)


@pytest.fixture
def record() -> Record:
    return declared_record()


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

    first = {**item, data_quality.PROVENANCE_KEY: PROVENANCE}
    second = {**reordered, data_quality.PROVENANCE_KEY: PROVENANCE}

    assert (
        data_quality.build_record(first, TEXT.content_parts(first), CANONICAL).rid
        == data_quality.build_record(second, TEXT.content_parts(second), CANONICAL).rid
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
    assert release.scenario_hash(record, contract) == utils.catalog_hash(OFFERED)


# --- the five checks over the declared shape ----------------------------------


def test_the_declared_input_passes_every_validity_check(record: Record) -> None:
    """The point of the fixture: a well-formed item in the shape the spec declares is
    not quarantined by a check written when the answer was an array of names."""
    checks = data_quality.validity_checks(CANONICAL, answer_ceiling=3)

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
    checks = data_quality.validity_checks(CANONICAL, answer_ceiling=3)
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


# --- δ and consensus over the declared shape ----------------------------------


def wrong_argument() -> list[dict[str, Any]]:
    """The target with one of its two arguments changed. A human fixes this in a second."""
    return [
        {
            "name": "SendStatement",
            "arguments": {"ma_khach": "480215", "ky": "thang_truoc"},
        }
    ]


def wrong_tool() -> list[dict[str, Any]]:
    return [{"name": "OpenTicket", "arguments": {"ly_do": "khách hỏi sao kê"}}]


def test_a_wrong_argument_is_nearer_than_a_wrong_tool() -> None:
    """Requirement 72 on the input this is for, not only on a synthetic pair.

    This is the ordering every triage bucket and every cohesion figure is written on:
    the jury calling the right tool with one argument wrong is a different kind of
    record from the jury calling the wrong tool, and δ has to say so.
    """
    assert answer_distance(TARGET, TARGET) == 0.0
    assert answer_distance(TARGET, wrong_argument()) == pytest.approx(0.5)
    assert answer_distance(TARGET, wrong_tool()) == 1.0
    assert answer_distance(TARGET, []) == 1.0


def test_dropping_the_arguments_makes_the_target_a_names_only_answer(
    record: Record,
) -> None:
    """The reduction, on this record: with arguments off both sides, δ is Jaccard."""
    names_only = [{"name": "SendStatement"}]

    assert answer_distance(names_only, ["SendStatement"]) == 0.0
    assert answer_distance(names_only, ["OpenTicket"]) == 1.0


def test_three_jurors_splitting_on_one_argument_agree_on_the_majority_value(
    record: Record, contract: SourceContract
) -> None:
    """Requirement 74 against a real catalog, where `ky` and `ma_khach` are both
    `required` -- so a split that left either without a majority would drop the call."""
    catalog = utils.record_catalog(record, contract)
    votes = [TARGET, TARGET, wrong_argument()]

    assert vote_consensus(votes, catalog) == TARGET


def test_a_required_argument_the_jurors_never_agreed_on_drops_the_call(
    record: Record, contract: SourceContract
) -> None:
    """`SendStatement` declares both arguments `required`, so a three-way split on
    `ma_khach` leaves nothing that would validate -- and a dropped call is the answer,
    not a call carrying one juror's guess."""
    catalog = utils.record_catalog(record, contract)
    votes = [
        [
            {
                "name": "SendStatement",
                "arguments": {"ma_khach": "111111", "ky": "thang_nay"},
            }
        ],
        [
            {
                "name": "SendStatement",
                "arguments": {"ma_khach": "222222", "ky": "thang_nay"},
            }
        ],
        [
            {
                "name": "SendStatement",
                "arguments": {"ma_khach": "333333", "ky": "thang_nay"},
            }
        ],
    ]

    assert vote_consensus(votes, catalog) == []


def test_a_consensus_call_is_inside_the_record_s_own_answer_space(
    record: Record, contract: SourceContract
) -> None:
    """The tie between requirements 74 and 71: what consensus emits has to be a thing
    the record could have answered, or the ranking signal is built on an invalid call."""
    catalog = utils.record_catalog(record, contract)

    consensus = vote_consensus([TARGET, TARGET, wrong_argument()], catalog)

    assert accepts(space_for(record), consensus)


# --- requirement 75: capturing a compound answer ------------------------------


def control_for(record: Record, contract: SourceContract, which: str) -> str:
    return human_review.answer_config(record, contract, control=which)


def test_the_form_control_offers_every_name_and_no_others(
    record: Record, contract: SourceContract
) -> None:
    built = control_for(record, contract, human_review.PER_NAME_ARGUMENTS)

    # Inside the name control only: an argument with a declared `enum` contributes
    # `<Choice>` elements of its own, and those are a different question.
    names = built.split('<Choices name="tools"')[1].split("</Choices>")[0]

    assert names.count("<Choice ") == 3
    for name in OFFERED:
        assert f'value="{name}"' in names
    assert "DeleteAccount" not in built


def test_each_tool_s_arguments_are_shown_only_when_that_tool_is_picked(
    record: Record, contract: SourceContract
) -> None:
    """What makes this a form rather than a wall of fields: an annotator cannot state
    an argument for a tool they did not call, so an out-of-space answer is harder to
    express than to avoid."""
    built = control_for(record, contract, human_review.PER_NAME_ARGUMENTS)

    assert 'name="SendStatement.ky"' in built
    assert 'name="SendStatement.ma_khach"' in built
    assert 'name="OpenTicket.ly_do"' in built
    assert built.count('visibleWhen="choice-selected"') == 4
    assert 'whenChoiceValue="SendStatement"' in built


def test_an_argument_the_tool_constrains_is_a_closed_choice_not_free_text(
    record: Record, contract: SourceContract
) -> None:
    """`ky` declares an `enum`, so the control that captures it declares one too --
    otherwise the surface would accept a value the answer space rejects, and the
    annotator would only find out at pull time."""
    built = control_for(record, contract, human_review.PER_NAME_ARGUMENTS)

    assert '<Choices name="SendStatement.ky"' in built
    assert 'value="thang_nay"' in built
    assert 'value="thang_truoc"' in built
    assert '<TextArea name="SendStatement.ky"' not in built


def test_the_fallback_is_one_text_control_and_names_no_tool(
    record: Record, contract: SourceContract
) -> None:
    """The declared fallback for a tool that cannot show a field conditionally. It can
    express any answer at all, which is why requirement 75 pairs it with validation at
    pull time rather than treating the two controls as equivalent."""
    built = control_for(record, contract, human_review.JSON_TEXT)

    assert "<TextArea " in built
    assert "<Choices " not in built
    assert "SendStatement.ky" not in built


def test_which_control_ships_is_declared_and_not_guessed() -> None:
    """Requirement 75's last clause: it is on the profile, so `publish` can stamp it.

    An annotator who filled in a form and one who hand-wrote JSON were not asked the
    same question, so an agreement figure is only readable next to which surface
    produced it.
    """
    assert TOOL_DECISION.answer_control in human_review.CONTROLS

    with pytest.raises(Exception, match="not an answer control"):
        human_review.answer_config(
            declared_record(), CANONICAL, control="a_third_thing"
        )


def test_no_control_carries_anything_a_model_produced(
    record: Record, contract: SourceContract
) -> None:
    """Invariant 10 does not soften because the control got richer. Everything in
    either control comes from the record's own catalog, and the record's `meta` carries
    a `label_source` naming what labelled it -- which must not reach the page."""
    for which in human_review.CONTROLS:
        built = control_for(record, contract, which)

        assert "debait" not in built
        assert "480215" not in built
        assert str(record.label) not in built


def test_the_form_control_escapes_a_name_that_would_break_the_attribute(
    record: Record, contract: SourceContract
) -> None:
    """Argument field names are built from tool names, so they are escaped on the same
    terms -- a name is source data and the field name is now derived from it."""
    hostile = record.model_copy(
        update={
            "meta": {
                **record.meta,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": 'Send" onclick="steal()',
                            "description": "",
                            "parameters": {
                                "type": "object",
                                "properties": {"ky": {"type": "string"}},
                            },
                        },
                    }
                ],
            }
        }
    )

    built = control_for(hostile, contract, human_review.PER_NAME_ARGUMENTS)

    assert 'onclick="steal()"' not in built
    assert "&quot;" in built
