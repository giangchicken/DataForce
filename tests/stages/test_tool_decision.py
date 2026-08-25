"""T13 · the tool_decision profile: what an answer is, how two differ, what makes one invalid.

Not a stage either, and here for the reason `test_text2text.py` gives: everything a stage of
`data_quality`, `ai_review` and `human_review` knows about the task comes from this one object.

**Four of the fifteen members carry real algorithms** and get the weight here: `answer_schema`
(`oneOf` per offered tool), `answer_distance` (name-first and soft), `vote_consensus` (per name,
then per argument) and `label_checks` (five). δ is asserted as the *ordering* the spec hand-works,
not as three numbers that happen to come out right, and the Jaccard reduction is asserted to the
bit -- every threshold measured before arguments existed still has to describe this δ.

`jsonschema` is the outside opinion in this module: `answer_schema` is checked by validating
fixtures against it rather than by reading the dict it returns, which is what makes "rejects
`OpenTicket` carrying `LookupBalance`'s argument" a fact about the schema and not about our
expectations of it.

Every fixture is invented (AGENTS.md §9), in `objective.md` §2's shape.
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import jsonschema
import pytest

from dataforce.errors import ConfigError
from dataforce.manifest import Manifest
from dataforce.modalities.text2text import Text2Text
from dataforce.modalities.text2text.utils import stated_calls
from dataforce.profiles import Profile
from dataforce.profiles.tool_decision import ToolDecision
from dataforce.record import (
    SPOKEN_AND_STATED,
    Branch,
    FinalLabel,
    HumanReview,
    Part,
    Provenance,
    Record,
    StoredAnswer,
    record_id_for,
)

QUESTION = "Những tool nào cần được gọi?"

CATALOG: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "LookupBalance",
            "description": "Tra cứu số dư tài khoản của khách hàng.",
            "parameters": {
                "type": "object",
                "properties": {"ma_khach": {"type": "string"}},
                "required": ["ma_khach"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "SendStatement",
            "description": "Gửi sao kê cho khách hàng qua email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ma_khach": {"type": "string"},
                    "ky": {"type": "string", "enum": ["thang_nay", "thang_truoc"]},
                },
                "required": ["ma_khach", "ky"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "OpenTicket",
            "description": "Mở phiếu hỗ trợ.",
            "parameters": {
                "type": "object",
                "properties": {"noi_dung": {"type": "string"}},
            },
        },
    },
]

TURNS = (
    ("system", "Chọn tool cần gọi, kèm tham số."),
    ("user", "Cho mình xem số dư tài khoản."),
    ("assistant", "Bạn cho mình mã khách hàng nhé."),
    ("user", "Gửi giúp mình sao kê tháng này qua email."),
)

SENT = {"name": "SendStatement", "arguments": {"ma_khach": "480215", "ky": "thang_nay"}}
LOOKED_UP = {"name": "LookupBalance", "arguments": {"ma_khach": "480215"}}
TICKETED = {"name": "OpenTicket", "arguments": {"noi_dung": "khách cần hỗ trợ"}}

DECLARED: dict[str, Any] = {
    "prompts": {"question": "profiles/tool_decision/question.v2"},
    "max_calls": 2,
    "answer_control": "names_and_json_arguments",
    "shape": "openai_chat_completion",
    "roles": {"target": "assistant"},
    "label": {"at": "label"},
    "gold": {"from": "human_checked"},
}

PROVENANCE = {
    "source_file_sha256": "a" * 64,
    "offset": 41,
    "ingested_at": "2026-08-24T00:00:00Z",
    "modality": "text2text@1",
    "profile": "tool_decision@1",
    "run_id": "r1",
}


def a_manifest(**declared: Any) -> Manifest:
    """One `config/profiles/tool_decision.yaml`, already parsed."""
    return Manifest(
        name="tool_decision",
        version="1",
        modality=declared.pop("modality", "text2text"),
        declarations={**DECLARED, **declared},
    )


def a_profile(question: str = QUESTION, **declared: Any) -> ToolDecision:
    """The profile under test, built the way a composition root will build it."""
    return ToolDecision(a_manifest(**declared), question)


def parts(turns: Sequence[tuple[str, str]] = TURNS) -> tuple[Part, ...]:
    """The content, as `text2text` would have produced it."""
    return tuple(Part(type="text", role=role, text=text) for role, text in turns)


def a_text2text() -> Text2Text:
    """The modality this profile composes with. Its encoder is never called from here."""
    return Text2Text(
        Manifest(
            name="text2text",
            version="1",
            declarations={"embedding": {"model": "m", "exclude_roles": []}},
        ),
        lambda document: (0.0,),
    )


def a_turn_that_calls(name: str, arguments: Any, said: str | None = None) -> Part:
    """One target turn, rendered by the modality that will actually render it.

    Crossing the seam is the point. `text2text` writes a turn's calls into a part's text and
    `restated_answer` reads them back out, and until a review found it the two agreed only by a
    convention spelled in one axis and assumed in the other. Building this fixture here rather than
    hand-writing `json.dumps` is what makes a change at either end fail this file. The *arguments*
    are a JSON string on purpose: that is the form a source item carries them in.
    """
    turn: dict[str, Any] = {
        "role": "assistant",
        "tool_calls": [
            {"function": {"name": name, "arguments": json.dumps(arguments)}}
        ],
    }
    if said is not None:
        turn["content"] = said
    return a_text2text().content_parts({"messages": [turn]})[0]


def a_record(
    *,
    tools: Any = CATALOG,
    label: StoredAnswer = (SENT,),
    content: Sequence[Part] | None = None,
    **written: Any,
) -> Record:
    """One record already loaded, with whatever a later phase has written on it."""
    carried = content if content is not None else parts()
    return Record(
        record_id=record_id_for(carried),
        source_id="s4471",
        branch=Branch(modality="text2text", profile="tool_decision"),
        provenance=Provenance(**PROVENANCE),
        content=tuple(carried),
        label=label,
        meta={"tools": tools, "label": list(label), "llm_model": "a-model"},
        **written,
    )


def an_item(**overrides: Any) -> dict[str, Any]:
    """One source item in the declared shape, as the source wrote it."""
    return {
        "id": "s4471",
        "messages": [{"role": role, "content": text} for role, text in TURNS],
        "tools": CATALOG,
        "meta": {"label": [SENT], "human_checked": True, "llm_model": "a-model"},
        **overrides,
    }


def a_provenance() -> Provenance:
    """What `load_data` hands over: the file, the offset, the clock, the pair and the run."""
    return Provenance(**PROVENANCE)


def checks_that_fire(record: Record, profile: ToolDecision | None = None) -> set[str]:
    """Which of the five defects this record's label carries."""
    return {
        check.name
        for check in (profile or a_profile()).label_checks()
        if check.defect_in(record)
    }


