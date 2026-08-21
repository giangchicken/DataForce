"""The answer space: derived from a record's own catalog, and stored nowhere.

Requirement 71. `ANSWER_SCHEMA` is the answer *type*, which choosing this profile
already settles; `answer_space` is one record's *space*, which its catalog
settles. The tests below are about the difference, because the first draft of the
requirement said the record should carry a copy and the measurement reversed it.

`jsonschema` is used rather than assertions about the schema's shape on purpose: what
has to be true is that the schema *means* "this name with these arguments", and a test
that only checked for a `const` key would pass on a schema that validated nothing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import TEXT, TOOL_DECISION
from jsonschema import Draft202012Validator

from dataforce.profiles.tool_decision import schema, utils

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "tool_decision"
CATALOGS = FIXTURES / "catalogs"

BALANCE = schema.Tool(
    name="LookupBalance",
    description="Tra cứu số dư tài khoản của khách hàng.",
    parameters={
        "type": "object",
        "properties": {"ma_khach": {"type": "string"}},
        "required": ["ma_khach"],
        "additionalProperties": False,
    },
)
TICKET = schema.Tool(
    name="OpenTicket",
    description="Mở phiếu hỗ trợ.",
    parameters={
        "type": "object",
        "properties": {"ly_do": {"type": "string"}},
        "required": ["ly_do"],
        "additionalProperties": False,
    },
)
TWO_TOOLS = schema.Catalog(tools=(BALANCE, TICKET))


def accepts(space: dict[str, Any], answer: Any) -> bool:
    return Draft202012Validator(space).is_valid(answer)


# --- what the space means -----------------------------------------------------


def test_a_call_the_catalog_offers_with_the_arguments_it_declares_is_in_the_space() -> (
    None
):
    space = schema.answer_space(TWO_TOOLS)

    assert accepts(space, [{"name": "LookupBalance", "arguments": {"ma_khach": "480"}}])
    assert accepts(space, [{"name": "OpenTicket", "arguments": {"ly_do": "chưa nhận"}}])


def test_the_empty_answer_is_in_every_space() -> None:
    """35.4% of the reference source, and a first-class answer rather than a missing one."""
    assert accepts(schema.answer_space(TWO_TOOLS), [])


def test_a_name_the_catalog_does_not_offer_is_outside_the_space() -> None:
    space = schema.answer_space(TWO_TOOLS)

    assert not accepts(space, [{"name": "SendMail", "arguments": {}}])


def test_a_name_and_its_arguments_are_constrained_together_not_separately() -> None:
    """The case an `enum` of names beside a free-form argument object cannot state.

    `OpenTicket` carrying `LookupBalance`'s argument is two valid halves and one
    invalid call, which is the whole reason each branch of the `oneOf` closes over one
    tool's own `parameters`.
    """
    space = schema.answer_space(TWO_TOOLS)

    assert not accepts(
        space, [{"name": "OpenTicket", "arguments": {"ma_khach": "480"}}]
    )


def test_arguments_that_violate_the_tool_s_own_schema_are_outside_the_space() -> None:
    space = schema.answer_space(TWO_TOOLS)

    assert not accepts(space, [{"name": "LookupBalance", "arguments": {}}])
    assert not accepts(
        space, [{"name": "LookupBalance", "arguments": {"ma_khach": 480}}]
    )


def test_an_empty_catalog_permits_exactly_one_answer() -> None:
    """Spelled `maxItems` because an empty `oneOf` is not a schema."""
    space = schema.answer_space(schema.Catalog(tools=()))

    assert accepts(space, [])
    assert not accepts(space, [{"name": "LookupBalance", "arguments": {}}])


def test_a_tool_declaring_no_parameters_is_called_with_none() -> None:
    quiet = schema.Catalog(tools=(schema.Tool(name="Escalate", description="Chuyển."),))
    space = schema.answer_space(quiet)

    assert accepts(space, [{"name": "Escalate"}])
    assert accepts(space, [{"name": "Escalate", "arguments": {}}])


# --- the type, as against one record's space ----------------------------------


def test_the_declared_answer_type_is_calls_not_names() -> None:
    """What choosing the profile settles, and what `profile.answer_schema` is."""
    assert accepts(TOOL_DECISION.answer_schema, [{"name": "Anything", "arguments": {}}])
    assert accepts(TOOL_DECISION.answer_schema, [])
    assert not accepts(TOOL_DECISION.answer_schema, ["Anything"])


def test_the_type_constrains_no_name_and_the_space_does() -> None:
    """The division of labour requirement 71 draws: type from the profile, space from
    the record. A schema that knew both would have to be built per record and would
    then be the space, leaving the type with nothing to be."""
    outside = [{"name": "NotInAnyCatalog", "arguments": {}}]

    assert accepts(TOOL_DECISION.answer_schema, outside)
    assert not accepts(schema.answer_space(TWO_TOOLS), outside)


# --- the size claim -----------------------------------------------------------


@pytest.fixture
def eight_tool_record() -> Any:
    raw = {
        "messages": [
            {
                "role": "system",
                "content": (CATALOGS / "eight_tools.txt").read_text(encoding="utf-8"),
            },
            {"role": "user", "content": "cho mình hỏi"},
            {"role": "assistant", "content": "[]"},
        ],
        "meta": {"label": []},
        "__provenance__": {
            "source": {
                "file_sha256": "0" * 64,
                "offset": 0,
                "ingested_at": "2026-08-21T00:00:00Z",
            },
            "producer": {"modality": "text@1", "profile": "tool_decision@1"},
        },
    }
    return TOOL_DECISION.build_record(raw, TEXT.content_parts(raw))


def test_no_record_carries_an_answer_space_and_the_compound_one_is_bigger(
    eight_tool_record: Any,
) -> None:
    """Requirement 71's measurement, as an assertion rather than a paragraph.

    A stored compound space would have been the largest column on every row -- larger
    than the catalog it is derived from, which is a copy bigger than the original. The
    names-only field it replaced was small, which is exactly why storing it looked
    free and why the honest comparison is against the space this profile now has.
    """
    written = eight_tool_record.model_dump()
    assert "answer_space" not in written

    names = utils.catalog_names(eight_tool_record, TOOL_DECISION.contract)
    assert len(names) == 8

    would_have_stored = json.dumps(
        {"type": "array", "items": {"type": "string", "enum": names}}
    )
    derived = json.dumps(TOOL_DECISION.answer_space(eight_tool_record))

    assert len(derived) > len(would_have_stored)
