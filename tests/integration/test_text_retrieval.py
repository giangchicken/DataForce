"""Does `potion-multilingual-128M` actually separate Vietnamese near-duplicates?

An assumption in the profile spec, checked here against the corpus rather than
asserted. The pairs are not hand-made: 491 records in the first corpus share a user
turn with exactly one other record, which is a near-duplicate the corpus itself
supplies -- same conversation, different tool catalog.

This test is also the reason `embed` leaves the system turn out. With it in, every
one of these retrievals fails.
"""

from __future__ import annotations

import random
from collections import defaultdict
from pathlib import Path

import pytest
from agent_toolkit.file_utils import iter_json_array_file, read_yaml
from agent_toolkit.string_utils import compute_hash
from conftest import REPO_ROOT

from dataforce.modalities.text import TEXT
from dataforce.shared.record import TextPart

pytestmark = pytest.mark.integration

PAIRS = 200
DISTRACTORS = 300
FLOOR = 0.95


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = sum(x * x for x in a) ** 0.5 * sum(y * y for y in b) ** 0.5
    return dot / norm


@pytest.fixture(scope="module")
def corpus() -> Path:
    declared = read_yaml(REPO_ROOT / "params.yaml")["source"]["path"]
    path = REPO_ROOT / declared
    if not path.exists():
        pytest.skip(f"{declared} is not present; data/raw/ is deliberately untracked")
    return path


def test_a_near_duplicate_is_retrieved_before_any_unrelated_record(
    corpus: Path,
) -> None:
    by_user: dict[str, list[list[TextPart]]] = defaultdict(list)
    everything: list[list[TextPart]] = []
    for raw in iter_json_array_file(corpus):
        parts = [part for part in TEXT.load(raw) if isinstance(part, TextPart)]
        user = next(part.text for part in parts if part.role == "user")
        by_user[compute_hash(user, "sha256")].append(parts)
        everything.append(parts)

    pairs = [group for group in by_user.values() if len(group) == 2][:PAIRS]
    assert len(pairs) == PAIRS, f"only {len(pairs)} duplicate pairs in this source"

    paired = [parts for pair in pairs for parts in pair]
    unrelated = random.Random(20260819).sample(everything, DISTRACTORS)
    vectors = [list(TEXT.embed(list(parts))) for parts in paired + unrelated]

    hits = 0
    for index in range(len(paired)):
        partner = index + 1 if index % 2 == 0 else index - 1
        scores = [
            (cosine(vectors[index], other), position)
            for position, other in enumerate(vectors)
            if position != index
        ]
        hits += max(scores)[1] == partner

    precision = hits / len(paired)
    assert precision >= FLOOR, (
        f"precision@1 is {precision:.3f} over {len(paired)} retrievals; the profile "
        "spec's assumption about this embedder does not hold and the "
        "sentence-transformer fallback is due"
    )


def test_two_records_differing_only_in_their_catalog_embed_identically(
    corpus: Path,
) -> None:
    """Why the system turn is excluded, asserted structurally rather than by score."""
    conversation = [
        TextPart(role="user", text="cho tôi kiểm tra hạn mức thẻ"),
        TextPart(role="assistant", text='["Lookup00_0a"]'),
    ]
    one = [TextPart(role="system", text="TOOLS:\n[A]\nMục đích: một"), *conversation]
    other = [
        TextPart(role="system", text="TOOLS:\n[B]\nMục đích: hai khác hẳn"),
        *conversation,
    ]

    assert list(TEXT.embed(list(one))) == list(TEXT.embed(list(other)))
