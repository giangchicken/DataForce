"""T12 · the text2text modality: what it reads off an item, what it embeds, and what it shows.

Not a stage, but it is what every stage of `load_data` and `data_quality` reads content through, so
it sits beside the record tests rather than in `tests/properties/`, which is I8 and I11 over a live
corpus.

**The encoder is a stand-in in every test here**, and that is the boundary rather than a shortcut:
`Text2Text` is handed the thing that turns a document into a vector because loading a static model
opens a file and the engine opens none (I1). What is this modality's to get right is the *document*
-- the turns it keeps, in order, joined one way -- and a stand-in that reveals its input is what
makes that assertable. The determinism test runs it in two processes under two hash seeds, which is
where a set iteration or an unsorted `json.dumps` would show up.

Every fixture is invented (AGENTS.md §9), in `objective.md` §2's shape. The Vietnamese is the
corpus's language and the spoken-digit fixtures are the ones an off-the-shelf scrubber misses.
"""

import json
import re
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from agent_toolkit.file_utils import read_yaml
from agent_toolkit.string_utils import normalize_text

from dataforce.errors import ConfigError
from dataforce.manifest import Manifest
from dataforce.modalities import Modality
from dataforce.modalities.text2text import Encoder, Text2Text, embedding_model
from dataforce.modalities.text2text.utils import personal_data_detectors, spaced
from dataforce.record import (
    AgreementScores,
    AiReview,
    Branch,
    PanelVerdict,
    Part,
    Provenance,
    Record,
    ReviewSelection,
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

# What `edge/bootstrap.py` will hand over, standing in for the loaded static model. It reveals its
# input, so an assertion about a vector is an assertion about the document that produced it.
CODE_POINTS = "def encode(document):\n    return [float(ord(c)) for c in document]\n"


def code_points(document: str) -> Sequence[float]:
    """The stand-in encoder: reversible, so the document is readable out of the vector."""
    return [float(ord(character)) for character in document]


# The manifest this repository ships, which one test below compares the fixture against.
MANIFEST = (
    Path(__file__).resolve().parents[2] / "config" / "modalities" / "text2text.yaml"
)

# The language layer one is filled with. Declared in `config/modalities/text2text.yaml` since the
# modality stopped holding it, and repeated here because a fixture that read the real file would
# make every detection test depend on a committed file's current contents. The values are that
# file's, and `test_the_shipped_manifest_declares_a_working_language` is what compares the two.
A_LANGUAGE: dict[str, Any] = {
    "spoken": {
        "digits": [
            "không",
            "một",
            "mốt",
            "hai",
            "ba",
            "bốn",
            "tư",
            "năm",
            "lăm",
            "sáu",
            "bảy",
            "tám",
            "chín",
        ],
        "zero": "không",
        "at": "a còng",
        "dot": "chấm",
    },
    "identifier_digits": 6,
    "phone": {"prefix": "0", "written_digits": [10, 11], "spoken_words": [9, 10]},
}


def a_manifest(**declared: Any) -> Manifest:
    """One `config/modalities/text2text.yaml`, already parsed, with the declarations it holds."""
    embedding = {
        "model": "minishlab/potion-multilingual-128M",
        "exclude_roles": ["system"],
    }
    language = declared.pop("personal_data", A_LANGUAGE)
    return Manifest(
        name="text2text",
        version="1",
        declarations={
            "embedding": {**embedding, **declared},
            "personal_data": language,
        },
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


@pytest.mark.parametrize(
    "arguments",
    [
        '{"ma_khach": "480215", "ky": "thang_nay"}',
        '{ "ky" : "thang_nay" ,\n  "ma_khach" : "480215" }',
        {"ma_khach": "480215", "ky": "thang_nay"},
    ],
    ids=["json-string", "reordered-and-spaced", "object"],
)
def test_one_call_spelled_three_ways_is_one_part_and_one_id(arguments: Any) -> None:
    """Requirement 15, asserted against the first spelling rather than against itself."""
    spelled = {
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "SendStatement", "arguments": arguments}}
                ],
            }
        ]
    }
    canonical = {
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "function": {
                            "name": "SendStatement",
                            "arguments": '{"ma_khach": "480215", "ky": "thang_nay"}',
                        }
                    }
                ],
            }
        ]
    }
    modality = a_modality()

    written = modality.content_parts(spelled)
    expected = modality.content_parts(canonical)

    assert len(written) == 1
    assert written == expected
    assert record_id_for(written) == record_id_for(expected)


