"""Measure the source file, and say which measurement moved since the last one.

The source changed four times in five weeks, and `label_assistant_mismatch` going
from 48 to 0 was discovered by accident. Every count the profile spec quotes
describes one SHA-256 rather than "the corpus", so this command emits them all
against the digest of the file it read, and refuses to overwrite a committed
baseline that disagrees with what it just measured.

Streamed throughout: the file is 126 MiB and is never held whole, which is why the
user turns are counted by digest rather than kept.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from agent_toolkit.file_utils import iter_json_array_file, read_yaml, write_json
from agent_toolkit.string_utils import compute_hash

from dataforce.modalities.base import Modality
from dataforce.profiles.tool_decision.adapter import PROVENANCE_KEY, catalog_names
from dataforce.profiles.tool_decision.profile import ToolDecisionProfile
from dataforce.shared.record import Record, TextPart

__all__ = ["BASELINE", "drift", "measure", "profile_corpus", "source_digest"]

BASELINE = Path("metrics/corpus_profile.json")
PARAMS = Path("params.yaml")

# Read in blocks, so a 126 MiB source never becomes a 126 MiB string. `compute_hash`
# hashes text already in memory, which is the one thing this must not do.
_DIGEST_BLOCK = 1 << 20


def source_digest(path: Path) -> str:
    """The file's SHA-256, without reading the file into memory."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256", _bufsize=_DIGEST_BLOCK).hexdigest()


def _percentile(ordered: list[int], quantile: float) -> int:
    """Nearest-rank, on the sorted values. Stated because a count needs a definition."""
    return ordered[int(quantile * (len(ordered) - 1))]


def _records(
    path: Path, modality: Modality, profile: ToolDecisionProfile, digest: str
) -> Iterator[tuple[Any, Record]]:
    """Every raw item with the record it adapts to, one at a time."""
    for offset, raw in enumerate(iter_json_array_file(path)):
        parts = modality.load(raw)
        yield (
            raw,
            profile.adapt(
                {
                    **raw,
                    PROVENANCE_KEY: {
                        "source": {
                            "file_sha256": digest,
                            "offset": offset,
                            # Nothing is being ingested here; measuring is not a run,
                            # and stamping a time would put one in a metrics file that
                            # has to be byte-comparable against the committed baseline.
                            "ingested_at": "",
                        },
                        "producer": {
                            "modality": f"{modality.name}@{modality.version}",
                            "profile": f"{profile.name}@{profile.version}",
                        },
                    },
                },
                parts,
            ),
        )


def _turn(record: Record, role: str) -> str:
    return next(
        (p.text for p in record.content if isinstance(p, TextPart) and p.role == role),
        "",
    )