# --- δ, the operation every number in the pipeline is written on ---


def test_the_worked_ordering_holds_to_the_bit() -> None:
    """The spec's own three numbers, asserted as the ordering rather than as three facts."""
    profile = a_profile()
    differing = {
        "name": "SendStatement",
        "arguments": {"ma_khach": "480215", "ky": "thang_truoc"},
    }

    same = profile.answer_distance((SENT,), (SENT,))
    one_argument = profile.answer_distance((SENT,), (differing,))
    other_tool = profile.answer_distance((LOOKED_UP,), (TICKETED,))

    assert same == 0.0
    assert one_argument == 0.5
    assert other_tool == 1.0
    assert same < one_argument < other_tool


def test_two_empty_answers_agree_perfectly() -> None:
    """`δ(∅, ∅) = 0` by definition, and load-bearing: a NaN here takes every α with it."""
    assert a_profile().answer_distance((), ()) == 0.0


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (("LookupBalance",), ("LookupBalance",)),
        (("LookupBalance", "SendStatement"), ("LookupBalance",)),
        (("LookupBalance",), ("SendStatement",)),
        (("LookupBalance", "SendStatement"), ("SendStatement", "OpenTicket")),
        ((), ("SendStatement",)),
    ],
    ids=["identical", "one-of-two", "disjoint", "one-shared", "empty-against-one"],
)
def test_argument_less_calls_reduce_to_plain_jaccard(
    left: tuple[str, ...], right: tuple[str, ...]
) -> None:
    """The reduction is exact, not approximate -- and a bare name reads as an argument-less call."""
    names, other = set(left), set(right)
    expected = (
        0.0 if not names | other else 1.0 - len(names & other) / len(names | other)
    )

    assert a_profile().answer_distance(left, right) == expected


def test_argument_agreement_is_over_the_union_of_keys() -> None:
    """`len(shared) / len(left)` would call a one-argument call a perfect match for five."""
    thin = {"name": "SendStatement", "arguments": {"ma_khach": "480215"}}

    assert a_profile().answer_distance((thin,), (SENT,)) == 0.5


# --- the answer space, materialised and never stored ---


def a_validator(
    profile: ToolDecision, record: Record
) -> jsonschema.Draft202012Validator:
    """This record's own answer schema, as something that can say yes or no."""
    return jsonschema.Draft202012Validator(profile.answer_schema(record))


