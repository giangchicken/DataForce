"""The declared input shapes, checked against real data rather than asserted.

A schema nobody validated is a guess with syntax. So: the corpus is checked against
the legacy shape it is actually in, the generator's own 41-tool file against the tool
shape, and a catalog converted out of a corpus record against the canonical shape.

`jsonschema` is a dependency the library owns and no pipeline module may import it --
core invariant 17. A test validating a contract document is not pipeline code, and
this is the only place it appears.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from agent_toolkit.file_utils import iter_json_array_file, read_yaml
from conftest import REPO_ROOT
from referencing import Registry, Resource

pytestmark = pytest.mark.integration

SCHEMAS = REPO_ROOT / "src" / "dataforce" / "profiles" / "tool_decision" / "schemas"
# From the environment, never committed: the renderer lives in another repository and
# its checkout path is one person's filesystem layout.
GENERATOR_DIR = os.environ.get("DATAFORCE_GENERATOR_DIR")
SAMPLE = 2000


def schema(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(
        (SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8")
    )
    return loaded


NAMES = ("tool", "record", "legacy_record")


@pytest.fixture(scope="module")
def validators() -> dict[str, jsonschema.protocols.Validator]:
    """One registry, so `record` resolves its `$ref` to `tool` by that schema's `$id`."""
    loaded = {name: schema(name) for name in NAMES}
    registry = Registry().with_resources(
        (body["$id"], Resource.from_contents(body)) for body in loaded.values()
    )
    return {
        name: jsonschema.Draft202012Validator(body, registry=registry)
        for name, body in loaded.items()
    }


def test_every_schema_is_a_valid_json_schema() -> None:
    for name in NAMES:
        jsonschema.Draft202012Validator.check_schema(schema(name))


def test_the_corpus_is_in_the_legacy_shape_the_schema_declares(
    validators: dict[str, jsonschema.protocols.Validator],
) -> None:
    """Which is what lets ingest assert what it is reading before converting it."""
    declared = read_yaml(REPO_ROOT / "params.yaml")["source"]["path"]
    source = REPO_ROOT / declared
    if not source.exists():
        pytest.skip(f"{declared} is not present; data/raw/ is deliberately untracked")

    checked = 0
    for raw in iter_json_array_file(source):
        validators["legacy_record"].validate(raw)
        checked += 1
        if checked >= SAMPLE:
            break

    assert checked == SAMPLE


def test_the_corpus_is_not_yet_in_the_canonical_shape(
    validators: dict[str, jsonschema.protocols.Validator],
) -> None:
    """The gap the conversion exists to close, stated as a failing validation."""
    declared = read_yaml(REPO_ROOT / "params.yaml")["source"]["path"]
    source = REPO_ROOT / declared
    if not source.exists():
        pytest.skip(f"{declared} is not present; data/raw/ is deliberately untracked")

    raw = next(iter(iter_json_array_file(source)))

    with pytest.raises(jsonschema.ValidationError, match="tools"):
        validators["record"].validate(raw)


def test_the_generator_s_own_tools_satisfy_the_tool_schema(
    validators: dict[str, jsonschema.protocols.Validator],
) -> None:
    """The forward renderer's input is the shape this pipeline declares as canonical."""
    if not GENERATOR_DIR:
        pytest.skip(
            "set DATAFORCE_GENERATOR_DIR to the renderer's checkout to run this"
        )
    tools_file = Path(GENERATOR_DIR) / "provided_tools_enriched.json"
    if not tools_file.is_file():
        pytest.skip(f"{tools_file} is not present")

    tools = json.loads(tools_file.read_text(encoding="utf-8"))

    assert len(tools) == 41
    for tool in tools:
        validators["tool"].validate({"type": "function", "function": tool})


def test_the_declared_source_shape_matches_what_the_file_is() -> None:
    declared = read_yaml(REPO_ROOT / "config" / "profiles" / "tool_decision.yaml")

    assert declared["shape"] == "legacy_system_prompt"
    assert declared["gold"]["from"] == "human_checked"
    assert declared["roles"] == {
        "instruction": "system",
        "conversation": ["user"],
        "target": "assistant",
    }
