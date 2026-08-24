"""Requirement 48: a phase's stage order is engine knowledge, and this is the module that holds it.

Every stage in the tree is a docstring until Phase 4, so the fold is proved against stand-ins
installed on the real stage modules -- which also proves the dispatch: `run_phase` finds a service
by deriving its module from the flow table, so a stand-in has to be reachable exactly where a real
one will be.

The stand-ins sign each record they pass on, so one assertion reads the whole fold: which stages
ran, in which order, and whether each one's records were the next one's.

`a_record` and `a_registry_holding` come from the two test modules beside this one rather than from
a `conftest.py`. Two consumers is when a thing moves; this is the second, and it is one import.
"""

from collections.abc import Iterable
from importlib import import_module

import pytest

from dataforce.engine import Engine, ServiceResult
from dataforce.errors import ConfigError
from dataforce.pipeline.flow import STAGES
from dataforce.pipeline.runner import Service, run_phase, stage_module_name
from dataforce.record import Record

from .test_record import a_record, a_text_part
from .test_registry import a_registry_holding

PHASE = "data_quality"


def an_engine() -> Engine:
    """What `edge/bootstrap.py` will hand a stage. Nothing below reads it -- the stand-ins ignore
    it, and the point is that the runner passes the same one to every stage."""
    registry = a_registry_holding("text2text")
    return Engine(
        modality=registry.modality("text2text"),
        profile=registry.profile("text2text"),
        registry=registry,
        thresholds={},
        policy_digests={},
    )


def a_stage_signing_its_name(name: str) -> Service:
    """A stand-in service: it marks every record it saw and hands back one piece of side output."""

    def service(engine: Engine, records: Iterable[Record]) -> ServiceResult:
        signed = tuple(
            record.model_copy(update={"source_id": f"{record.source_id}+{name}"})
            for record in records
        )
        return ServiceResult(
            records=signed, side_output={name: "for the edge to write"}
        )

    return service


@pytest.fixture
def stand_ins(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """One stand-in per `data_quality` stage, installed where the runner will look for it."""
    installed = []
    for stage in (row for row in STAGES if row.phase == PHASE):
        monkeypatch.setattr(
            f"{stage_module_name(stage.phase, stage.stage)}.{stage.stage}",
            a_stage_signing_its_name(stage.stage),
            raising=False,
        )
        installed.append(stage.stage)
    return installed


def test_one_stage_in_a_phase_is_a_module_and_several_are_a_directory() -> None:
    """The layout rule, stated once here and read by the guard that checks the tree against it."""
    assert stage_module_name("load_data", "load_data") == "dataforce.pipeline.load_data"
    assert (
        stage_module_name("data_quality", "pii_check")
        == "dataforce.pipeline.data_quality.pii_check"
    )


def test_a_phase_runs_its_stages_in_the_table_s_order(stand_ins: list[str]) -> None:
    """Requirement 48, and the fold with it: each stage's records are the next stage's."""
    ran = run_phase(an_engine(), PHASE, [a_record(a_text_part("xin chào"))])

    assert ran.records[0].source_id == "+".join(["s1", *stand_ins])


def test_side_output_comes_back_under_the_name_of_the_stage_that_produced_it(
    stand_ins: list[str],
) -> None:
    """The edge writes it, and what it writes depends on which stage it came from."""
    ran = run_phase(an_engine(), PHASE, [a_record(a_text_part("xin chào"))])

    assert sorted(ran.side_output) == sorted(stand_ins)


def test_a_phase_hands_back_as_many_records_as_it_was_given(
    stand_ins: list[str],
) -> None:
    """Requirement 41. The stand-ins conserve records; a phase that did not would show here."""
    records = [a_record(a_text_part(f"turn {n}")) for n in range(3)]

    assert len(run_phase(an_engine(), PHASE, records).records) == len(records)


def test_a_phase_that_is_declared_and_not_built_says_so() -> None:
    """`release` is a row of the flow with no module: asking for it is a configuration mistake."""
    with pytest.raises(ConfigError, match="declared"):
        run_phase(an_engine(), "release", [])


def test_a_phase_the_flow_does_not_have_names_the_ones_it_does() -> None:
    """The same courtesy the registry gives an unknown axis name."""
    with pytest.raises(ConfigError, match="data_quality"):
        run_phase(an_engine(), "data_qualtiy", [])


def test_a_stage_module_with_no_function_of_its_own_name_says_which(
    stand_ins: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The unwrapped `AttributeError` `runner.py`'s docstring argues for, which nothing proved.

    `delattr(..., raising=False)` is what makes this durable in both directions: the attribute is
    missing anyway until Phase 4 builds the stage, and from then on it exists and is removed for
    the length of this test. Asserting the raise directly against a bare module would have been
    green today and red the day `label_check` was written.
    """
    first = next(row for row in STAGES if row.phase == PHASE)
    module = import_module(stage_module_name(first.phase, first.stage))
    monkeypatch.delattr(module, first.stage, raising=False)

    with pytest.raises(AttributeError, match=first.stage):
        run_phase(an_engine(), PHASE, [])
