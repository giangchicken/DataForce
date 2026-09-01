"""T12 · the text2text modality: what it reads off an item, what it embeds, and what it shows.

Not a stage, but it is what every stage of `load_data` and `data_quality` reads content through, so
it sits beside the record tests rather than in `tests/properties/`, which is I8 and I11 over a live
corpus.

**The encoder is a stand-in in every test here**, and that is the boundary rather than a shortcut:
`Text2Text` is handed the thing that turns a document into a vector because resolving the model
opens a file and calling it opens a socket, and the engine does neither (I1). What is this modality's
to get right is the *document* -- the turns it keeps, in order, joined one way -- and a stand-in that
reveals its input is what makes that assertable. The determinism test runs it in two processes under two hash seeds, which is
where a set iteration or an unsorted `json.dumps` would show up.

Every fixture is invented, in `objective.md` §2's shape. The Vietnamese is the
corpus's language and the spoken-digit fixtures are the ones an off-the-shelf scrubber misses.
"""

import json
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from agent_toolkit.file_utils import read_yaml
from agent_toolkit.string_utils import (
    NAME_TITLES,
    OTP_CUES,
    SPOKEN_AT,
    SPOKEN_DIGITS,
    SPOKEN_DOT,
)

from dataforce.errors import ConfigError
from dataforce.manifest import Manifest
from dataforce.modalities import Modality
from dataforce.modalities.text2text import Encoder, Text2Text, embedding_model
from dataforce.modalities.text2text.pii_detector import LANGUAGES
from dataforce.record import (
    Branch,
    Part,
    Provenance,
    Record,
    record_id_for,
)

ITEM: dict[str, Any] = {
    "id": "s4471",
    "messages": [
        {"role": "system", "content": "Chọn tool cần gọi, kèm tham số."},
        {"role": "user", "content": "Cho mình xem số dư tài khoản."},
        {"role": "assistant", "content": "Bạn cho mình mã khách hàng nhé."},
        {"role": "user", "content": "Mã của mình là 480215."},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "LookupBalance",
                        "arguments": '{"ma_khach": "480215"}',
                    },
                }
            ],
        },
        {"role": "user", "content": "Gửi giúp mình sao kê tháng này qua email."},
    ],
}

# What `edge/bootstrap.py` hands over, standing in for a call to the deployment's embedder. It
# reveals its input, so an assertion about a vector is an assertion about the document behind it.
CODE_POINTS = "def encode(document):\n    return [float(ord(c)) for c in document]\n"


def code_points(document: str) -> Sequence[float]:
    """The stand-in encoder: reversible, so the document is readable out of the vector."""
    return [float(ord(character)) for character in document]


# The manifest this repository ships, which one test below compares the fixture against.
MANIFEST = (
    Path(__file__).resolve().parents[2] / "config" / "modalities" / "text2text.yaml"
)


def a_manifest(**declared: Any) -> Manifest:
    """One `config/modalities/text2text.yaml`, already parsed, with the declarations it holds."""
    embedding = {
        "model": "bge-m3",
        "exclude_roles": ["system"],
    }
    language = declared.pop("language", "vi")
    return Manifest(
        name="text2text",
        version="1",
        declarations={"embedding": {**embedding, **declared}, "language": language},
    )


def a_modality(encode: Encoder = code_points, **declared: Any) -> Text2Text:
    """The modality under test, built the way a composition root will build it."""
    return Text2Text(a_manifest(**declared), encode)


def a_record(parts: Sequence[Part], **written: Any) -> Record:
    """One record carrying those parts, and whatever a phase has already written on it."""
    return Record(
        record_id=record_id_for(parts),
        source_id="s4471",
        branch=Branch(modality="text2text", profile="tool_decision"),
        provenance=Provenance(
            source_file_sha256="a" * 64,
            offset=0,
            ingested_at=datetime(2026, 8, 24, tzinfo=UTC),
            modality="text2text@1",
            profile="tool_decision@1",
            run_id="r1",
        ),
        content=tuple(parts),
        label=({"name": "SendStatement", "arguments": {"ky": "thang_nay"}},),
        **written,
    )