def test_a_call_from_the_catalog_validates() -> None:
    """The green case, so the rejections below are a rule and not a refusal."""
    validator = a_validator(a_profile(), a_record())

    assert validator.is_valid([LOOKED_UP])
    assert validator.is_valid([SENT])
    assert validator.is_valid([])


def test_one_tool_carrying_another_tool_s_argument_is_rejected() -> None:
    """T13's acceptance criterion: two valid halves and one invalid call.

    `OpenTicket` declares no `required`, so the only thing wrong with this is the argument -- which
    is what an `enum` of names beside a free-form object could not have said.
    """
    validator = a_validator(a_profile(), a_record())

    assert validator.is_valid([{"name": "OpenTicket", "arguments": {"noi_dung": "x"}}])
    assert not validator.is_valid(
        [{"name": "OpenTicket", "arguments": {"ma_khach": "480215"}}]
    )


def test_an_argument_outside_its_enum_is_rejected() -> None:
    """What a second, hand-written reading of the catalog would have let through."""
    wrong = {
        "name": "SendStatement",
        "arguments": {"ma_khach": "480215", "ky": "thang_sau"},
    }

    assert not a_validator(a_profile(), a_record()).is_valid([wrong])


def test_a_missing_required_argument_is_rejected() -> None:
    """`required` is the tool's own declaration, and the schema carries it verbatim."""
    partial = {"name": "SendStatement", "arguments": {"ma_khach": "480215"}}

    assert not a_validator(a_profile(), a_record()).is_valid([partial])


def test_more_calls_than_the_ceiling_are_rejected() -> None:
    """`max_calls` is the manifest's, and `maxItems` is the same number."""
    assert not a_validator(a_profile(), a_record()).is_valid(
        [LOOKED_UP, SENT, TICKETED]
    )


def test_an_empty_catalog_permits_only_the_empty_answer() -> None:
    """There was nothing to choose from, so `maxItems: 0` is the whole space."""
    validator = a_validator(a_profile(), a_record(tools=[]))

    assert validator.is_valid([])
    assert not validator.is_valid([LOOKED_UP])


def test_the_space_is_materialised_and_never_written_down() -> None:
    """I10: the catalog is the source's own key, kept verbatim; the space is derived on request."""
    profile = a_profile()
    record = profile.build_record(an_item(), parts(), a_provenance())

    assert "answer_space" not in record.model_dump()
    assert record.meta["tools"] == CATALOG
    assert profile.answer_schema(record) == profile.answer_schema(record)


# --- what the space permits, which is more than the schema can say ---


def test_a_permitted_answer_is_one_the_materialised_schema_accepts() -> None:
    """The ordinary case: the member and the schema agree, and the schema is the whole of it."""
    profile, record = a_profile(), a_record()

    assert profile.answer_is_permitted((SENT,), record)
    assert profile.answer_is_permitted((), record)
    assert not profile.answer_is_permitted(("SendStatement",), record)


def test_two_calls_on_one_tool_are_refused_where_the_schema_cannot_refuse_them() -> (
    None
):
    """`uniqueItems` compares whole calls, so two calls on one tool with different arguments are
    unique to the schema and still name one tool twice. `jury` counts an invalid vote on this
    member for that reason: `vote_consensus` refuses the same answer, and a stage reading the
    schema alone would call a vote usable that no consensus could be built from."""
    profile, record = a_profile(), a_record()
    twice = (
        SENT,
        {
            "name": "SendStatement",
            "arguments": {"ma_khach": "480216", "ky": "thang_truoc"},
        },
    )

    assert a_validator(profile, record).is_valid(list(twice))
    assert not profile.answer_is_permitted(twice, record)


def test_an_answer_over_the_declared_ceiling_is_refused() -> None:
    """The ceiling is the manifest's, which is why the member does not take one: a caller
    counting a jury's invalid votes has no business knowing what this profile permits."""
    profile = a_profile(max_calls=1)

    assert not profile.answer_is_permitted((SENT, LOOKED_UP), a_record())


# --- consensus, per name and then per argument ---


def test_a_majority_voting_the_empty_answer_is_the_empty_answer() -> None:
    """Step 1, which is the whole of what keeps `()` and `None` apart."""
    record = a_record()

    agreed = a_profile().vote_consensus([(), (), (LOOKED_UP,)], record)

    assert agreed == ()


def test_no_votes_at_all_is_not_the_empty_answer() -> None:
    """*Agreed to call nothing* and *nothing defensible* are two values, not one read twice."""
    assert a_profile().vote_consensus([], a_record()) is None


