"""Stage 0: nothing dropped, nothing invented, and two runs that agree byte for byte.

Every source here is invented and written into `tmp_path`. The declared corpus is not
the input to a test: what a test may assert about is a file it wrote, whose digest,
element order and unreadable rows it chose. Running stage 0 over the declared source is
a command a person runs -- `uv run dataforce run load` -- and the reproducibility claim
this file makes is what makes that run worth trusting.

Four claims, one per criterion of T11. Provenance is on every record and stamps both
axes. The same source read twice writes the same bytes twice -- which is why nothing in
the stage reads a clock. A digest the policy did not pin stops the run before the source
is parsed at all. And an item the reader cannot read is carried with its own text rather
than skipped, so `parsed + unparsed == source count` is a real claim about the loop.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml
from conftest import CONFIG

from dataforce import api
from dataforce.cli import main
from dataforce.core.artifacts import schema_for
from dataforce.core.errors import ConfigError
from dataforce.core.gates import GateFailed
from dataforce.core.record import PROVENANCE_KEY

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "tool_decision"

STAGE_DIRECTORY = "1_data_quality"


def turns(catalog: str, label: list[str]) -> list[dict[str, Any]]:
    """One conversation: the catalog rendered into the instruction turn, then the answer."""
    return [
        {
            "role": "system",
            "content": (FIXTURES / "catalogs" / catalog).read_text(encoding="utf-8"),
        },
        {"role": "user", "content": "cho tôi hỏi một chút"},
        {"role": "assistant", "content": json.dumps(label)},
    ]


def readable_item(catalog: str, label: list[str], index: int) -> dict[str, Any]:
    return {
        "idx": index,
        "messages": turns(catalog, label),
        "meta": {"label": label, "llm_model": "gemma-4-31B-it", "source_index": index},
    }


# Two items the reader cannot read, for two different reasons, so `UNREADABLE` is shown
# to cover more than one: an item with no turns at all, and a turn carrying neither text
# nor a call. Both are carried rather than dropped -- requirement 14.
NO_MESSAGES: dict[str, Any] = {"idx": 3, "meta": {"label": []}}
EMPTY_TURN: dict[str, Any] = {
    "idx": 4,
    "messages": [{"role": "assistant", "content": None}],
    "meta": {"label": []},
}

ITEMS: list[dict[str, Any]] = [
    readable_item("one_tool.txt", ["Lookup00_0a"], 1),
    readable_item("eight_tools.txt", [], 2),
    NO_MESSAGES,
    EMPTY_TURN,
]


@pytest.fixture
def policy(tmp_path: Path) -> Path:
    """This repository's config, somewhere that is not this repository."""
    shutil.copytree(CONFIG, tmp_path / "policy")
    return tmp_path / "policy"


def declared_params(
    root: Path, items: list[dict[str, Any]], *, sha256: str | None = None
) -> Path:
    """An invented source on disk, and the `params.yaml` that pins it.

    `sha256` is a parameter so that one test can pin a digest the file does not have,
    which is the only way to reach the identity gate's failing side.
    """
    source = root / "source.json"
    source.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    params = root / "params.yaml"
    params.write_text(
        yaml.safe_dump(
            {
                "source": {
                    "path": str(source),
                    "sha256": sha256 or api.file_digest(source),
                },
                "max_answer_cardinality": 3,
            }
        ),
        encoding="utf-8",
    )
    return params


def loaded_rows(artifact: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in artifact.read_text(encoding="utf-8").splitlines()
        if line
    ]


def stage_zero(policy: Path, params: Path, data_root: Path) -> dict[str, Path]:
    engine = api.open_engine(profile="tool_decision", config_root=policy, params=params)
    return api.stage_outputs(engine, ["load"], params=params, data_root=data_root)


# --- what one record carries ---------------------------------------------------


def test_every_record_carries_its_provenance_and_both_versions(
    tmp_path: Path, policy: Path
) -> None:
    """Requirement 14's five fields, and `producer` as `name@version` on both axes."""
    params = declared_params(tmp_path, ITEMS)
    written = stage_zero(policy, params, tmp_path / "data")

    rows = loaded_rows(written["loaded"])
    assert len(rows) == len(ITEMS)
    digest = yaml.safe_load(params.read_text(encoding="utf-8"))["source"]["sha256"]
    for offset, row in enumerate(rows):
        assert row["source"] == {
            "file_sha256": digest,
            "offset": offset,
            "ingested_at": rows[0]["source"]["ingested_at"],
        }
        assert row["producer"] == {"modality": "text@1", "profile": "tool_decision@1"}
    assert rows[0]["source"]["ingested_at"].endswith("Z")
    assert PROVENANCE_KEY not in rows[0]["meta"], "the key is lifted out, not stored"


def test_the_artifact_is_where_its_phase_says_and_validates_against_its_schema(
    tmp_path: Path, policy: Path
) -> None:
    """`loaded` is a name in `core/artifacts/`, and the row shape is that schema's."""
    params = declared_params(tmp_path, ITEMS)
    written = stage_zero(policy, params, tmp_path / "data")

    assert written["loaded"] == (
        tmp_path / "data" / "interim" / STAGE_DIRECTORY / "loaded.jsonl"
    )
    assert api.interim_directory("data_quality", data_root=tmp_path) == (
        tmp_path / "interim" / STAGE_DIRECTORY
    )
    schema_for("loaded").validate(pd.DataFrame(loaded_rows(written["loaded"])))


# --- nothing dropped -----------------------------------------------------------