def test_the_turns_arrive_in_order_carrying_their_roles() -> None:
    """`content_parts` is one part per message, and order within a record is content (Req 7)."""
    parts = a_modality().content_parts(ITEM)

    assert [part.role for part in parts] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
    ]
    assert parts[1].text == "Cho mình xem số dư tài khoản."


def test_text_arrives_byte_identical() -> None:
    """Requirement 16: no normalisation at load. A vector is taken later, off a copy."""
    spaced = {"messages": [{"role": "user", "content": "Mã  của\tmình là 480 215."}]}

    assert a_modality().content_parts(spaced)[0].text == "Mã  của\tmình là 480 215."


def test_a_turn_that_calls_a_tool_keeps_only_what_it_said() -> None:
    """What T54 moved out of this axis, asserted from the side that stopped doing it.

    `tool_calls` is what one module in this family answers with, so the concept reads a role and a
    `content` and stops -- and `summarize` beside `tool_decision` gets a turn with no vocabulary of
    another task written onto it. Where the calls go and how they are rendered is
    `tests/stages/test_tool_decision.py`'s, which is where those assertions moved.
    """
    spoke_and_called = ITEM["messages"][4]
    assert "tool_calls" in spoke_and_called, "the fixture is the shape being ignored"

    part = a_modality().content_parts(ITEM)[4]

    assert part.role == "assistant"
    assert part.text == ""
    assert "LookupBalance" not in (part.text or "")


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ([{"type": "text", "text": "Cho mình xem số dư."}], "Cho mình xem số dư."),
        (
            [
                {"type": "text", "text": "Số dư "},
                {"type": "text", "text": "là bao nhiêu?"},
            ],
            "Số dư là bao nhiêu?",
        ),
        (
            [{"type": "image_url", "image_url": {"url": "s3://b/one.png"}}],
            '{"image_url":{"url":"s3://b/one.png"},"type":"image_url"}',
        ),
        (5, "5"),
        (None, ""),
    ],
    ids=["one-block", "two-blocks", "a-block-with-no-text", "not-a-string", "null"],
)
def test_a_content_block_item_becomes_a_record_rather_than_an_exception(
    content: Any, expected: str
) -> None:
    """Requirement 13 declares the OpenAI shape, and the content-block form is that shape.

    So this is a declared item and has to become a record -- Requirement 43's *a run always
    completes* is what a `TypeError` on item 3 of 20,000 would have broken. A block carrying no text
    is written down as canonical JSON rather than dropped, which keeps it inside `record_id`.
    """
    item = {"messages": [{"role": "user", "content": content}]}

    assert a_modality().content_parts(item)[0].text == expected


def test_a_mixed_content_block_turn_keeps_both_halves() -> None:
    """Nothing is dropped, and no separator is invented between blocks."""
    mixed = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Ảnh sao kê đây:"},
                    {"type": "image_url", "image_url": {"url": "s3://b/one.png"}},
                ],
            }
        ]
    }

    text = a_modality().content_parts(mixed)[0].text or ""

    assert text.startswith("Ảnh sao kê đây:")
    assert "s3://b/one.png" in text


def test_a_content_block_turn_hashes_the_same_way_twice() -> None:
    """The rendering is canonical, so two runs over one item give one `record_id`."""
    item = {
        "messages": [
            {
                "role": "user",
                "content": [{"type": "image_url", "image_url": {"b": 2, "a": 1}}],
            }
        ]
    }
    modality = a_modality()

    assert record_id_for(modality.content_parts(item)) == record_id_for(
        modality.content_parts(item)
    )


def test_an_item_with_no_turns_names_the_key_it_wanted() -> None:
    """A source whose turns are somewhere else is a wrong declaration, not a bad record."""
    with pytest.raises(ConfigError, match="messages"):
        a_modality().content_parts({"id": "s1", "tools": []})


def test_a_turn_with_no_role_is_refused() -> None:
    """Every turn is context and its role is what says whose; a part cannot be built without one."""
    with pytest.raises(ConfigError, match="role"):
        a_modality().content_parts({"messages": [{"content": "xin chào"}]})


