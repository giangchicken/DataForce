"""I20 · the record's keys are the keys § *The record* draws.

The drawing is the only place a record key's *meaning* is written next to it in prose, and
`record.py` is the only place it is written next to the field. P31: two statements of one fact are
compared or one of them is fiction. This is the largest uncompared fact left in the document --
about a hundred keys -- and the plan already records two ways the two sides have drifted before
anyone typed this guard.

**Two keys are not compared, and they are named rather than detected.** `label` and `meta` are
free-form: the drawing shows an example *answer* and an example source key, which are contents and
not keys. Everything else is compared, including through lists (`content`, `spans`,
`question_generate`) and including a field's alias, which is why `class` compares to `class` and
not to `personal_data_class`.

**One drawn *value* is compared, and it is named here.** `aggregate.method` is the name of an
estimator rather than an example of one, and the drawing carried `majority_gold_weighted` --  a
method this repository has never contained -- for as long as only the keys were compared. Every
other value in the drawing is an illustration and stays uncompared.

**A list draws its members' shape.** `content` draws a text part and a media part, and the union of
what they carry is what `Part` has to hold: a comment saying "media types carry `uri` + `sha256`"
is prose, and prose is what this guard exists to stop trusting.
"""

import json
import re
from collections.abc import Callable, Mapping
from typing import Any, get_args

import pytest
from pydantic import BaseModel

from dataforce.pipeline.human_review.aggregate import METHOD
from dataforce.record import Record

from .tree import SPEC

# The drawing shows the contents of these two, not their keys: an answer is the profile's shape
# (Requirement 47) and `meta` is whatever the source presented, verbatim (Requirement 9).
FREE_FORM = ("label", "meta")


def drawn_record() -> dict[str, Any]:
    """§ *The record*'s JSONC, parsed: comments gone, trailing commas gone."""
    design = SPEC.read_text(encoding="utf-8").split("## Design", 1)[1]
    block = (
        design[design.index("### The record") :].split("```jsonc")[1].split("```")[0]
    )
    bare = re.sub(r",(\s*[}\]])", r"\1", re.sub(r"//[^\n]*", "", block))
    return dict(json.loads(bare))


def model_keys(model: type[BaseModel]) -> dict[str, Any]:
    """Every key that model writes, under the name it is written with, nested all the way down."""
    keys: dict[str, Any] = {}
    for name, field in model.model_fields.items():
        nested = _model_inside(field.annotation)
        keys[field.alias or name] = model_keys(nested) if nested else {}
    return keys


def _model_inside(annotation: Any) -> type[BaseModel] | None:
    """The model in `X`, `X | None` or `tuple[X, ...]`; None where the leaf is free-form JSON."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for argument in get_args(annotation):
        found = _model_inside(argument)
        if found is not None:
            return found
    return None


def _keys_of(drawn: Any) -> dict[str, Any]:
    """What one drawn value declares: a list of objects declares the shape of its members."""
    if isinstance(drawn, Mapping):
        return dict(drawn)
    if isinstance(drawn, list):
        return {
            k: v for item in drawn if isinstance(item, Mapping) for k, v in item.items()
        }
    return {}


def differences(
    drawn: Mapping[str, Any], coded: Mapping[str, Any], path: str = ""
) -> list[str]:
    """Every key one side has and the other does not, named by where it sits."""
    found = [
        f"{path}{key}: drawn, and the record has no such field"
        for key in drawn
        if key not in coded
    ]
    found += [
        f"{path}{key}: a record field the document does not draw"
        for key in coded
        if key not in drawn
    ]
    for key in drawn.keys() & coded.keys():
        if f"{path}{key}" in FREE_FORM:
            continue
        found += differences(_keys_of(drawn[key]), coded[key], f"{path}{key}.")
    return sorted(found)


def test_the_drawing_was_found_and_parsed() -> None:
    """Guards the parser: an unread drawing makes every assertion below vacuous."""
    drawn = drawn_record()

    assert len(drawn) == len(Record.model_fields)
    assert "record_id" in drawn
    assert _keys_of(drawn["data_quality"])["pii_check"]["spans"][0]["class"]


def test_the_record_holds_the_keys_the_document_draws() -> None:
    """I20, both directions, over the whole drawing."""
    assert differences(drawn_record(), model_keys(Record)) == []


@pytest.mark.parametrize(
    "drift",
    [
        pytest.param(
            lambda drawn: {**drawn, "a_key_nobody_declared": 1},
            id="drawn-with-no-field",
        ),
        pytest.param(
            lambda drawn: {k: v for k, v in drawn.items() if k != "content_version"},
            id="a-key-dropped-from-the-drawing",
        ),
        pytest.param(
            lambda drawn: {**drawn, "human_review": {"human_config": {}}},
            id="a-phase-that-lost-its-stages",
        ),
    ],
)
def test_the_scan_rejects_a_drawing_that_has_drifted(
    drift: Callable[[dict[str, Any]], dict[str, Any]],
) -> None:
    """P29: a key in the document with no field, a key dropped, and a nested key dropped."""
    assert differences(drift(drawn_record()), model_keys(Record)) != []


def test_the_scan_rejects_a_field_the_document_does_not_draw() -> None:
    """P29, the other direction: `record.py` grows a key and § *The record* is not touched."""
    coded = model_keys(Record)
    coded["answer_space"] = {}

    assert differences(drawn_record(), coded) != []


def test_the_two_free_form_keys_are_not_compared() -> None:
    """Named, not detected: what is inside `label` and `meta` is the profile's and the source's."""
    drawn = drawn_record()
    drawn["label"] = [{"whatever": "a profile decides this"}]
    drawn["meta"] = {"a_key_no_code_recognises": True}

    assert differences(drawn, model_keys(Record)) == []


def test_the_method_the_drawing_names_is_the_method_aggregate_writes() -> None:
    """The one drawn value that is a claim: it named an estimator that has never existed here."""
    drawn = drawn_record()

    assert drawn["human_review"]["aggregate"]["method"] == METHOD


def test_a_media_part_is_drawn_and_not_only_described() -> None:
    """`uri` and `sha256` were a comment on `type` until this guard needed them to be keys."""
    parts = _keys_of(drawn_record()["content"])

    assert {"uri", "sha256"} <= parts.keys()