def test_a_call_a_majority_named_survives_with_the_arguments_they_agreed_on() -> None:
    """Steps 2 and 3, and the consensus is asserted against the record's own schema directly."""
    profile, record = a_profile(), a_record()
    votes: list[StoredAnswer] = [(SENT,), (SENT,), (TICKETED,)]

    agreed = profile.vote_consensus(votes, record)

    assert agreed == (SENT,)
    assert a_validator(profile, record).is_valid(list(agreed or ()))


def test_a_call_missing_a_required_argument_is_dropped_not_completed() -> None:
    """Step 4. Half-building one puts a value no juror proposed into a ranking signal."""
    profile, record = a_profile(), a_record()
    votes: list[StoredAnswer] = [
        (SENT,),
        ({"name": "SendStatement", "arguments": {"ma_khach": "480215"}},),
        ({"name": "SendStatement", "arguments": {"ky": "thang_truoc"}},),
    ]

    agreed = profile.vote_consensus(votes, record)

    assert agreed is None


def test_an_argument_only_a_minority_named_is_absent() -> None:
    """A key with no majority is absent -- and `noi_dung` is not `required`, so the call stays."""
    profile, record = a_profile(), a_record()
    bare = {"name": "OpenTicket", "arguments": {}}
    votes: list[StoredAnswer] = [(TICKETED,), (bare,), (bare,)]

    assert profile.vote_consensus(votes, record) == (bare,)


def test_a_juror_who_did_not_name_the_tool_has_no_opinion_about_its_arguments() -> None:
    """Step 3's denominator is the votes *naming that tool*, never all of them."""
    profile, record = a_profile(), a_record()
    votes: list[StoredAnswer] = [(TICKETED,), (TICKETED,), (LOOKED_UP,)]

    assert profile.vote_consensus(votes, record) == (TICKETED,)


def test_a_tool_no_catalog_offered_is_dropped_for_step_4_s_own_reason() -> None:
    """It would fail this record's `answer_schema`, which is what step 4 refuses to produce."""
    hallucinated = {"name": "DeleteAccount", "arguments": {}}
    votes: list[StoredAnswer] = [(hallucinated,), (hallucinated,), (hallucinated,)]

    assert a_profile().vote_consensus(votes, a_record()) is None


# --- the five checks that need no opinion ---


def test_a_clean_record_fires_no_check() -> None:
    """Every check is named for a defect, so a good record has to be silent on all five."""
    assert checks_that_fire(a_record()) == set()


def test_the_five_are_the_names_params_declares() -> None:
    """Requirement 22: each carries a declared expected count under these exact names."""
    named = [check.name for check in a_profile().label_checks()]

    assert named == [
        "label_assistant_mismatch",
        "label_not_in_catalog",
        "empty_catalog",
        "label_cardinality_anomaly",
        "label_names_one_tool_twice",
    ]


def test_a_label_naming_a_tool_the_record_never_offered_fires() -> None:
    """Unlearnable, and it teaches hallucination. Never truncated to the catalog."""
    stray = {"name": "DeleteAccount", "arguments": {}}

    assert "label_not_in_catalog" in checks_that_fire(a_record(label=(stray,)))


def test_a_record_with_nothing_to_choose_from_fires() -> None:
    """A quarantine for triage, not a verdict -- and Requirement 13 never parses a catalog out."""
    fired = checks_that_fire(a_record(tools=[], label=()))

    assert "empty_catalog" in fired


def test_a_label_over_the_ceiling_fires() -> None:
    """`max_calls: 2`, so three calls is the anomaly the manifest declares."""
    over = a_record(label=(LOOKED_UP, SENT, TICKETED))

    assert "label_cardinality_anomaly" in checks_that_fire(over)


def test_a_label_naming_one_tool_twice_fires() -> None:
    """A target of `["X", "X"]` trains a model to call X twice and makes the answer a multiset."""
    twice = a_record(label=(TICKETED, TICKETED))

    assert "label_names_one_tool_twice" in checks_that_fire(twice)


def test_the_separator_between_what_a_turn_said_and_called_is_the_records() -> None:
    """The fourth name both axes borrow, asserted once so neither copy can drift.

    This is the assumption that made `label_assistant_mismatch` silent on every turn that both
    speaks and acts: the modality joined the two halves and the profile parsed the whole string.
    """
    part = a_turn_that_calls(
        "LookupBalance", {"ma_khach": "480215"}, said="Mình tra cứu ngay nhé."
    )

    spoken, stated = (part.text or "").split(SPOKEN_AND_STATED)

    assert spoken == "Mình tra cứu ngay nhé."
    assert stated == stated_calls(
        [{"function": {"name": "LookupBalance", "arguments": '{"ma_khach": "480215"}'}}]
    )
    assert json.loads(stated) == [LOOKED_UP]