def test_an_unreadable_item_is_carried_with_its_own_text(
    tmp_path: Path, policy: Path
) -> None:
    """Requirement 14: nothing is dropped, and an unreadable item says why."""
    params = declared_params(tmp_path, ITEMS)
    written = stage_zero(policy, params, tmp_path / "data")

    rows = loaded_rows(written["loaded"])
    statuses = [row["parse_status"] for row in rows]
    assert statuses == ["ok", "ok", "unparsed", "unparsed"]

    carried = rows[2]
    assert carried["content"] == [
        {
            "type": "text",
            "role": "raw",
            "text": json.dumps(NO_MESSAGES, ensure_ascii=False),
        }
    ]
    assert carried["meta"]["parse_error"], "an unparsed record says what defeated it"
    assert len(carried["rid"]) == 16
    assert rows[3]["rid"] != carried["rid"], "two unreadable items are two records"


def test_the_conservation_gate_counts_the_source_and_both_kinds_of_row(
    tmp_path: Path, policy: Path
) -> None:
    params = declared_params(tmp_path, ITEMS)
    data_root = tmp_path / "data"
    stage_zero(policy, params, data_root)

    metrics = json.loads(
        (data_root / "interim" / STAGE_DIRECTORY / api.METRICS_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    assert metrics["stage"] == "load"
    assert [gate["gate"] for gate in metrics["gates"]] == [
        "source_identity",
        "conservation",
    ]
    assert all(gate["ok"] for gate in metrics["gates"])
    conservation = metrics["gates"][1]
    assert conservation["observed"]["output"] == len(ITEMS)
    assert conservation["expected"] == {"input": len(ITEMS)}


# --- the same source twice -----------------------------------------------------


def test_the_ingest_time_is_the_sources_own_and_not_the_clock(
    tmp_path: Path, policy: Path
) -> None:
    """Where `ingested_at` comes from, pinned to a date no run can have happened on.

    The byte-identity test below cannot make this claim: two runs a moment apart share
    a wall-clock second, so it passes just as happily on `datetime.now()` -- which is
    exactly what a perturbation of this stage showed. This one fails on it.
    """
    params = declared_params(tmp_path, ITEMS)
    source = tmp_path / "source.json"
    written_at = datetime(2019, 3, 4, 5, 6, 7, tzinfo=UTC).timestamp()
    os.utime(source, (written_at, written_at))
    # Touching mtime leaves the bytes alone, so the digest the policy pinned still holds.
    written = stage_zero(policy, params, tmp_path / "data")

    stamped = {row["source"]["ingested_at"] for row in loaded_rows(written["loaded"])}
    assert stamped == {"2019-03-04T05:06:07Z"}


def test_two_runs_over_one_source_write_the_same_bytes(
    tmp_path: Path, policy: Path
) -> None:
    """The criterion that decides whether stage 0 may read a clock. It may not.

    Not a no-op and not asserted to be fast -- there is no stage cache, so this reads
    the source twice on purpose.
    """
    params = declared_params(tmp_path, ITEMS)
    data_root = tmp_path / "data"

    first = stage_zero(policy, params, data_root)
    artifact = first["loaded"].read_bytes()
    manifest = first["run"].read_bytes()

    second = stage_zero(policy, params, data_root)

    assert second["loaded"].read_bytes() == artifact
    assert second["run"].read_bytes() == manifest


def test_the_run_manifest_names_the_artifact_and_the_policy(
    tmp_path: Path, policy: Path
) -> None:
    params = declared_params(tmp_path, ITEMS)
    data_root = tmp_path / "data"
    written = stage_zero(policy, params, data_root)

    recorded = json.loads(written["run"].read_text(encoding="utf-8"))
    assert written["run"] == data_root / api.RUN_MANIFEST_FILENAME
    assert recorded["producer"] == {"modality": "text@1", "profile": "tool_decision@1"}
    assert recorded["artifacts"] == {"loaded": api.file_digest(written["loaded"])}
    assert sorted(Path(named).name for named in recorded["policy"]) == [
        "params.yaml",
        "question.v1.txt",
        "text.yaml",
        "tool_decision.yaml",
    ]


# --- the two hard stops --------------------------------------------------------


def test_a_source_the_policy_did_not_pin_stops_before_it_is_parsed(
    tmp_path: Path, policy: Path
) -> None:
    """A changed source is a new dataset version, decided by a person."""
    params = declared_params(tmp_path, ITEMS, sha256="0" * 64)
    data_root = tmp_path / "data"

    with pytest.raises(GateFailed) as stopped:
        stage_zero(policy, params, data_root)

    assert [result.name for result in stopped.value.failures] == ["source_identity"]
    stage_dir = data_root / "interim" / STAGE_DIRECTORY
    assert not (stage_dir / "loaded.jsonl").exists(), "it parsed the wrong file anyway"
    failure = json.loads(
        (stage_dir / api.GATE_FAILED_FILENAME).read_text(encoding="utf-8")
    )
    assert failure["expected"] == "0" * 64


def test_a_stage_that_is_not_built_names_the_ones_that_are(
    tmp_path: Path, policy: Path
) -> None:
    params = declared_params(tmp_path, ITEMS)
    engine = api.open_engine(profile="tool_decision", config_root=policy, params=params)

    with pytest.raises(ConfigError, match=r"\['jury'\].*load"):
        api.stage_outputs(
            engine, ["load", "jury"], params=params, data_root=tmp_path / "data"
        )
    assert not (tmp_path / "data").exists(), "it started before checking the names"


def test_the_command_stops_on_a_pair_the_profile_does_not_declare(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Through `dataforce run` itself, and before anything opens the source.

    The one test here that reads this repository's own policy, because what it is
    checking is the command's exit code and the command knows where the policy is.
    """
    assert main(["run", "--modality", "audio", "--profile", "tool_decision"]) == 2
    assert "composes with modality 'text'" in capsys.readouterr().err