def measure(
    path: Path, modality: Modality, profile: ToolDecisionProfile
) -> dict[str, Any]:
    """Every property this corpus is described by, measured over every record.

    Every field name it reads comes from the profile's source contract. A profiler that
    spells `llm_model` is a profiler about one file, and this one has to keep working when
    the next file calls it something else.
    """
    digest = source_digest(path)
    contract = profile.contract
    checks = profile.validity_checks()
    detectors = modality.privacy_detectors()

    instruction_role = contract.role_name("instruction")
    conversation_role = contract.role_name("conversation")
    labelling_model = contract.field_name("labelling_model")
    prior_label = contract.field_name("prior_label")
    label_provenance = contract.field_name("label_provenance")
    human_checked = contract.field_name("human_checked")
    human_checked_by = contract.field_name("human_checked_by")

    records = 0
    cardinality: Counter[int] = Counter()
    tool_names: Counter[str] = Counter()
    catalog_sizes: Counter[int] = Counter()
    fingerprints: Counter[str] = Counter()
    key_sets: Counter[tuple[str, ...]] = Counter()
    meta_keys: Counter[str] = Counter()
    checked_by: Counter[str] = Counter()
    label_sources: Counter[str] = Counter()
    checked = 0
    checked_and_changed = 0
    models: Counter[str] = Counter()
    invalid = Counter({name: 0 for name in checks})
    signals = Counter({detector.__name__: 0 for detector in detectors})
    user_digests: Counter[str] = Counter()
    pair_digests: Counter[str] = Counter()
    prompt_sizes: list[int] = []
    total_characters = 0
    relabelled = 0
    relabelled_changed = 0

    for raw, record in _records(path, modality, profile, digest):
        records += 1
        label = record.label or []
        cardinality[len(label)] += 1
        tool_names.update(label)
        catalog_sizes[len(catalog_names(record))] += 1
        fingerprints[profile.group_key(record)] += 1
        # The source's own `meta`, not the record's: `adapt` adds the fields the
        # item carried outside `meta`, and what drifted is what the file contains.
        key_sets[tuple(sorted(raw.get("meta") or {}))] += 1
        # `.keys()`, not the mapping: Counter.update over a dict adds its *values*.
        meta_keys.update((raw.get("meta") or {}).keys())
        if record.meta.get(human_checked):
            checked += 1
            checked_by.update(record.meta.get(human_checked_by) or ["unstated"])
            if record.meta.get(prior_label, label) != label:
                checked_and_changed += 1
        if label_provenance in record.meta:
            label_sources[str(record.meta[label_provenance])] += 1
        models[record.meta.get(labelling_model) or "unstated"] += 1
        for name, check in checks.items():
            if check(record):
                invalid[name] += 1
        for detector in detectors:
            signals[detector.__name__] += bool(detector(record.content))
        system = _turn(record, instruction_role)
        user = _turn(record, conversation_role)
        prompt_sizes.append(len(system) + len(user))
        total_characters += len(system) + len(user)
        user_digests[compute_hash(user, "sha256")] += 1
        pair_digests[compute_hash(f"{system}\n{user}", "sha256")] += 1
        if prior_label in record.meta:
            relabelled += 1
            if record.meta[prior_label] != label:
                relabelled_changed += 1

    prompt_sizes.sort()
    largest, largest_count = fingerprints.most_common(1)[0]
    return {
        # No path. A source is identified by its digest, `params.yaml` already
        # declares where it was read from, and the one thing a committed metrics file
        # must never carry is somebody's absolute filesystem layout.
        "source": {"sha256": digest, "bytes": path.stat().st_size},
        "records": records,
        "answer_cardinality": {str(k): cardinality[k] for k in sorted(cardinality)},
        "labels": {
            "distinct_tool_names": len(tool_names),
            "most_frequent": list(tool_names.most_common(1)[0]) if tool_names else [],
            "relabelled_once": relabelled,
            "relabelled_and_changed": relabelled_changed,
        },
        "catalog_size": {
            "min": min(catalog_sizes),
            "max": max(catalog_sizes),
            "distribution": {str(k): catalog_sizes[k] for k in sorted(catalog_sizes)},
        },
        "catalog_fingerprints": {
            "distinct": len(fingerprints),
            "singletons": sum(1 for count in fingerprints.values() if count == 1),
            "largest": {"fingerprint": largest, "records": largest_count},
        },
        "meta_key_sets": {
            "distinct": len(key_sets),
            "sets": [
                {"keys": list(keys), "records": count}
                for keys, count in sorted(
                    key_sets.items(), key=lambda kv: (-kv[1], kv[0])
                )
            ],
        },
        "labelling_model": dict(sorted(models.items())),
        # Which records a person has already looked at -- the gold pool, which the
        # manifest names. Counted per key as well as per key-set, so a population
        # appearing or shrinking in `meta` is a drift rather than a discovery.
        "meta_keys": dict(sorted(meta_keys.items())),
        "gold": {
            "field": contract.gold_from,
            "records": checked,
            "by_source": dict(sorted(checked_by.items())),
            "and_the_label_changed": checked_and_changed,
        },
        "label_source": dict(sorted(label_sources.items())),
        "duplicates": {
            "user_turn_groups": sum(1 for c in user_digests.values() if c > 1),
            "user_turn_records": sum(c for c in user_digests.values() if c > 1),
            "system_user_pair_groups": sum(1 for c in pair_digests.values() if c > 1),
        },
        "prompt_characters": {
            "total": total_characters,
            "mean": round(total_characters / records),
            "p50": _percentile(prompt_sizes, 0.50),
            "p90": _percentile(prompt_sizes, 0.90),
            "p99": _percentile(prompt_sizes, 0.99),
        },
        "invalid_counts": dict(invalid),
        # Empty until the modality declares detectors; then five counts appear here
        # without this module learning what a phone number looks like.
        "privacy_signals": dict(signals),
    }


def _leaves(value: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            yield from _leaves(nested, f"{path}.{key}" if path else str(key))
    else:
        yield path, value


def drift(baseline: Mapping[str, Any], measured: Mapping[str, Any]) -> list[str]:
    """Which counts moved, named one per line, in the baseline's own order."""
    now = dict(_leaves(measured))
    moved = [
        f"{where}: was {was!r}, now {now.get(where, '<absent>')!r}"
        for where, was in _leaves(baseline)
        if where not in now or now[where] != was
    ]
    appeared = [
        f"{where}: absent before, now {value!r}"
        for where, value in now.items()
        if where not in dict(_leaves(baseline))
    ]
    return moved + appeared


def profile_corpus(
    modality: Modality,
    profile: ToolDecisionProfile,
    *,
    accept: bool = False,
    baseline: Path = BASELINE,
    params: Path = PARAMS,
) -> tuple[dict[str, Any], list[str]]:
    """Measure the declared source, and write the baseline only if nothing moved.

    Returns the measurement and the drift. A drift is not written over: the point of
    the file is to be the last agreed measurement, and agreeing to a new one is a
    commit, which is what `accept` stands for.
    """
    declared = read_yaml(params)["source"]
    measured = measure(Path(declared["path"]), modality, profile)
    if not baseline.exists() or accept:
        write_json(baseline, measured)
        return measured, []
    moved = drift(read_yaml(baseline), measured)
    if not moved:
        write_json(baseline, measured)
    return measured, moved