def test_a_restating_turn_that_disagrees_with_the_label_fires() -> None:
    """The final turn states the answer, and the two disagree."""
    restated = parts(TURNS) + (
        a_turn_that_calls("LookupBalance", {"ma_khach": "480215"}),
    )

    assert "label_assistant_mismatch" in checks_that_fire(a_record(content=restated))


def test_a_turn_that_speaks_and_calls_is_still_a_restatement() -> None:
    """The shape the check went silent on: prose joined to the calls in one part's text."""
    both = parts(TURNS) + (
        a_turn_that_calls(
            "LookupBalance", {"ma_khach": "480215"}, said="Mình tra cứu ngay nhé."
        ),
    )

    assert "label_assistant_mismatch" in checks_that_fire(a_record(content=both))


def test_a_restating_turn_that_agrees_is_quiet() -> None:
    """The check is about disagreement, so the agreeing case has to stay silent."""
    agreed = {"ma_khach": "480215", "ky": "thang_nay"}
    restated = parts(TURNS) + (a_turn_that_calls("SendStatement", agreed),)
    speaks_too = parts(TURNS) + (
        a_turn_that_calls("SendStatement", agreed, said="Đã gửi sao kê cho bạn."),
    )

    assert "label_assistant_mismatch" not in checks_that_fire(
        a_record(content=restated)
    )
    assert "label_assistant_mismatch" not in checks_that_fire(
        a_record(content=speaks_too)
    )


def test_a_conversation_that_ends_with_the_customer_restates_nothing() -> None:
    """The declared shape's ordinary case: the label answers the final turn, nothing restates it.

    This is where the previous tree's version of the check would have quarantined every record --
    it returned True when nothing restated the label, which was right for a corpus whose assistant
    turn *was* the answer and is wrong for the one Requirement 13 declares.
    """
    assert "label_assistant_mismatch" not in checks_that_fire(a_record())


def test_prose_in_the_final_turn_restates_nothing() -> None:
    """A turn that says what was done in words is not a second statement of the answer."""
    spoken = parts((*TURNS, ("assistant", "Mình đã gửi sao kê cho bạn rồi nhé.")))

    assert "label_assistant_mismatch" not in checks_that_fire(a_record(content=spoken))


def test_an_earlier_tool_call_turn_is_history_and_not_a_restatement() -> None:
    """A tool called before the customer supplied what was missing is context (Requirement 13)."""
    history = (
        *parts((("user", "Cho mình xem số dư."),)),
        a_turn_that_calls("LookupBalance", {"ma_khach": "480215"}),
        *parts((("user", "Gửi giúp mình sao kê tháng này."),)),
    )

    assert "label_assistant_mismatch" not in checks_that_fire(a_record(content=history))


# --- one item into one record ---


def test_the_record_carries_what_the_item_and_load_data_gave_it() -> None:
    """`build_record` is the only place a source shape is read."""
    record = a_profile().build_record(an_item(), parts(), a_provenance())

    assert record.record_id == record_id_for(parts())
    assert record.source_id == "s4471"
    assert record.branch == Branch(modality="text2text", profile="tool_decision")
    assert record.provenance.offset == 41
    assert record.label == (SENT,)
    assert record.content_version == 1


def test_meta_keeps_every_key_the_source_presented() -> None:
    """Requirement 9, verbatim -- including the keys no code recognises."""
    record = a_profile().build_record(
        an_item(unrecognised={"x": 1}), parts(), a_provenance()
    )

    assert record.meta["unrecognised"] == {"x": 1}
    assert record.meta["human_checked"] is True
    assert record.meta["tools"] == CATALOG
    assert record.meta["id"] == "s4471"
    assert "messages" not in record.meta


def test_the_answer_is_read_from_the_key_the_manifest_declares() -> None:
    """Requirement 14: a source calling it `gold` needs a manifest line and no code."""
    renamed = a_profile(label={"at": "gold"})
    item = an_item(meta={"gold": [TICKETED]})

    assert renamed.build_record(item, parts(), a_provenance()).label == (TICKETED,)


def test_an_item_with_no_answer_under_the_declared_key_names_both() -> None:
    """The error names the manifest and what the item does carry, which is what a person needs."""
    item = an_item(meta={"target": [SENT]})

    with pytest.raises(ConfigError, match="meta.label"):
        a_profile().build_record(item, parts(), a_provenance())