def test_the_vector_leaves_out_the_roles_the_manifest_excludes() -> None:
    """`exclude_roles: [system]` is a declared, measured choice -- and it is read, not assumed."""
    parts = a_modality().content_parts(ITEM)

    document = "".join(chr(int(point)) for point in a_modality().embedding(parts))

    assert "Chọn tool cần gọi" not in document
    assert "Cho mình xem số dư tài khoản." in document


def test_excluding_no_role_embeds_every_turn() -> None:
    """The exclusion is the manifest's to make, so an empty list embeds the instruction turn too."""
    modality = a_modality(exclude_roles=[])
    parts = modality.content_parts(ITEM)

    document = "".join(chr(int(point)) for point in modality.embedding(parts))

    assert "Chọn tool cần gọi" in document


def test_the_same_input_gives_the_same_vector_in_two_processes(tmp_path: Path) -> None:
    """T12's acceptance criterion, run where a hash-ordered set would actually show up.

    Two hash seeds, because that is what varies dict and set iteration between runs. What is being
    proved is this modality's half: the document it composes and the order it composes it in. What
    the model behind the encoder answers is the other half, is the edge's, and is the half
    Requirement 23 now qualifies.
    """
    script = tmp_path / "embed.py"
    script.write_text(
        "import json\n"
        "from dataforce.manifest import Manifest\n"
        "from dataforce.modalities.text2text import Text2Text\n"
        f"{CODE_POINTS}"
        f"ITEM = {ITEM!r}\n"
        "declared = {'embedding': {'model': 'm', 'exclude_roles': ['system']}, "
        "'language': 'vi'}\n"
        'modality = Text2Text(Manifest(name="text2text", version="1", declarations=declared), encode)\n'
        "print(json.dumps(modality.embedding(modality.content_parts(ITEM))))\n",
        encoding="utf-8",
    )

    runs = [
        subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
        ).stdout
        for seed in ("0", "1")
    ]

    assert runs[0] == runs[1]
    assert json.loads(runs[0])


def test_a_media_part_is_refused_rather_than_skipped() -> None:
    """A pair is chosen once, at composition, so the wrong one is a `ConfigError` (Req 43)."""
    audio = Part(type="audio", role="user", uri="s3://bucket/one.wav", sha256="b" * 64)

    with pytest.raises(ConfigError, match="audio"):
        a_modality().embedding([audio])


def test_identity_comes_from_the_manifest() -> None:
    """Requirement 40: the filename is the identity, and nothing here has a name of its own."""
    renamed = Manifest(
        name="text2text_v2",
        version="7",
        declarations={
            "embedding": {"model": "m", "exclude_roles": []},
            "language": "vi",
        },
    )

    modality = Text2Text(renamed, code_points)

    assert (modality.modality_name, modality.modality_version) == ("text2text_v2", "7")


@pytest.mark.parametrize(
    "declarations",
    [{}, {"embedding": {}}, {"embedding": {"model": "m"}}],
    ids=["nothing", "no-keys", "no-exclude-roles"],
)
def test_an_undeclared_embedding_key_names_the_manifest(
    declarations: dict[str, Any],
) -> None:
    """The error names the file and the path, because that is what a person has to go and edit."""
    incomplete = Manifest(name="text2text", version="1", declarations=declarations)

    with pytest.raises(ConfigError, match=r"config/modalities/text2text.yaml"):
        Text2Text(incomplete, code_points)


@pytest.mark.parametrize(
    "exclude_roles",
    ["system", {"system": True}, ["system", 1], 7],
    ids=["a-bare-string", "a-mapping", "a-mixed-list", "a-number"],
)
def test_exclude_roles_that_is_not_a_list_of_roles_is_refused(
    exclude_roles: Any,
) -> None:
    """The slip that produced a green run and wrong vectors for every record.

    `exclude_roles: system` is one YAML character away from `[system]`, and
    `frozenset("system")` is five letters -- so no role matched, the instruction turn went into
    every vector, and nothing said a word. A refused run is visible; wrong vectors are not.
    """
    with pytest.raises(ConfigError, match="exclude_roles"):
        a_modality(exclude_roles=exclude_roles)