def test_a_turn_that_both_speaks_and_calls_carries_both() -> None:
    """Dropping either would lose content `record_id` has to cover."""
    both = {
        "messages": [
            {
                "role": "assistant",
                "content": "Mình tra cứu ngay nhé.",
                "tool_calls": [
                    {"function": {"name": "LookupBalance", "arguments": "{}"}}
                ],
            }
        ]
    }

    text = a_modality().content_parts(both)[0].text or ""

    assert text.startswith("Mình tra cứu ngay nhé.\n")
    assert '"LookupBalance"' in text


def test_a_malformed_arguments_string_is_written_down_rather_than_refused() -> None:
    """Requirement 43: a run always completes, and a malformed turn is evidence, not a stop."""
    broken = {
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {"function": {"name": "OpenTicket", "arguments": "{not json"}}
                ],
            }
        ]
    }

    assert "{not json" in (a_modality().content_parts(broken)[0].text or "")


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
    proved is this modality's half: the document it composes and the order it composes it in. The
    model behind the encoder is static (Requirement 23), which is the other half and is the edge's.
    """
    script = tmp_path / "embed.py"
    script.write_text(
        "import json\n"
        "from dataforce.manifest import Manifest\n"
        "from dataforce.modalities.text2text import Text2Text\n"
        f"{CODE_POINTS}"
        f"ITEM = {ITEM!r}\n"
        f"declared = {{'embedding': {{'model': 'm', 'exclude_roles': ['system']}}, "
        f"'personal_data': {A_LANGUAGE!r}}}\n"
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
            "personal_data": A_LANGUAGE,
        },
    )

    modality = Text2Text(renamed, code_points)

    assert (modality.name, modality.version) == ("text2text_v2", "7")


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
    """The key is read here and the model is loaded at the edge; this is the seam between them."""
    assert embedding_model(a_manifest()) == "minishlab/potion-multilingual-128M"

    with pytest.raises(ConfigError, match=r"embedding\.model"):
        embedding_model(
            Manifest(name="text2text", version="1", declarations={"embedding": {}})
        )


def test_the_shipped_manifest_declares_a_working_language() -> None:
    """P31, and the reason `A_LANGUAGE` is a fixture rather than a read of the committed file.

    Every detection test above runs against the fixture, so nothing would notice if the shipped
    file drifted from it -- or declared something the readers refuse, which would be a
    `ConfigError` on the first real run and on no test. This is the one place the two meet.
    """
    shipped = read_yaml(MANIFEST)

    assert shipped["personal_data"] == A_LANGUAGE
    assert len(
        personal_data_detectors(
            Manifest(name="text2text", version="1", declarations=shipped)
        )
    ) == len(a_modality().personal_data_detectors())


def test_a_second_language_gets_the_same_shapes_and_its_own_words() -> None:
    """The defect this declaration exists for: an English corpus registering this modality used
    to get `không|một|mốt|...` and nothing usable, because a modality that provides a task
    family's framework was also deciding the family's language."""
    english = {
        "spoken": {
            "digits": [
                "zero",
                "oh",
                "one",
                "two",
                "three",
                "four",
                "five",
                "six",
                "seven",
                "eight",
                "nine",
            ],
            "zero": "zero",
            "at": "at",
            "dot": "dot",
        },
        "identifier_digits": 6,
        "phone": {"prefix": "0", "written_digits": [10, 11], "spoken_words": [9, 10]},
    }
    spoken = {
        detector.name: detector.pattern
        for detector in a_modality(personal_data=english).personal_data_detectors()
    }

    assert re.search(spoken["customer_id_spoken"], "four eight zero two one five")
    assert re.search(spoken["email_spoken"], "an at vi du dot vn")
    assert "không" not in spoken["customer_id_spoken"]
    assert spoken["customer_id_digits"] == r"\d(?:[\s.-]?\d){5,}", "shapes do not move"


def test_a_declared_phrase_matches_however_its_words_are_spaced() -> None:
    """`a còng` is two words, so the pattern joins them on `\\s+` rather than on one space."""
    assert spaced("a còng") == r"a\s+còng"
    assert re.search(spaced("a còng"), "an  a\ncòng vidu")


@pytest.mark.parametrize(
    "digits",
    [["một", "."], ["một", "(hai"], ["một", ""], "một", [], ["một", 9]],
    ids=["a-dot", "a-group", "blank", "a-bare-string", "empty", "a-number"],
)
def test_a_digit_list_that_is_not_words_is_refused(digits: Any) -> None:
    """These go into a regular expression. `.` compiles, matches anything, and says nothing --
    so a declaration that is not a word is refused where it is read (P22)."""
    with pytest.raises(ConfigError, match="spoken.digits"):
        a_modality(
            personal_data={
                **A_LANGUAGE,
                "spoken": {**A_LANGUAGE["spoken"], "digits": digits},
            }
        )


@pytest.mark.parametrize(
    "length",
    [0, -1, "six", 6.5, True, None],
    ids=["zero", "negative", "a-word", "a-float", "a-bool", "null"],
)
def test_an_identifier_length_that_is_not_a_count_is_refused(length: Any) -> None:
    """A floor of 0 makes every digit a hit; `True` is an `int` in Python and would read as 1."""
    with pytest.raises(ConfigError, match="identifier_digits"):
        a_modality(personal_data={**A_LANGUAGE, "identifier_digits": length})


@pytest.mark.parametrize(
    "span",
    [[11, 10], [10], [10, 11, 12], 10, [10, "eleven"], [0, 11], [True, 11]],
    ids=[
        "backwards",
        "one-edge",
        "three-edges",
        "a-number",
        "a-word",
        "zero-floor",
        "a-bool",
    ],
)
def test_a_phone_span_that_is_not_two_counts_is_refused(span: Any) -> None:
    """A floor above its ceiling matches nothing at all, and a detector that matches nothing
    looks exactly like a clean corpus -- which is the one failure this layer cannot notice."""
    with pytest.raises(ConfigError, match="phone.written_digits"):
        a_modality(
            personal_data={
                **A_LANGUAGE,
                "phone": {**A_LANGUAGE["phone"], "written_digits": span},
            }
        )


def test_the_two_phone_lengths_disagree_by_one_and_the_file_says_so() -> None:
    """Declaring a literal must not move a boundary: the written shape matched ten or eleven
    digits and the spoken shape nine or ten words before these lines existed, and both still do.
    The discrepancy is inherited, and the manifest is where it is now visible."""
    declared = read_yaml(MANIFEST)["personal_data"]["phone"]

    assert declared["written_digits"] != declared["spoken_words"]
    assert "inherited, not chosen" in MANIFEST.read_text(encoding="utf-8")


def test_every_detector_carries_two_patterns_that_compile() -> None:
    """A pattern that does not compile is a detector that finds nothing and says nothing."""
    detectors = a_modality().personal_data_detectors()

    assert len(detectors) == 6
    for detector in detectors:
        assert re.compile(detector.pattern)
        assert re.compile(detector.tone_stripped_pattern)
        assert detector.personal_data_class.isupper()


def test_the_detector_names_are_distinct() -> None:
    """A name is what a noisy detector is turned down by, so two of them cannot share one."""
    named = [detector.name for detector in a_modality().personal_data_detectors()]

    assert len(set(named)) == len(named)


@pytest.mark.parametrize(
    ("hit", "expected"),
    [
        ("Mã của mình là 480215.", "CUSTOMER_ID"),
        ("Số của mình là 0900123456.", "PHONE"),
        ("Mã của mình là bốn tám không hai một năm.", "CUSTOMER_ID"),
        ("Số là không chín không một hai ba bốn năm sáu bảy.", "PHONE"),
        ("Email của mình là an.nguyen@vidu.vn nhé.", "EMAIL"),
        ("Email là an chấm nguyen a còng vi du chấm vn.", "EMAIL"),
    ],
    ids=[
        "written-id",
        "written-phone",
        "spoken-id",
        "spoken-phone",
        "email",
        "spoken-email",
    ],
)
def test_layer_one_finds_the_spoken_forms_a_scrubber_misses(
    hit: str, expected: str
) -> None:
    """Requirement 18, over the two texts every pattern is run against."""
    stripped = normalize_text(hit, remove_tone_marks=True)
    found = {
        detector.personal_data_class
        for detector in a_modality().personal_data_detectors()
        if re.search(detector.pattern, hit)
        or re.search(detector.tone_stripped_pattern, stripped)
    }

    assert expected in found


def test_a_pattern_written_with_tone_marks_finds_the_stripped_text_too() -> None:
    """The half of Requirement 18 that fails silently: correct Vietnamese against `khong chin`."""
    typed = "Ma cua minh la bon tam khong hai mot nam."
    spoken = next(
        detector
        for detector in a_modality().personal_data_detectors()
        if detector.name == "customer_id_spoken"
    )

    assert not re.search(spoken.pattern, typed)
    assert re.search(spoken.tone_stripped_pattern, typed)


def test_the_display_half_is_community_tags_over_the_conversation() -> None:
    """Requirement 52 and Requirement 31: `<Paragraphs>`, and only this half's own data."""
    modality = a_modality()
    record = a_record(modality.content_parts(ITEM))

    shown = modality.display_config(record)

    assert "<Chat" not in shown.tags
    assert '<Paragraphs name="conversation"' in shown.tags
    assert set(shown.data) == {"conversation"}
    assert shown.data["conversation"][1] == {
        "role": "user",
        "content": "Cho mình xem số dư tài khoản.",
    }