def test_a_label_that_is_one_string_is_not_thirteen_calls() -> None:
    """`tuple("SendStatement")` is a tuple of characters, which is the shape of a real defect."""
    item = an_item(meta={"label": "SendStatement"})

    record = a_profile().build_record(item, parts(), a_provenance())

    assert record.label == ()
    assert "empty_catalog" not in checks_that_fire(record)


def test_a_catalog_that_is_one_string_offers_nothing() -> None:
    """The same guard where the source's own `tools` key arrives malformed."""
    assert checks_that_fire(a_record(tools="LookupBalance", label=())) == {
        "empty_catalog"
    }


def test_an_item_with_no_id_traces_back_through_its_offset() -> None:
    """`source_id` is for tracing back to the item, so an empty one would trace nowhere."""
    item = an_item()
    del item["id"]

    assert a_profile().build_record(item, parts(), a_provenance()).source_id == "41"


# --- the label, redacted with the content ---


def test_a_value_in_an_argument_is_replaced_under_its_placeholder() -> None:
    """Requirement 17: the stage rewrites the content and this rewrites the label, one map."""
    redacted = a_profile().redact_label((SENT,), {"480215": "<CUSTOMER_ID_1>"})

    assert redacted == (
        {
            "name": "SendStatement",
            "arguments": {"ma_khach": "<CUSTOMER_ID_1>", "ky": "thang_nay"},
        },
    )


def test_a_tool_name_is_never_rewritten() -> None:
    """A name is the catalog's, not the customer's: rewriting one fires `label_not_in_catalog`."""
    redacted = a_profile().redact_label((SENT,), {"Send": "<X_1>", "480215": "<X_2>"})

    assert redacted[0]["name"] == "SendStatement"  # type: ignore[call-overload]


def test_a_value_nested_inside_an_argument_is_reached() -> None:
    """An argument may itself be an object or an array, which is why the walk recurses."""
    nested = ({"name": "OpenTicket", "arguments": {"khach": {"ma": ["480215"]}}},)

    redacted = a_profile().redact_label(nested, {"480215": "<CUSTOMER_ID_1>"})

    assert redacted == (
        {"name": "OpenTicket", "arguments": {"khach": {"ma": ["<CUSTOMER_ID_1>"]}}},
    )


def test_a_bare_name_answer_comes_back_as_it_went_in() -> None:
    """A names-only source's label carries no values, so there is nothing in it to redact."""
    assert a_profile().redact_label(("SendStatement",), {"Send": "<X_1>"}) == (
        "SendStatement",
    )


def test_one_value_inside_another_is_replaced_longest_first() -> None:
    """The order both ends share, through `record.redacted_text`.

    Shortest-first would write `48<PHONE_1>` here and the stage would write `<CUSTOMER_ID_1>` in the
    content, which is the mismatch Requirement 17 exists to prevent -- manufactured by the fix.
    """
    both = {"480215": "<CUSTOMER_ID_1>", "0215": "<PHONE_1>"}

    redacted = a_profile().redact_label((SENT,), both)

    assert redacted[0]["arguments"]["ma_khach"] == "<CUSTOMER_ID_1>"  # type: ignore[call-overload,index]


def test_a_label_with_nothing_to_replace_is_unchanged() -> None:
    """The ordinary case, and the one that must not invent a key: no `arguments`, none added."""
    assert a_profile().redact_label((SENT,), {}) == (SENT,)


# --- what a person is asked, and what comes back ---


def test_the_question_is_the_template_the_edge_read() -> None:
    """Prompt text in code is a prompt change no run manifest records (Requirement 51)."""
    assert a_profile().question_text(a_record()) == QUESTION


def test_a_template_naming_a_slot_this_profile_cannot_fill_is_refused() -> None:
    """One question is asked per record, so a raw `{{focus}}` reaching an annotator is the bug."""
    with pytest.raises(ConfigError, match="slot"):
        a_profile(question="Tập trung vào: {{focus}}")


def an_annotation(**controls: Any) -> list[dict[str, Any]]:
    """One `annotation.result` list: one object per control that was answered."""
    shapes = {
        "verdict": ("choices", {"choices": controls.get("verdict", ["incorrect"])}),
        "corrected_names": (
            "choices",
            {"choices": controls.get("corrected_names", ["SendStatement"])},
        ),
        "corrected_arguments": (
            "textarea",
            {
                "text": controls.get(
                    "corrected_arguments",
                    ['{"SendStatement": {"ma_khach": "480215", "ky": "thang_nay"}}'],
                )
            },
        ),
    }
    return [
        {"from_name": name, "to_name": "conversation", "type": kind, "value": value}
        for name, (kind, value) in shapes.items()
        if name not in controls or controls[name] is not None
    ]


