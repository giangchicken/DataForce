"""The suite every profile passes before it can be named on a run.

The protocol's types cannot express "delta is a metric" or "consensus is
deterministic", and a profile violating either produces cohesion numbers that
look fine and mean nothing. Checking at registration moves that error from a
hundred-million-token run to a test, which is the whole reason this file exists.

Answer pairs are generated from the profile's own answer schema, so the suite
needs no per-profile fixtures for the three checks it runs at registration. The
adapter and exporter checks need one raw record, so they run where a fixture
exists -- in `tests/conformance/` -- rather than at import time.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from dataforce.profiles.base import Answer, Profile
from dataforce.shared.errors import ConformanceError
from dataforce.shared.record import Part, Record

__all__ = [
    "CheckResult",
    "ConformanceReport",
    "check_adapter_preserves_unowned_fields",
    "check_answers_round_trip",
    "check_consensus",
    "check_delta_is_a_metric",
    "check_export_reproduces_the_answer",
    "declares_consensus",
    "empty_answer",
    "run",
    "run_with_sample",
    "sample_answers",
]

MAX_SAMPLES = 8
PROBE_KEY = "__conformance_probe__"


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str

    @classmethod
    def passed(cls, name: str, detail: str = "") -> CheckResult:
        return cls(name=name, ok=True, detail=detail)

    @classmethod
    def failed(cls, name: str, detail: str) -> CheckResult:
        return cls(name=name, ok=False, detail=detail)


@dataclass(frozen=True)
class ConformanceReport:
    """What the suite found, kept so a release can say what was checked."""

    profile: str
    checks: tuple[CheckResult, ...]
    barred_from_consensus_tier: bool

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    @property
    def failures(self) -> tuple[CheckResult, ...]:
        return tuple(check for check in self.checks if not check.ok)


def _key(value: Any) -> str:
    """A stable comparison key for answers, which need not be hashable."""
    return json.dumps(value, sort_keys=True, default=repr)


def _samples(schema: Mapping[str, Any]) -> list[Any]:
    if "enum" in schema:
        return list(schema["enum"])
    if "const" in schema:
        return [schema["const"]]
    for keyword in ("oneOf", "anyOf"):
        if keyword in schema:
            return [value for sub in schema[keyword] for value in _samples(sub)]

    declared = schema.get("type")
    if declared is None:
        raise ConformanceError(
            "cannot generate answers from a schema with no `type`, `enum`, `const`, "
            f"`oneOf` or `anyOf`: {dict(schema)!r}"
        )
    if isinstance(declared, list):
        return [
            value for name in declared for value in _samples({**schema, "type": name})
        ]

    if declared == "string":
        return ["", "alpha", "beta"]
    if declared == "integer":
        return [0, 1, 2]
    if declared == "number":
        return [0.0, 1.5]
    if declared == "boolean":
        return [True, False]
    if declared == "null":
        return [None]
    if declared == "array":
        return _array_samples(schema)
    if declared == "object":
        return _object_samples(schema)
    raise ConformanceError(f"cannot generate answers for type {declared!r}")


def _array_samples(schema: Mapping[str, Any]) -> list[Any]:
    items = schema.get("items")
    item_samples = _samples(items) if isinstance(items, Mapping) else []

    candidates: list[list[Any]] = [[]]
    candidates.extend([item] for item in item_samples)
    if len(item_samples) >= 2:
        candidates.append(item_samples[:2])
        candidates.append(list(reversed(item_samples[:2])))

    low = schema.get("minItems", 0)
    high = schema.get("maxItems", len(item_samples) or 1)
    return [value for value in candidates if low <= len(value) <= high]


def _object_samples(schema: Mapping[str, Any]) -> list[Any]:
    properties = schema.get("properties") or {}
    required = schema.get("required") or []
    minimal = {
        name: _samples(properties[name])[0] for name in required if name in properties
    }
    full = {name: _samples(sub)[0] for name, sub in properties.items()}
    return [minimal, full] if _key(minimal) != _key(full) else [full]


def sample_answers(schema: Mapping[str, Any], *, limit: int = MAX_SAMPLES) -> list[Any]:
    """Distinct answers drawn from a schema, deterministically and in a fixed order.

    Deterministic because this runs at registration, on the path to a real run: a
    suite that sometimes generates the pair that breaks a profile is not a gate.
    """
    seen: set[str] = set()
    answers: list[Any] = []
    for value in _samples(schema):
        key = _key(value)
        if key in seen:
            continue
        seen.add(key)
        answers.append(value)
        if len(answers) == limit:
            break
    if not answers:
        raise ConformanceError(f"no answers could be generated from {dict(schema)!r}")
    return answers


def empty_answer(schema: Mapping[str, Any]) -> tuple[bool, Any]:
    """This profile's empty answer, if it has one.

    Load-bearing: for the first profile a third of the corpus is the empty set,
    and a Jaccard distance returning 0/0 there inverts the signal on all of it.
    """
    declared = schema.get("type")
    declared_types = declared if isinstance(declared, list) else [declared]
    if "null" in declared_types:
        return True, None
    if "array" in declared_types and schema.get("minItems", 0) == 0:
        return True, []
    if "string" in declared_types and schema.get("minLength", 0) == 0:
        return True, ""
    if "object" in declared_types and not (schema.get("required") or []):
        return True, {}
    return False, None


def _distance(profile: Profile, a: Answer, b: Answer) -> tuple[float | None, str]:
    """Delta, or why it could not be computed.

    A delta that raises fails the same axiom a NaN does -- a Jaccard written as
    `len(a & b) / len(a | b)` raises on two empty answers rather than returning
    NaN -- and the profile learns more from being told which pair did it than from
    the traceback.
    """
    try:
        return float(profile.delta(a, b)), ""
    except Exception as exc:  # any failure of a third-party delta is a failed axiom
        return None, f"{type(exc).__name__}: {exc}"


def check_delta_is_a_metric(profile: Profile, answers: Sequence[Answer]) -> CheckResult:
    name = "delta_is_a_metric"
    for answer in answers:
        distance, why = _distance(profile, answer, answer)
        if distance is None:
            return CheckResult.failed(
                name, f"delta(a, a) raised {why} for a={answer!r}"
            )
        if math.isnan(distance):
            return CheckResult.failed(name, f"delta(a, a) is NaN for a={answer!r}")
        if distance != 0.0:
            return CheckResult.failed(
                name, f"delta(a, a) = {distance} for a={answer!r}"
            )

    for left, right in combinations(answers, 2):
        forward, why = _distance(profile, left, right)
        backward, why_back = _distance(profile, right, left)
        if forward is None or backward is None:
            return CheckResult.failed(
                name, f"delta raised {why or why_back} for {left!r} and {right!r}"
            )
        if math.isnan(forward) or math.isnan(backward):
            return CheckResult.failed(name, f"delta is NaN for {left!r} and {right!r}")
        if forward != backward:
            return CheckResult.failed(
                name,
                f"delta is not symmetric: {forward} vs {backward} for {left!r}, {right!r}",
            )
        if not 0.0 <= forward <= 1.0:
            return CheckResult.failed(
                name, f"delta = {forward} is outside [0, 1] for {left!r}, {right!r}"
            )
    return CheckResult.passed(name, f"checked {len(answers)} answers pairwise")


def _agreed(profile: Profile, answers: list[Answer]) -> tuple[Any, str]:
    """Consensus, or why it could not be computed. A raise is a failure, not a bar."""
    try:
        return profile.consensus(answers), ""
    except Exception as exc:  # any failure of a third-party consensus is a failed check
        return None, f"{type(exc).__name__}: {exc}"


def declares_consensus(profile: Profile, answers: Sequence[Answer]) -> bool:
    """False when the profile abstains even on unanimous input, which is a declaration.

    A consensus that *raises* is not a declaration -- it is a defect -- so this
    reports True and lets `check_consensus` name it.
    """
    for answer in answers:
        agreed, why = _agreed(profile, [answer] * 3)
        if agreed is not None or why:
            return True
    return False


def check_consensus(profile: Profile, answers: Sequence[Answer]) -> CheckResult:
    name = "consensus_is_deterministic_and_agrees_on_unanimity"
    votes = list(answers)
    first, why = _agreed(profile, votes)
    second, why_again = _agreed(profile, list(votes))
    if why or why_again:
        return CheckResult.failed(name, f"consensus raised {why or why_again}")
    if _key(first) != _key(second):
        return CheckResult.failed(name, "consensus is not deterministic over one input")

    for answer in answers:
        agreed, why = _agreed(profile, [answer] * 3)
        if why:
            return CheckResult.failed(
                name, f"consensus raised {why} on unanimous input a={answer!r}"
            )
        if agreed is None:
            return CheckResult.failed(
                name, f"consensus abstained on unanimous input a={answer!r}"
            )
        distance, why = _distance(profile, agreed, answer)
        if distance is None:
            return CheckResult.failed(name, f"delta raised {why} against the consensus")
        if distance != 0.0:
            return CheckResult.failed(
                name,
                f"consensus over three identical answers is {agreed!r}, "
                f"delta {distance} from a={answer!r}",
            )
    return CheckResult.passed(name)


def check_answers_round_trip(
    profile: Profile, answers: Sequence[Answer]
) -> CheckResult:
    name = "answers_survive_an_artifact"
    for answer in answers:
        restored = json.loads(json.dumps(answer))
        if _key(restored) != _key(answer):
            return CheckResult.failed(name, f"{answer!r} came back as {restored!r}")
        distance, why = _distance(profile, restored, answer)
        if distance != 0.0:
            return CheckResult.failed(
                name,
                f"{answer!r} is not delta-identical to itself after a round trip"
                + (f": delta raised {why}" if distance is None else ""),
            )
    return CheckResult.passed(name)


def check_adapter_preserves_unowned_fields(
    profile: Profile, raw: Mapping[str, Any], parts: list[Part]
) -> CheckResult:
    """A field the adapter does not understand must survive it. Nothing is dropped."""
    name = "adapter_preserves_unowned_fields"
    probe = "kept-verbatim"
    record = profile.adapt({**raw, PROBE_KEY: probe}, parts)
    if probe not in _key(record.model_dump()):
        return CheckResult.failed(name, f"{PROBE_KEY} did not survive adapt()")
    return CheckResult.passed(name)


def _values(value: Any) -> Iterator[Any]:
    yield value
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _values(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _values(nested)


def check_export_reproduces_the_answer(profile: Profile, record: Record) -> CheckResult:
    """The exported example must still contain the answer the adapter read."""
    name = "export_reproduces_the_answer"
    exported = profile.export(record)
    for candidate in _values(exported):
        try:
            if profile.delta(candidate, record.label) == 0.0:
                return CheckResult.passed(name)
        except (AttributeError, KeyError, TypeError, ValueError):
            continue  # most values in a training example are not answers at all
    return CheckResult.failed(
        name, f"no value in the exported example is delta-identical to {record.label!r}"
    )


def run(profile: Profile) -> ConformanceReport:
    """The checks that need only the profile's schema. Run at registration.

    Raises when the suite cannot run at all -- an answer schema it cannot generate
    from -- because an unchecked profile must not be selectable. A profile that
    runs and fails comes back as a report whose `ok` is False.
    """
    answers = sample_answers(profile.answer_schema)
    has_empty, empty = empty_answer(profile.answer_schema)
    if has_empty and all(_key(empty) != _key(answer) for answer in answers):
        answers = [empty, *answers[: MAX_SAMPLES - 1]]

    barred = not declares_consensus(profile, answers)

    metric = check_delta_is_a_metric(profile, answers)
    if not metric.ok:
        # Every other check is expressed in terms of delta, so running them now
        # would report consequences instead of the cause.
        return ConformanceReport(
            profile=profile.name,
            checks=(metric,),
            barred_from_consensus_tier=barred,
        )

    checks = [metric, check_answers_round_trip(profile, answers)]
    if not barred:
        checks.append(check_consensus(profile, answers))
    return ConformanceReport(
        profile=profile.name,
        checks=tuple(checks),
        barred_from_consensus_tier=barred,
    )


def run_with_sample(
    profile: Profile, raw: Mapping[str, Any], parts: list[Part]
) -> ConformanceReport:
    """All five checks, for a profile with one raw record to adapt. Run in CI."""
    report = run(profile)
    record = profile.adapt(dict(raw), parts)
    checks = (
        *report.checks,
        check_adapter_preserves_unowned_fields(profile, raw, parts),
        check_export_reproduces_the_answer(profile, record),
    )
    return ConformanceReport(
        profile=report.profile,
        checks=checks,
        barred_from_consensus_tier=report.barred_from_consensus_tier,
    )
