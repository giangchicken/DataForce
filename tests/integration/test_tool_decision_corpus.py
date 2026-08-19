"""The adapter against the whole source file, not a sample.

The counts the profile spec quotes are parser-dependent, and this is the parser
that settles them. It also settles a question the spec left open: whether the 841
`empty_catalog` records are toolless prompts or a parser miss. Measured here over
every record, the answer is that no record in this file has an empty catalog.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest
from agent_toolkit.file_utils import iter_json_array_file, read_yaml
from agent_toolkit.string_utils import compute_hash
from conftest import REPO_ROOT

from dataforce.modalities.text import TEXT
from dataforce.profiles.tool_decision import TOOL_DECISION, adapter
from dataforce.profiles.tool_decision import catalog as cat

pytestmark = pytest.mark.integration

MARKERS = (
    "{trigger}",
    "{hold_other}",
    "{hold_missing}",
    "{constraint}",
    "{turn_trigger}",
    "{or}",
)

RECORDS = 21172
ENTRIES = 105880
LARGEST_GROUP = ("13fcdbc67145af61", 112)


@pytest.fixture(scope="module")
def source() -> Path:
    """The file `params.yaml` declares, or a skip naming what to link."""
    declared = Path(read_yaml(REPO_ROOT / "params.yaml")["source"]["path"])
    path = REPO_ROOT / declared
    if not path.exists():
        pytest.skip(f"{declared} is not present; data/raw/ is deliberately untracked")
    return path


@pytest.fixture(scope="module")
def parsed(source: Path) -> list[tuple[str, cat.Catalog, list[str]]]:
    instruction = TOOL_DECISION.contract.role("instruction")
    rows = []
    for raw in iter_json_array_file(source):
        turns = {turn["role"]: turn["content"] for turn in raw["messages"]}
        rows.append(
            (
                turns[instruction],
                cat.parse(turns[instruction]),
                TOOL_DECISION.contract.label_of(raw) or [],
            )
        )
    return rows


def test_the_file_is_the_one_params_yaml_declares(
    source: Path, repo_root: Path
) -> None:
    """Every count below describes one SHA-256, which is why it is asserted first."""
    declared = read_yaml(repo_root / "params.yaml")["source"]["sha256"]

    assert compute_hash(source.read_text(encoding="utf-8"), "sha256") == declared


def test_every_record_yields_a_catalog(
    parsed: list[tuple[str, cat.Catalog, list[str]]],
) -> None:
    assert len(parsed) == RECORDS
    assert sum(len(catalog.tools) for _, catalog, _ in parsed) == ENTRIES


def test_no_record_in_this_file_has_an_empty_catalog(
    parsed: list[tuple[str, cat.Catalog, list[str]]],
) -> None:
    """So `empty_catalog` reads 0, not the 841 a stricter name pattern reports."""
    assert [catalog.names for _, catalog, _ in parsed if catalog.is_empty] == []


def test_every_entry_parsed_a_name_and_a_description(
    parsed: list[tuple[str, cat.Catalog, list[str]]],
) -> None:
    """A description is one verbatim string, so an entry losing one loses everything."""
    for _, catalog, _ in parsed:
        for tool in catalog.tools:
            assert tool.name and tool.description


def test_every_label_names_a_tool_the_record_offered(
    parsed: list[tuple[str, cat.Catalog, list[str]]],
) -> None:
    """So `label_not_in_catalog` reads 0, not 722."""
    outside = [
        (catalog.names, label)
        for _, catalog, label in parsed
        if any(name not in catalog.names for name in label)
    ]

    assert outside == []


def test_every_catalog_re_renders_byte_identically(
    parsed: list[tuple[str, cat.Catalog, list[str]]],
) -> None:
    """What makes one definition of the format safe, over 21,172 catalogs.

    Read then written back with the same module. Any clause the reader silently dropped,
    and any wording the writer changed, is a difference in these bytes.
    """
    header = f"{cat.CATALOG_HEADER}\n"
    for system, catalog, _ in parsed:
        original = system.split(header, 1)[1]
        assert cat.render(catalog.tools) == original.rstrip("\n"), catalog.names[:2]


def test_every_marker_token_survives_every_record(
    parsed: list[tuple[str, cat.Catalog, list[str]]],
) -> None:
    """Invariant 1 over 21,172 records rather than over a fixture."""
    for system, catalog, _ in parsed:
        kept = "\n".join(
            tool.description + json.dumps(tool.parameters, ensure_ascii=False)
            for tool in catalog.tools
        )
        for marker in MARKERS:
            assert kept.count(marker) == system.count(marker), (
                marker,
                catalog.names[:2],
            )


def test_the_reader_reports_every_gap_it_could_not_close(source: Path) -> None:
    """A reader returning less than it was given has to say what it could not take.

    These are findings rather than failures: 3,901 tools whose parameters are all
    optional, 188 object parameters whose subfields the compact inline form cannot carry,
    and 20 whose allowed values are stated in prose where the schema has no enum.
    """
    instruction = TOOL_DECISION.contract.role("instruction")
    gaps: list[cat.Gap] = []
    for raw in iter_json_array_file(source):
        turns = {turn["role"]: turn["content"] for turn in raw["messages"]}
        cat.parse(turns[instruction], gaps=gaps)

    assert Counter(gap.kind for gap in gaps) == {
        "nothing_required": 3901,
        "object_without_subfields": 188,
        "enum_stated_in_prose": 20,
    }


def test_the_largest_catalog_group_is_the_one_the_split_gate_will_protect(
    parsed: list[tuple[str, cat.Catalog, list[str]]],
) -> None:
    groups = Counter(
        adapter.catalog_fingerprint(catalog.names) for _, catalog, _ in parsed
    )

    assert groups.most_common(1)[0] == LARGEST_GROUP


def test_no_two_tools_in_one_catalog_share_a_name(
    parsed: list[tuple[str, cat.Catalog, list[str]]],
) -> None:
    """The answer-space `enum` would otherwise offer one name twice."""
    for _, catalog, _ in parsed:
        assert len(set(catalog.names)) == len(catalog.names)


def test_the_four_checks_reproduce_the_counts_declared_in_params(source: Path) -> None:
    """T9's criterion: what the checks count is what `params.yaml` declares.

    Streamed rather than collected, so this test cannot pass by holding the whole
    126 MiB file the way the profiler is forbidden to.
    """
    declared = read_yaml(REPO_ROOT / "params.yaml")["invalid_counts"]
    check_by_name = TOOL_DECISION.validity_checks()
    counted = Counter({name: 0 for name in check_by_name})

    for offset, raw in enumerate(iter_json_array_file(source)):
        record = TOOL_DECISION.adapt(
            {
                **raw,
                adapter.PROVENANCE_KEY: {
                    "source": {
                        "file_sha256": "0" * 64,
                        "offset": offset,
                        "ingested_at": "2026-08-19T00:00:00Z",
                    },
                    "producer": {"modality": "text@1", "profile": "tool_decision@1"},
                },
            },
            TEXT.load(raw),
        )
        for name, check in check_by_name.items():
            if check(record):
                counted[name] += 1

    assert dict(counted) == declared


def test_one_real_record_makes_the_round_trip(source: Path) -> None:
    """Phase 2's exit condition: raw item in, canonical record, and out again.

    Byte-identical on the way out, including the marker DSL and whatever `meta` the
    item happened to carry -- with no LLM, no annotation tool and no DVC stage.
    """
    raw = next(iter(iter_json_array_file(source)))

    record = TOOL_DECISION.adapt(
        {
            **raw,
            adapter.PROVENANCE_KEY: {
                "source": {
                    "file_sha256": read_yaml(REPO_ROOT / "params.yaml")["source"][
                        "sha256"
                    ],
                    "offset": 0,
                    "ingested_at": "2026-08-19T00:00:00Z",
                },
                "producer": {"modality": "text@1", "profile": "tool_decision@1"},
            },
        },
        TEXT.load(raw),
    )
    exported = TOOL_DECISION.export(record)

    assert exported["messages"] == raw["messages"]
    assert exported["meta"]["label"] == raw["meta"]["label"]
    assert record.rid and record.answer_space is not None
    assert TOOL_DECISION.group_key(record) == adapter.catalog_fingerprint(
        cat.parse(raw["messages"][0]["content"]).names
    )