def test_a_corrected_answer_comes_back_as_the_answer_that_went_in() -> None:
    """I18's round trip: the capture half's inverse, and it validates against this record's space."""
    profile, record = a_profile(), a_record()

    assert profile.answer_from_response(an_annotation(), record) == (SENT,)


def test_a_textarea_string_rather_than_a_list_fails() -> None:
    """I18's other half. `maxSubmissions` permits more than one, so the value is always a list."""
    profile, record = a_profile(), a_record()
    result = an_annotation()
    result[2]["value"] = {"text": '{"SendStatement": {}}'}

    assert profile.answer_from_response(result, record) is None


def test_arguments_that_are_not_json_are_never_coerced() -> None:
    """Requirement 49: a human's malformed answer is evidence about the question, not noise."""
    malformed = an_annotation(corrected_arguments=['{"SendStatement": '])

    assert a_profile().answer_from_response(malformed, a_record()) is None


def test_a_correction_that_does_not_validate_is_none() -> None:
    """A name outside the catalog, and an argument the tool never declared."""
    profile, record = a_profile(), a_record()
    stray = an_annotation(corrected_names=["DeleteAccount"], corrected_arguments=["{}"])
    mistyped = an_annotation(
        corrected_arguments=[
            '{"SendStatement": {"ma_khach": "480215", "ky": "thang_sau"}}'
        ]
    )

    assert profile.answer_from_response(stray, record) is None
    assert profile.answer_from_response(mistyped, record) is None


def test_a_verdict_that_is_not_incorrect_carries_no_correction() -> None:
    """Called only where the verdict is `incorrect`; anything else has nothing to invert."""
    profile, record = a_profile(), a_record()

    assert (
        profile.answer_from_response(an_annotation(verdict=["correct"]), record) is None
    )


def test_a_control_the_annotator_never_touched_is_simply_absent() -> None:
    """Absent from the list rather than present and empty, which is why this reads by name."""
    profile, record = a_profile(), a_record()

    assert (
        profile.answer_from_response(an_annotation(corrected_names=None), record)
        is None
    )


def test_the_capture_half_declares_the_verdicts_and_emits_no_display_tag() -> None:
    """Requirement 31: neither half of the config may emit the other's."""
    control = a_profile().answer_config()

    assert control.verdicts == ("correct", "incorrect", "unsure")
    assert control.max_calls == 2
    assert control.control == "names_and_json_arguments"
    assert "<Paragraphs" not in control.tags
    assert '<Choices name="verdict"' in control.tags
    assert 'value="$tool_names"' in control.tags


# --- the four members a later phase reads ---


def test_two_records_offered_the_same_catalog_share_a_scenario() -> None:
    """What must not straddle a split. Never the offset, which is unique per record."""
    profile = a_profile()
    other = a_record(content=parts((("user", "Một hội thoại khác."),)))

    assert profile.scenario_hash(a_record()) == profile.scenario_hash(other)
    assert profile.scenario_hash(a_record(tools=CATALOG[:2])) != profile.scenario_hash(
        a_record()
    )


def test_a_reordered_catalog_is_a_different_scenario() -> None:
    """The catalog is presented in order, and two orderings are two prompts."""
    profile = a_profile()
    swapped = a_record(tools=[CATALOG[1], CATALOG[0], CATALOG[2]])

    assert profile.scenario_hash(swapped) != profile.scenario_hash(a_record())


def test_the_jury_s_slots_are_the_record_and_nothing_from_a_model() -> None:
    """The template is policy's; these are the values (Requirement 51)."""
    slots = a_profile().jury_slots(a_record())

    assert set(slots) == {"conversation", "catalog", "label"}
    assert "Gửi giúp mình sao kê tháng này qua email." in slots["conversation"]
    assert "LookupBalance(ma_khach)" in slots["catalog"]
    assert json.loads(slots["label"]) == [SENT]


def test_a_training_example_is_the_shape_the_record_arrived_in() -> None:
    """So an export is re-readable by the same loader, with the answer back where it was."""
    profile = a_profile()
    record = profile.build_record(an_item(), parts(), a_provenance())

    example = profile.training_example(record)

    assert set(example) == {"id", "messages", "tools", "meta"}
    assert example["messages"][1] == {"role": "user", "content": TURNS[1][1]}
    assert example["tools"] == CATALOG
    assert example["meta"]["label"] == [SENT]
    assert example["meta"]["human_checked"] is True


def test_a_training_example_ships_the_curated_answer_where_review_decided_one() -> None:
    """`curate` writes what ships, so this is what a trainer has to be handed."""
    corrected = a_record(
        human_review=HumanReview(
            curate=FinalLabel(
                status="corrected",
                label=(TICKETED,),
                validators=("an-annotator",),
                decided_at=datetime(2026, 8, 24, tzinfo=UTC),
            )
        )
    )

    assert a_profile().training_example(corrected)["meta"]["label"] == [TICKETED]