@pytest.mark.parametrize(
    "model", [["m"], "", None, 7], ids=["a-list", "empty", "null", "a-number"]
)
def test_a_model_that_is_not_a_name_is_refused(model: Any) -> None:
    """`str(["m"])` is `"['m']"`, which is a model nobody has and an error much later."""
    with pytest.raises(ConfigError, match="embedding.model"):
        embedding_model(a_manifest(model=model))


def test_the_model_name_is_read_off_the_manifest() -> None:
    """The key is read here and the endpoint is resolved at the edge; this is the seam between them."""
    assert embedding_model(a_manifest()) == "bge-m3"

    with pytest.raises(ConfigError, match=r"embedding\.model"):
        embedding_model(
            Manifest(name="text2text", version="1", declarations={"embedding": {}})
        )


def test_the_shipped_manifest_names_a_language_that_is_written_down() -> None:
    """The fixture defaults to `vi` and the committed file declares one, and a name with no
    entry in the library's tables is a `ConfigError` on the first real run and on no test."""
    shipped = read_yaml(MANIFEST)

    assert shipped["language"] in LANGUAGES
    assert shipped["language"] == "vi"


def test_a_second_language_gets_the_same_scans_and_its_own_words() -> None:
    """The defect the parameter exists for: an English corpus registering this modality used to
    get `không|một|mốt|...` and nothing usable, because a modality that provides a task family's
    framework was also deciding the family's language. The words are the library's now, so what
    this asserts is that a declared language reaches them."""
    found = {
        detector.personal_data_class: detector.scan(
            "my name is Dung, verification code one two three four five six"
        )
        for detector in a_modality(language="en").personal_data_detectors()
    }

    assert found["NAME"] == ["Dung"]
    assert found["OTP"] == ["one two three four five six"]
    assert (
        a_modality(language="vi").personal_data_detectors()[3].scan("my name is Dung")
        == []
    ), "the Vietnamese table has no `my name is`"


def test_a_language_nobody_wrote_down_is_refused() -> None:
    """Falling back to any particular language scans a Spanish corpus with Vietnamese digit words,
    finds nothing, and looks exactly like a clean corpus -- the one failure this layer cannot
    notice on its own. The message names the languages there are, because that is the fix."""
    with pytest.raises(ConfigError, match="'es'") as refused:
        a_modality(language="es")

    assert "en, vi" in str(refused.value)

    with pytest.raises(ConfigError, match="language"):
        a_modality(language=None)


def test_the_five_tables_behind_the_four_scans_agree_on_their_languages() -> None:
    """The upstream assumption `LANGUAGES` rests on, pinned where it costs nothing to hold.

    `personal_data_detectors` reads one table to say which languages there are. That is only true
    while the five agree: a language written into `OTP_CUES` and not into `SPOKEN_DIGITS` would be
    offered here and then raise a `KeyError` from inside the library on the first record, which is a
    stack trace where a `ConfigError` belongs. Asserting it here rather than intersecting five tables
    on every build is the trade -- the failure is a fact about the library, so it should break
    `make check` on the next `uv sync`, not cost a lookup in production code.
    """
    tables = (SPOKEN_DIGITS, SPOKEN_AT, SPOKEN_DOT, OTP_CUES, NAME_TITLES)

    assert LANGUAGES == {"en", "vi"}
    for table in tables:
        assert set(table) == LANGUAGES


def test_there_are_four_classes_and_each_carries_a_scan_that_runs() -> None:
    """One detector per class of personal data, and a class an identifier alone cannot reach.

    `CUSTOMER_ID` was a fifth, matching any run of six or more digits: a bare `480215` is an order
    number as often as a customer code, so it flagged every invoice in the corpus and layer two paid
    for each one. What is left is the same shape behind a cue word, which is `OTP`.
    """
    detectors = a_modality().personal_data_detectors()
    classes = [detector.personal_data_class for detector in detectors]

    assert classes == ["PHONE", "EMAIL", "OTP", "NAME"]
    assert len(set(classes)) == len(classes)
    for detector in detectors:
        assert detector.personal_data_class.isupper()
        assert detector.scan("nothing personal here") == []


