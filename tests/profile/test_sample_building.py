"""What a `tool_decision` sample ships as, and the four facets computed off what ships.

**`number_label_tools` is the one to read closely.** The no-call share and the calls-per-row
distribution are both read off that column and nothing downstream recounts them, so a test here is
the only thing holding it to the label it was computed from.

Every figure is asserted against what **ships** and not against what arrived, because the two
differ in every sample that went through a human or a redaction -- which is every sample.
"""

from typing import Any

import pytest

from dataforce.modalities.text2text.dataset_management import ShippedDatasetSample
from dataforce.profile.tool_decision.sample_building import ToolDecisionSampleBuilding

OPEN_TICKET: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "OpenTicket",
        "parameters": {
            "type": "object",
            "required": ["ma_khach"],
            "properties": {"ma_khach": {"type": "string"}, "note": {"type": "string"}},
        },
    },
}
LOOKUP: dict[str, Any] = {"type": "function", "function": {"name": "Lookup"}}
OPENED = {"name": "OpenTicket", "arguments": {"ma_khach": "KH-1"}}


def build_shipped(**overridden: Any) -> ShippedDatasetSample:
    """A sample as it ships: two turns, one tool offered, one call made."""
    parts: dict[str, Any] = {
        "messages": ({"role": "user", "content": "mở phiếu"}, {"role": "assistant"}),
        "tools": (OPEN_TICKET,),
        "label": (OPENED,),
    }
    return ShippedDatasetSample(**(parts | overridden))


@pytest.fixture
def building() -> ToolDecisionSampleBuilding:
    return ToolDecisionSampleBuilding()


def test_the_turns_and_the_catalog_ship_together_under_one_key(
    building: ToolDecisionSampleBuilding,
) -> None:
    """A tool call is a call *against a catalog*, so a label stored apart from the catalog it was
    written for is a label nothing can check -- `schema_valid` included."""
    assert building.build_input(build_shipped()) == {
        "messages": [{"role": "user", "content": "mở phiếu"}, {"role": "assistant"}],
        "tools": [OPEN_TICKET],
    }


def test_the_counts_are_of_what_ships(building: ToolDecisionSampleBuilding) -> None:
    """All four at once over one sample, because they describe the same row and a fixture that
    answered them one at a time could not show they agree."""
    assert building.compute_facets(build_shipped()) == {
        "number_turns": 2,
        "number_label_tools": 1,
        "number_provided_tools": 1,
        "schema_valid": True,
    }


def test_a_sample_that_called_nothing_counts_zero_calls_and_is_still_valid(
    building: ToolDecisionSampleBuilding,
) -> None:
    """*No tool call is needed* is an answer, not a skipped row: `0` is where the no-call share is
    read, and the column is the only place it is counted."""
    counted = building.compute_facets(build_shipped(label=()))

    assert counted["number_label_tools"] == 0
    assert counted["schema_valid"] is True


def test_an_absent_label_counts_the_same_as_an_empty_one(
    building: ToolDecisionSampleBuilding,
) -> None:
    """`()` and `None` are one reading -- no answer was needed -- and § *Open* has not yet said
    which of them a no-call sample writes, so the count may not depend on the answer."""
    assert building.compute_facets(build_shipped(label=None))["number_label_tools"] == 0


def test_two_calls_in_one_label_are_two(building: ToolDecisionSampleBuilding) -> None:
    """A turn answered by several calls at once, which is what the column's tail is for."""
    counted = building.compute_facets(
        build_shipped(
            tools=(OPEN_TICKET, LOOKUP),
            label=(OPENED, {"name": "Lookup", "arguments": {}}),
        )
    )

    assert counted["number_label_tools"] == 2
    assert counted["number_provided_tools"] == 2


def test_an_entry_naming_no_tool_is_not_a_call(
    building: ToolDecisionSampleBuilding,
) -> None:
    """One definition of what a call is, across the column and the validity check: the entry is
    not counted, and `schema_valid` is what says the row is broken."""
    counted = building.compute_facets(build_shipped(label=(OPENED, {"note": "oops"})))

    assert counted["number_label_tools"] == 1
    assert counted["schema_valid"] is False


def test_a_catalog_entry_nothing_can_read_is_not_a_tool_the_model_was_offered(
    building: ToolDecisionSampleBuilding,
) -> None:
    """The rendered catalog leaves it out and the validity check leaves it out, so counting it
    here would put a figure in the column that no other reading of the same row agrees with."""
    counted = building.compute_facets(build_shipped(tools=(OPEN_TICKET, {"junk": 1})))

    assert counted["number_provided_tools"] == 1


def test_a_call_on_a_tool_this_row_never_offered_is_a_broken_row(
    building: ToolDecisionSampleBuilding,
) -> None:
    """BFCL's AST check turned on the corpus rather than on a model, against **this row's own**
    catalog: a label calling a tool the sample never offered is broken, not hard."""
    counted = building.compute_facets(
        build_shipped(label=({"name": "Lookup", "arguments": {}},))
    )

    assert counted["schema_valid"] is False


def test_a_call_missing_a_required_parameter_is_a_broken_row(
    building: ToolDecisionSampleBuilding,
) -> None:
    """The other half of the same check, and the failure mode a corpus teaches if it holds it:
    parameter-value errors dominate complex tool-calling failures."""
    counted = building.compute_facets(
        build_shipped(label=({"name": "OpenTicket", "arguments": {"note": "x"}},))
    )

    assert counted["schema_valid"] is False


def test_nothing_declared_is_answered_here(
    building: ToolDecisionSampleBuilding,
) -> None:
    """A declared facet is a claim a person made and nothing computes one. It arrives under the
    record's `class` key, and a second list of those names here is a list to keep in step with the
    page's for nothing."""
    assert set(building.compute_facets(build_shipped())) == {
        "number_turns",
        "number_label_tools",
        "number_provided_tools",
        "schema_valid",
    }