def test_an_unresolved_review_ships_the_answer_the_record_arrived_with() -> None:
    """Unresolved is not a decision, so there is nothing to swap in."""
    open_still = a_record(
        human_review=HumanReview(
            curate=FinalLabel(
                status="unresolved",
                label=(),
                decided_at=datetime(2026, 8, 24, tzinfo=UTC),
            )
        )
    )

    assert a_profile().training_example(open_still)["meta"]["label"] == [SENT]


# --- identity, and every declaration this profile refuses to guess ---


def test_identity_and_the_pair_come_from_the_manifest() -> None:
    """Requirement 40, and the `modality:` a run naming another hard-stops against."""
    profile = a_profile()

    assert (profile.name, profile.version, profile.modality) == (
        "tool_decision",
        "1",
        "text2text",
    )


@pytest.mark.parametrize(
    "declared",
    [
        {"shape": "legacy_system_prompt"},
        {"answer_control": "free_text"},
        {"modality": None},
    ],
    ids=["retired-shape", "unknown-control", "no-pair"],
)
def test_a_declaration_that_is_not_one_of_the_declared_values_is_refused(
    declared: dict[str, Any],
) -> None:
    """Each of these decides how a file is read or what an agreement figure means."""
    with pytest.raises(ConfigError):
        a_profile(**declared)


@pytest.mark.parametrize(
    "missing",
    ["max_calls", "shape", "answer_control", "label", "roles"],
    ids=["max_calls", "shape", "answer_control", "label", "roles"],
)
def test_a_missing_declaration_names_the_file_and_the_path(missing: str) -> None:
    """A profile guesses none of these, and the error says which line to go and write."""
    declarations = {key: value for key, value in DECLARED.items() if key != missing}
    incomplete = Manifest(
        name="tool_decision",
        version="1",
        modality="text2text",
        declarations=declarations,
    )

    with pytest.raises(ConfigError, match=r"config/profiles/tool_decision.yaml"):
        ToolDecision(incomplete, QUESTION)


@pytest.mark.parametrize(
    "max_calls",
    ["two", [2], None, 2.7, True, 0, -1],
    ids=["a-word", "a-list", "null", "a-fraction", "a-flag", "zero", "negative"],
)
def test_a_ceiling_that_is_not_a_whole_number_of_calls_is_refused(
    max_calls: Any,
) -> None:
    """Two of these used to pass silently, which is the reason this test exists.

    `int()` truncated `2.7` to 2 and read `true` as 1 -- so a mistyped ceiling became `maxItems`
    *and* `label_cardinality_anomaly`'s boundary with nothing to read in a diff. `True` is an `int`
    in Python, which is exactly how the flag case got through.
    """
    with pytest.raises(ConfigError, match="max_calls"):
        a_profile(max_calls=max_calls)


@pytest.mark.parametrize(
    "at", [["label"], "", None, 7], ids=["a-list", "empty", "null", "a-number"]
)
def test_a_label_key_that_is_not_a_key_name_is_refused(at: Any) -> None:
    """`str(["label"])` is a key no item carries, and the run then failed once per record."""
    with pytest.raises(ConfigError, match="label.at"):
        a_profile(label={"at": at})


def test_a_role_declared_as_a_list_reads_as_its_first_entry() -> None:
    """`conversation: [user]` is a list in the manifest, so `target:` may be one too."""
    listed = a_profile(roles={"target": ["assistant"]})
    restated = parts(TURNS) + (
        a_turn_that_calls("LookupBalance", {"ma_khach": "480215"}),
    )

    assert "label_assistant_mismatch" in checks_that_fire(
        a_record(content=restated), listed
    )


def test_it_answers_every_member_its_protocol_declares() -> None:
    """The runtime half of what `utils.py`'s `TYPE_CHECKING` block proves statically.

    An equality, not a containment: the sixteen are *closed*, and the containment version of this
    test is what let `final_label` ship as an undeclared extra. I23 checks the same closure off the
    tree; this checks it off a live instance. Fifteen since T16, which brought `redact_label` the
    caller T13 refused to add it without; sixteen since T19, which brought `jury` -- a stage that
    cannot count an invalid vote without asking what a permitted answer is.
    """
    declared = {name for name in dir(Profile) if not name.startswith("_")} | set(
        Profile.__annotations__
    )

    assert len(declared) == 16
    assert {name for name in dir(a_profile()) if not name.startswith("_")} == declared