def test_no_model_output_reaches_the_display_half() -> None:
    """Requirement 30, asserted on a record that already carries all three `ai_review` keys."""
    modality = a_modality()
    reviewed = a_record(
        modality.content_parts(ITEM),
        ai_review=AiReview(
            jury=PanelVerdict(
                panel_version=1,
                prompt_version="jury.v1",
                invalid_votes=0,
                plurality=({"name": "LookupBalance", "arguments": {}},),
                final_prediction=({"name": "LookupBalance", "arguments": {}},),
            ),
            cohesion=AgreementScores(
                self_agreement=0.9, label_agreement=0.1, method="answer_distance"
            ),
            triage=ReviewSelection(
                bucket="disagreed",
                stratum="audit",
                selected_for_review=True,
                reason="label_agreement below the boundary",
            ),
        ),
    )

    shown = json.dumps(
        modality.display_config(reviewed).model_dump(), ensure_ascii=False
    )

    for leaked in ("jury", "cohesion", "triage", "disagreed", "audit", "0.9"):
        assert leaked not in shown


def test_it_answers_every_member_its_protocol_declares() -> None:
    """The runtime half of what `utils.py`'s `TYPE_CHECKING` block proves statically.

    A `Protocol` is not runtime-checkable and `mypy --strict` reads `src/` alone, so this is what
    catches a renamed member from the test side -- and it reads as the list of what a modality is.
    Asserted as an equality in both directions: I23 checks the same closure off the tree, and this
    checks it off a live instance, where a member arriving through a decorator or a base class would
    show up and an AST scan would not see it.
    """
    declared = {name for name in dir(Modality) if not name.startswith("_")} | set(
        Modality.__annotations__
    )

    assert declared == {
        "content_parts",
        "display_config",
        "embedding",
        "name",
        "personal_data_detectors",
        "version",
    }
    assert {name for name in dir(a_modality()) if not name.startswith("_")} == declared