@pytest.mark.parametrize(
    ("hit", "expected", "found"),
    [
        ("Số của mình là 0900123456.", "PHONE", "0900123456"),
        (
            "Số là không chín không một hai ba bốn năm sáu bảy.",
            "PHONE",
            "không chín không một hai ba bốn năm sáu bảy",
        ),
        ("Email của mình là an.nguyen@vidu.vn nhé.", "EMAIL", "an.nguyen@vidu.vn"),
        ("Mã xác nhận là 480215.", "OTP", "480215"),
        (
            "Mã xác nhận là bốn tám không hai một năm.",
            "OTP",
            "bốn tám không hai một năm",
        ),
        ("Chào anh Nguyễn Văn Dũng nhé.", "NAME", "Nguyễn Văn Dũng"),
    ],
    ids=[
        "written-phone",
        "spoken-phone",
        "email",
        "written-otp",
        "spoken-otp",
        "name-behind-its-title",
    ],
)
def test_layer_one_finds_the_spoken_forms_a_scrubber_misses(
    hit: str, expected: str, found: str
) -> None:
    """Requirement 18: one scan per class, each finding the written form and the dictated one."""
    scanned = {
        detector.personal_data_class: detector.scan(hit)
        for detector in a_modality().personal_data_detectors()
    }

    assert found in scanned[expected]


def test_one_pass_over_the_raw_text_finds_both_spellings() -> None:
    """The half of Requirement 18 that used to fail silently, and the mechanism T54 retired.

    A pattern written in correct Vietnamese cannot match `khong chin`, so this stage ran every
    pattern twice -- once over the raw text and once over a tone-stripped view built word by word to
    keep the offsets true. The library's patterns carry both spellings, so one pass finds both and
    there is no normalisation for an offset to survive.
    """
    detectors = {
        detector.personal_data_class: detector.scan
        for detector in a_modality().personal_data_detectors()
    }

    assert detectors["OTP"]("Ma xac nhan la bon tam khong hai mot nam.") == [
        "bon tam khong hai mot nam"
    ]
    assert detectors["OTP"]("Mã xác nhận là bốn tám không hai một năm.") == [
        "bốn tám không hai một năm"
    ]


def test_a_bare_identifier_is_not_a_class_layer_one_has() -> None:
    """The stated cost, asserted so a reader finds it here rather than in a corpus.

    `480215` with no cue word in front of it is an order number as often as a customer code, and a
    scan claiming it flags every invoice. Adding a fifth class is a rule added in `agent-toolkit`,
    reviewable in a diff there -- which is why this is a test about reach and not a TODO.
    """
    bare = "Đơn của mình là 480215."
    scanned = {
        detector.personal_data_class: detector.scan(bare)
        for detector in a_modality().personal_data_detectors()
    }

    assert scanned == {"PHONE": [], "EMAIL": [], "OTP": [], "NAME": []}


def test_it_answers_every_member_its_protocol_declares() -> None:
    """The runtime half of what `modality.py`'s `TYPE_CHECKING` block proves statically.

    A `Protocol` is not runtime-checkable and `mypy --strict` reads `src/` alone, so this is what
    catches a renamed member from the test side -- and it reads as the list of what a modality is.
    Asserted as an equality in both directions: I23 checks the same closure off the tree, and this
    checks it off a live instance, where a member arriving through a decorator or a base class would
    show up and an AST scan would not see it.

    `modality_name` rather than `name` since T52: a profile is one module inside a concept and says
    so by subclassing it, so one object answers this protocol and `Profile` at once -- and a bare
    `name` on both is one attribute where `Branch(modality=…, profile=…)` needs two. This class is
    the base and never sees the other half; `tests/stages/test_tool_decision.py` asserts the union.
    """
    declared = {name for name in dir(Modality) if not name.startswith("_")} | set(
        Modality.__annotations__
    )

    assert declared == {
        "content_parts",
        "embedding",
        "modality_name",
        "modality_version",
        "personal_data_detectors",
    }
    assert {name for name in dir(a_modality()) if not name.startswith("_")} == declared
