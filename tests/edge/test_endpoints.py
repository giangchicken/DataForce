"""Each of the router's routes through `TestClient`, driven by nothing but its own arguments.

Every test body holds one route, and no fixture carries an answer from one route into another:
that is the flow's first rule, and a suite is the easiest place to break it, because a fixture
that posts the scan and feeds the answer to `/ai-review` passes while making the parts undrivable
apart. The one body that arrives from another route is the `PersonalDataDetected` the replace
route takes back, and that is one part's second call rather than a payload threaded between two.
`GET /health` is the app's own and not this task's, so it is not among them. `GET /ui/` is the
app's own too -- a mount rather than a route -- and what is asserted about it is only that it is
served, because no test drives either page.

Which models a request may tick is a directory, so the stub is a directory: `DATAFORCE_MODEL_DIR`
points at files this test wrote, set before the app is created because `register_resolver()` reads
it at startup. Nothing here reaches a provider -- `complete` is answered per module that calls it,
and the tests about a refusal install one that fails the test if it is reached at all, which is
what *before any model is called* means.
"""

import json
import uuid
from collections.abc import Iterator, Mapping
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from agent_toolkit.llm import set_config_resolver
from fastapi.testclient import TestClient

from dataforce.edge.database import DEFAULT_STORE_FILE, db
from dataforce.edge.main import UI, create_app
from dataforce.edge.routers.text2text import tool_decision as route
from dataforce.modalities.text2text.data_quality import (
    PersonalDataDetected,
    personal_data_checking,
)
from dataforce.profile.tool_decision import ai_review, data_quality
from dataforce.profile.tool_decision.sample_building import (
    create_tables,
)
from dataforce.profile.tool_decision.schema import (
    ToolDecisionRecord,
    ToolDecisionSample,
)
from dataforce.profile.tool_decision.utils import build_review_text
from dataforce.tables import Base

BASE = "/text2text/tool-decision"

JUROR = "a-juror"
SECOND = "another-juror"
VERIFIER = "a-verifier"
# Served -- the directory holds its file -- and no endpoint in it, which is the other refusal.
NO_ENDPOINT = "no-endpoint"
UNSERVED = "a-model-nobody-attached"

SERVED: Mapping[str, Mapping[str, Any]] = {
    JUROR: {"model": JUROR, "base_url": "http://a-juror.invalid/v1"},
    SECOND: {"model": SECOND, "base_url": "http://another-juror.invalid/v1"},
    VERIFIER: {"model": VERIFIER, "base_url": "http://a-verifier.invalid/v1"},
    NO_ENDPOINT: {"model": NO_ENDPOINT, "temperature": 0.0},
}

PHONE = "0912345678"
# A corpus key this service does not read, posted with every sample: what is handed on is what
# arrived, so a key nothing here knows about is not dropped on the way through.
SOURCE = "a-corpus"
SAMPLE: Mapping[str, Any] = {
    "id": "one-ticket",
    "messages": [
        {"role": "user", "content": f"Chào em, số anh là {PHONE}, mở phiếu với."},
        {"role": "assistant", "content": "Dạ em mở phiếu hỗ trợ cho mình ngay ạ."},
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "OpenTicket",
                "description": "Mở phiếu hỗ trợ cho khách hàng.",
                "parameters": {
                    "type": "object",
                    "required": ["ma_khach"],
                    "properties": {"ma_khach": {"type": "string"}},
                },
            },
        }
    ],
    "label": [{"name": "OpenTicket", "arguments": {"ma_khach": "KH-1"}}],
    "source": SOURCE,
}

OPEN_TICKET = [{"name": "OpenTicket", "arguments": {"ma_khach": "KH-1"}}]

# The names `edge/static/index.html` writes down. The drawing may: every answer in it is its own,
# and a picture of a tick list needs names to draw. The UI may not, and lifting that line out of
# the drawing is exactly how it would come to.
DRAWN_MODELS = ("DeepSeek-V4-Flash", "bge-m3", "gemma-4-31B-it", "sft-tool-decision")

# The one body that arrives from another route: the detect answer, with the spans as a reviewer
# left them. Written out here rather than fetched, so this test drives one route.
REVIEW_TEXT = f"user: số anh là {PHONE}."
DETECTED: Mapping[str, Any] = {
    "review_text": REVIEW_TEXT,
    "claims": [["PHONE", PHONE]],
    "spans": [
        {
            "id": 1,
            "start": REVIEW_TEXT.index(PHONE),
            "end": REVIEW_TEXT.index(PHONE) + len(PHONE),
            "personal_data_class": "PHONE",
            "placeholder": "<PHONE_1>",
            "reason": "khách tự cho số của mình",
        }
    ],
}

# Where each `complete` this service calls is bound. One per step that asks a model, because that
# is the seam a stub replaces -- there is no single import to patch.
ASKING: tuple[ModuleType, ...] = (ai_review, data_quality, personal_data_checking)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The app over a model directory this test wrote. The directory *is* the list.

    The environment is set before `create_app()`, because `register_resolver()` reads it once at
    startup -- so a resolver pointed at the real `config/model/` is what a test that sets it later
    would be asking. Reset afterwards, so nothing outside this module inherits a resolver reading
    a directory that has been deleted.
    """
    directory = tmp_path / "model"
    directory.mkdir()
    for name, declared in SERVED.items():
        (directory / f"{name}.json").write_text(json.dumps(declared), encoding="utf-8")
    monkeypatch.setenv("DATAFORCE_MODEL_DIR", str(directory))
    yield TestClient(create_app())
    set_config_resolver(None)


def install_model_answers(monkeypatch: pytest.MonkeyPatch, **answers: Any) -> list[str]:
    """Install a `complete` in every module that calls one, answering per model asked.

    An entry may be the answer object or the text of one. The list that comes back holds the
    models asked, in order, so a test can say which steps ran and how often.
    """
    asked: list[str] = []

    async def answered(prompt: str, **kwargs: Any) -> str:
        asked.append(kwargs["model"])
        resp = answers[kwargs["model"]]
        return resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)

    for module in ASKING:
        monkeypatch.setattr(module, "complete", answered)
    return asked


def forbid_model_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a `complete` that fails the test. What *before any model is called* asserts."""

    async def never(prompt: str, **kwargs: Any) -> str:
        raise AssertionError(f"a model was called: {kwargs['model']}")

    for module in ASKING:
        monkeypatch.setattr(module, "complete", never)


# ----------------------------------------------------------------- the page, and the list


def test_the_page_is_served_by_its_own_route(client: TestClient) -> None:
    """The file, as a file: no test drives the page, and a browser is the check."""
    resp = client.get(f"{BASE}/")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert resp.text == route.PAGE.read_text(encoding="utf-8")


def test_the_labelling_ui_is_served_at_its_own_mount(client: TestClient) -> None:
    """The file, as a file: no test drives the UI, and a browser is the check."""
    resp = client.get("/ui/")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert resp.text == (UI / "index.html").read_text(encoding="utf-8")


def test_the_page_is_loaded_as_a_module_and_the_mount_serves_one(
    client: TestClient,
) -> None:
    """`<script type="module">` is what gives the page files to be split into.

    A browser refuses to run a module served as anything but JavaScript -- and refuses it
    *silently*, with no request failing and nothing in the page to say so. Reading the tag alone
    would pass against a mount answering `text/plain`, so the media type is read here too.

    Both spellings, because the answer is not this repository's: `StaticFiles` asks `mimetypes`,
    which reads the machine's own table, and `.js` is `text/javascript` on one distribution and
    `application/javascript` on the next. A browser runs a module served as either, so a check
    that named one would go red on a deployment this sentence blesses.
    """
    assert '<script type="module" src="app.js"></script>' in (
        UI / "index.html"
    ).read_text(encoding="utf-8")

    resp = client.get("/ui/app.js")

    assert resp.status_code == 200
    assert resp.headers["content-type"].split(";")[0].strip() in {
        "text/javascript",
        "application/javascript",
    }


def test_the_ui_ticks_from_the_endpoint_rather_than_naming_a_model_itself() -> None:
    """The directory is the list, so the UI asks for it.

    Read off the files rather than out of a browser, because what it pins is a *second
    declaration* of what this deployment serves -- and the one that would appear is the drawing's
    `SERVED`, copied across. The drawing is read too, so the day those names change there the
    constant here fails rather than quietly guarding nothing.
    """
    drawing = route.PAGE.read_text(encoding="utf-8")
    written = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(UI.iterdir())
        if path.is_file()
    }

    assert "/models" in written["app.js"]
    for name in DRAWN_MODELS:
        assert name in drawing
        for said in written.values():
            assert name not in said


def test_models_answers_the_directory_this_deployment_serves(
    client: TestClient,
) -> None:
    """The names on disk, sorted, and nothing declared twice."""
    resp = client.get(f"{BASE}/models")

    assert resp.status_code == 200
    assert resp.json() == sorted(SERVED)


# ----------------------------------------------------------------- the personal-data scan


def test_the_scan_answers_over_the_sample_s_own_review_text(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sample, the language and the model in, a `PersonalDataDetected` out.

    Both model steps are answered here: the detector claims nothing this time, so the phone is the
    rule scan's, and the confirmation is what carries its span into the answer. Every offset is
    read back off the text rather than written down, which is the rule -- `review_text` is the
    frame of reference and nothing afterwards may reflow it.
    """
    asked = install_model_answers(
        monkeypatch,
        **{VERIFIER: json.dumps({"detected": []})},
    )

    resp = client.post(
        f"{BASE}/data-quality/personal-data",
        json={**SAMPLE, "language": "vi", "verifier_model": VERIFIER},
    )

    assert resp.status_code == 200
    answer = resp.json()
    assert answer["claims"] == [["PHONE", PHONE]]
    # The confirmation read the same answer, which carries no `confirmed` key: it confirmed no
    # span, and a span nothing confirmed is not in the answer.
    assert answer["spans"] == []
    assert PHONE in answer["review_text"]
    assert asked == [VERIFIER, VERIFIER]


def test_the_scan_confirms_what_the_verifier_confirms(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same route with the confirmation answering: one span, and its offsets slice back."""
    install_model_answers(
        monkeypatch,
        **{
            VERIFIER: json.dumps(
                {
                    "detected": [],
                    "confirmed": [
                        {"id": 1, "reason": "số của khách", "confirmed": True}
                    ],
                }
            )
        },
    )

    resp = client.post(
        f"{BASE}/data-quality/personal-data",
        json={**SAMPLE, "language": "vi", "verifier_model": VERIFIER},
    )

    answer = resp.json()
    span = answer["spans"][0]
    assert answer["review_text"][span["start"] : span["end"]] == PHONE
    assert span["placeholder"] == "<PHONE_1>"
    assert span["reason"] == "số của khách"


def test_the_scan_s_declarations_are_not_keys_of_the_record(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read at the seam the handler owns: what is handed on is what arrived.

    `language` and `verifier_model` are declarations about this request, so the sample the service
    is handed is the corpus's own record -- every key it carries, including one nothing here reads,
    and neither of the two the caller ticked with.
    """
    handed: dict[str, Any] = {}

    async def detecting(
        config: Any, sample: Any, language: Any
    ) -> PersonalDataDetected:
        handed.update({"sample": sample, "language": language})
        return PersonalDataDetected(review_text="")

    monkeypatch.setattr(route, "detect_personal_data", detecting)

    resp = client.post(
        f"{BASE}/data-quality/personal-data",
        json={**SAMPLE, "language": "en", "verifier_model": VERIFIER},
    )

    assert resp.status_code == 200
    assert handed["language"] == "en"
    # Read back through JSON, because the schema declares the two sequences as tuples and what
    # arrived was an array: the fact being asserted is the keys and their values, not the type
    # `model_dump` hands over.
    assert json.loads(json.dumps(handed["sample"])) == dict(SAMPLE)
    assert handed["sample"]["source"] == SOURCE


def test_an_unserved_verifier_is_refused_before_any_model_is_called(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """422 naming the name and the served list, so the caller learns which."""
    forbid_model_calls(monkeypatch)

    resp = client.post(
        f"{BASE}/data-quality/personal-data",
        json={**SAMPLE, "verifier_model": UNSERVED},
    )

    assert resp.status_code == 422
    assert UNSERVED in resp.json()["detail"]
    assert JUROR in resp.json()["detail"]


# ----------------------------------------------------------------- replacing, with no model


# ----------------------------------------------------------------- redacting, with no model


def test_the_redact_route_replaces_a_handed_back_value_in_every_field(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Where the record's three `new_` keys come from, and the reach `replace` does not have.

    A span indexes `review_text`; the turns and the label are other strings, so this replaces by
    value across the record. Its body carries no model either, so there is no name here to refuse.
    """
    forbid_model_calls(monkeypatch)

    resp = client.post(
        f"{BASE}/data-quality/personal-data/redact",
        json={**SAMPLE, "detected": DETECTED},
    )

    assert resp.status_code == 200
    answer = resp.json()["sample"]
    assert PHONE not in json.dumps(answer, ensure_ascii=False)
    assert answer["messages"][0]["content"] == str(
        SAMPLE["messages"][0]["content"]
    ).replace(PHONE, "<PHONE_1>")
    # Everything the value was not in comes back as it arrived, including a corpus key this
    # service does not read: what is answered is the record, not a copy of the part it rewrote.
    assert answer["messages"][1] == SAMPLE["messages"][1]
    assert answer["tools"] == SAMPLE["tools"]
    assert answer["label"] == SAMPLE["label"]
    assert answer["id"] == SAMPLE["id"]
    assert answer["source"] == SOURCE


def test_the_redacted_record_comes_back_with_the_text_it_now_reads_as(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The half a reviewer can actually check, and the one place the label is visibly redacted.

    A record is JSON, and *the phone number in the argument is the same one as in the turn* is a
    claim nobody reads off JSON. Rendered forward from the redacted record -- the turns, the
    catalog, then the label -- so the two placeholders stand one screen apart and are the same
    string, which is what co-reference means here.
    """
    forbid_model_calls(monkeypatch)
    # The number the customer gave, carried into the call that was labelled -- which is the whole
    # case: a label is copied out of the conversation, so it holds what the conversation held.
    called = {
        **SAMPLE,
        "label": [{"name": "OpenTicket", "arguments": {"ma_khach": PHONE}}],
    }

    resp = client.post(
        f"{BASE}/data-quality/personal-data/redact",
        json={**called, "detected": DETECTED},
    )

    text = resp.json()["review_text"]
    assert PHONE not in text
    # The label is *in* the text, and carries the placeholder the turn carries -- one string, so
    # a model reading the pair still reads them as the same person's number.
    said, label = text.split("label: ")
    assert "<PHONE_1>" in said
    assert "<PHONE_1>" in label
    # The same text a scan builds, so the offsets a second scan answers index this one.
    assert text == build_review_text(resp.json()["sample"])


def test_the_spans_handed_back_are_not_a_key_of_the_record(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`detected` is a declaration about this request, on the same terms as the scan's two.

    So what comes back is the record's own keys and nothing about how it was redacted: the page
    composes the record, and this route answers one of its parts.
    """
    forbid_model_calls(monkeypatch)

    resp = client.post(
        f"{BASE}/data-quality/personal-data/redact",
        json={**SAMPLE, "detected": DETECTED},
    )

    assert set(resp.json()["sample"]) == set(SAMPLE)


def test_no_span_handed_back_is_nothing_replaced(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reviewer who handed back no span asked for nothing to be rewritten.

    Which is also what the last rectangle sends where the scan was never run: the record comes
    back as it arrived rather than refused, because nothing was confirmed to replace.
    """
    forbid_model_calls(monkeypatch)

    resp = client.post(
        f"{BASE}/data-quality/personal-data/redact",
        json={
            **SAMPLE,
            "detected": {"review_text": "", "claims": [], "spans": []},
        },
    )

    assert resp.status_code == 200
    assert resp.json()["sample"] == dict(SAMPLE)


# ----------------------------------------------------------------- is the label even callable


def test_a_label_the_catalog_cannot_take_is_answered_with_what_is_wrong_with_it(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**The shape a corpus really arrives in**: a tool's name where a call should be.

    The store writes `schema_valid` false for this row at write time, which somebody finds days
    later reading the corpus. Asked here, the same rule reaches the reviewer while the sample is
    still in front of them -- and it names the call and says what a call is made of, because
    *invalid* on its own sends them nowhere.
    """
    forbid_model_calls(monkeypatch)

    resp = client.post(
        f"{BASE}/data-quality/label",
        json={**SAMPLE, "label": ["OpenTicket"]},
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "schema_valid": False,
        "faults": [
            'call 1 does not read as a tool call: it has to be {"name": ..., "arguments": {...}}'
        ],
    }


def test_a_label_the_catalog_can_take_is_answered_with_nothing_to_say(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The sample's own label, which calls the one tool it was offered and supplies what it asks."""
    forbid_model_calls(monkeypatch)

    resp = client.post(f"{BASE}/data-quality/label", json=dict(SAMPLE))

    assert resp.status_code == 200
    assert resp.json() == {"schema_valid": True, "faults": []}


def test_a_label_nothing_can_call_is_a_check_and_never_a_refusal(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """200 with a verdict, not 422. What the label ought to be is the reviewer's to say.

    A route that refused would decide it from the far side of a fetch, and a corpus of hard rows
    is exactly the corpus worth labelling.
    """
    forbid_model_calls(monkeypatch)

    resp = client.post(
        f"{BASE}/data-quality/label",
        json={**SAMPLE, "label": [{"name": "Refund", "arguments": {}}]},
    )

    assert resp.status_code == 200
    assert resp.json()["faults"] == [
        "call 1 names Refund, which this sample's catalog does not offer"
    ]


def test_a_sample_needing_no_call_is_not_a_fault(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty label is an answer, and both spellings of it reach this route from the page."""
    forbid_model_calls(monkeypatch)

    empty = client.post(f"{BASE}/data-quality/label", json={**SAMPLE, "label": []})
    absent = client.post(f"{BASE}/data-quality/label", json={**SAMPLE, "label": None})

    assert empty.json() == {"schema_valid": True, "faults": []}
    assert absent.json() == {"schema_valid": True, "faults": []}


# ----------------------------------------------------------------- the two that report nothing


def test_duplicate_answers_null_at_two_hundred(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing failed, and there is nothing to report."""
    forbid_model_calls(monkeypatch)

    resp = client.post(f"{BASE}/data-quality/duplicate", json=dict(SAMPLE))

    assert resp.status_code == 200
    assert resp.json() is None


def test_abnormal_answers_null_at_two_hundred(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other check with nothing to report. Neither declares a shape to return."""
    forbid_model_calls(monkeypatch)

    resp = client.post(f"{BASE}/data-quality/abnormal", json=dict(SAMPLE))

    assert resp.status_code == 200
    assert resp.json() is None


# ----------------------------------------------------------------- the panel


def test_ai_review_answers_the_panel_and_no_finetuned_reviewer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both reviewers side by side, and `sft` is `None` where none was ticked.

    Two jurors asked once each, each vote naming the model that cast it, and the
    consensus is the answer as a juror wrote it. `sft: null` is a reviewer the request declared
    none of, which is not a reviewer that disagreed.
    """
    asked = install_model_answers(
        monkeypatch,
        **{
            JUROR: {"reason": "Khách đã cho mã.", "label": OPEN_TICKET},
            SECOND: {"reason": "Đủ thông tin.", "label": OPEN_TICKET},
        },
    )

    resp = client.post(
        f"{BASE}/ai-review",
        json={**SAMPLE, "language": "vi", "jury_models": [JUROR, SECOND]},
    )

    assert resp.status_code == 200
    answer = resp.json()
    assert sorted(asked) == [JUROR, SECOND]
    assert [vote["model_name"] for vote in answer["llm"]["votes"]] == [JUROR, SECOND]
    assert answer["llm"]["label_agreement"] == 1.0
    assert json.loads(answer["llm"]["consensus"]) == OPEN_TICKET
    assert answer["sft"] is None


def test_a_panel_of_none_asks_nothing_and_answers_nothing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty tick is no panel, not an empty panel: `llm` is `None` and no model is called."""
    forbid_model_calls(monkeypatch)

    resp = client.post(f"{BASE}/ai-review", json=dict(SAMPLE))

    assert resp.status_code == 200
    assert resp.json() == {"llm": None, "sft": None}


def test_the_review_s_declarations_are_not_keys_of_the_record(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same seam as the scan's: the three ticks are not the record's keys."""
    handed: dict[str, Any] = {}

    async def predicting(config: Any, sample: Any, language: Any) -> None:
        handed.update({"sample": sample, "language": language})
        return None

    monkeypatch.setattr(route, "predict_tool_decision_by_llm", predicting)

    resp = client.post(
        f"{BASE}/ai-review",
        json={**SAMPLE, "language": "en", "jury_models": [JUROR]},
    )

    assert resp.status_code == 200
    assert handed["language"] == "en"
    assert json.loads(json.dumps(handed["sample"])) == dict(SAMPLE)


def test_an_unserved_juror_is_refused_before_any_model_is_called(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unserved name on the other route, and the first of two refusals that read alike."""
    forbid_model_calls(monkeypatch)

    resp = client.post(
        f"{BASE}/ai-review", json={**SAMPLE, "jury_models": [JUROR, UNSERVED]}
    )

    assert resp.status_code == 422
    assert UNSERVED in resp.json()["detail"]
    assert "Served" in resp.json()["detail"]


def test_a_served_juror_whose_file_names_no_endpoint_is_refused_for_its_own_reason(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A name with no file and no explicit URL, and the reason the two 422s are pinned apart.

    This name *is* served -- the directory holds its file -- so `check_served_models` passes it. The
    refusal comes from the juror being built, before any record: a config naming no endpoint is a
    call to somewhere nobody declared, never a provider's default.
    """
    forbid_model_calls(monkeypatch)

    resp = client.post(
        f"{BASE}/ai-review", json={**SAMPLE, "jury_models": [NO_ENDPOINT]}
    )

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert NO_ENDPOINT in detail
    assert "base_url" in detail
    assert "Served" not in detail


def test_a_ticked_finetuned_reviewer_is_refused_as_one_this_deployment_cannot_run(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§ *Open*, settled as a refusal: 422, not a 500 behind a model that resolved.

    Where its confidence comes from is undecided, so `ToolDecisionSFTPrediction.predict` has no
    answer to give -- and ticking a reviewer this deployment cannot run is a declaration it cannot
    act on, which is what every other 422 on this route says too.
    """
    forbid_model_calls(monkeypatch)

    resp = client.post(f"{BASE}/ai-review", json={**SAMPLE, "sft_model": JUROR})

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "confidence" in detail
    # Not the unserved refusal's words: this name *is* served, and two 422s that read alike are
    # two the caller cannot tell apart.
    assert "Served" not in detail
    assert "served here" not in detail


def test_the_finetuned_reviewer_is_refused_before_the_panel_is_paid_for(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A request that ticks both is one refusal, not one refusal and N calls billed for nothing.

    The refusal is a declaration about this deployment and not about this sample, so nothing about
    it needs the panel's answer -- and every other refusal on this route happens before a model is
    called, which is the vocabulary this one has to keep.
    """
    asked = install_model_answers(
        monkeypatch, **{JUROR: {"reason": "stubbed", "label": OPEN_TICKET}}
    )

    resp = client.post(
        f"{BASE}/ai-review",
        json={**SAMPLE, "jury_models": [JUROR], "sft_model": JUROR},
    )

    assert resp.status_code == 422
    assert asked == []


# ----------------------------------------------------------- what the corpus holds, counted

WROTE_AT = datetime(2026, 9, 16, 15, 30, 45)

LOOKUP_CATALOG = [
    {
        "type": "function",
        "function": {
            "name": "Lookup",
            "parameters": {"type": "object", "required": ["id"], "properties": {}},
        },
    }
]
ASKED: Mapping[str, Any] = {
    "messages": [{"role": "user", "content": "nợ bao nhiêu"}],
    "tools": LOOKUP_CATALOG,
}
THANKED: Mapping[str, Any] = {
    "messages": [{"role": "user", "content": "cảm ơn em"}],
    "tools": LOOKUP_CATALOG,
}
LOOKED_UP = [{"name": "Lookup", "arguments": {"id": "KH-1"}}]


@pytest.fixture
def attached(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_endpoints: None
) -> Iterator[None]:
    """A database of this test's own, attached the way a deployment attaches one.

    `no_endpoints` is named rather than left to run on its own: it clears
    `DATAFORCE_DATABASE_URL`, and it has to do that before this sets it.
    """
    monkeypatch.setenv(
        "DATAFORCE_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'store.sqlite3'}"
    )
    engine = db.open_engine()
    assert engine is not None
    create_tables(engine)

    yield

    Base.metadata.drop_all(engine)


def store_one_sample(**overridden: Any) -> None:
    """One row in each table under one key, which is what the two tables holding the same rows is.

    Written straight in rather than posted: no route writes one yet (T16), and § *What is not
    schedulable yet* is why the counting is built before the writing.
    """
    columns: dict[str, Any] = {
        "input": ASKED,
        "label": LOOKED_UP,
        "language": "vi",
        "personal_data": [],
        "ambiguous": "LOW",
        "domain": "debt_collection",
        "call_trigger": ["condition_met"],
        "number_turns": 1,
        "number_label_tools": 1,
        "number_provided_tools": 1,
        "schema_valid": True,
    }
    key = uuid.uuid4()
    times = {"created_time": WROTE_AT, "modified_time": WROTE_AT}
    session = db.open_session()
    assert session is not None
    with session, session.begin():
        session.add(ToolDecisionRecord(id=key, document={}, **times))
        session.add(ToolDecisionSample(id=key, **times, **(columns | overridden)))


def store_a_corpus() -> None:
    """Three rows: two that are one another's duplicate, and one that answered nothing."""
    store_one_sample()
    store_one_sample()
    store_one_sample(
        input=THANKED,
        label=None,
        domain="telesale",
        call_trigger=["user_utterance"],
        number_label_tools=0,
    )


def test_the_statistics_say_what_to_set_where_no_database_is_attached(
    client: TestClient,
) -> None:
    """503 rather than zeros: *a corpus with nothing in it* and *nothing was asked* are different
    claims, and the detail names the variable so the message says what to set."""
    resp = client.get(f"{BASE}/records/stats")

    assert resp.status_code == 503
    assert "DATAFORCE_DATABASE_URL" in resp.json()["detail"]


def test_no_other_route_is_affected_by_there_being_no_database(
    client: TestClient,
) -> None:
    """The store is a place to put the result, never a dependency of the review."""
    assert client.get(f"{BASE}/models").status_code == 200
    assert client.get(f"{BASE}/").status_code == 200


def test_every_statistic_is_in_the_answer_over_rows_a_test_wrote(
    client: TestClient, attached: None
) -> None:
    """§ *The statistics* in full, each figure beside the total it came out of."""
    store_a_corpus()

    answered = client.get(f"{BASE}/records/stats").json()

    assert answered["sample_totals"] == {
        "tool_decision_record": 3,
        "tool_decision_dataset": 3,
    }
    assert answered["counted_distribution_by_facet"]["domain"] == {
        "debt_collection": 2,
        "telesale": 1,
    }
    assert answered["counted_distribution_by_facet"]["schema_valid"] == {"true": 3}
    # How many rows make each number of calls: a facet column, so the per-facet distribution
    # is where it is read -- `label_summary` holds no second count of the same thing.
    assert answered["counted_distribution_by_facet"]["number_label_tools"] == {
        "0": 1,
        "1": 2,
    }
    assert (
        answered["counted_distribution_by_domain_and_call_trigger"]["debt_collection"][
            "condition_met"
        ]
        == 2
    )
    assert (
        answered["counted_distribution_by_domain_and_call_trigger"]["telesale"][
            "user_utterance"
        ]
        == 1
    )
    assert answered["label_summary"] == {
        "total": 3,
        "number_not_null_label": 2,
        "number_diff_label": 2,
    }
    assert answered["number_tools_offered"] == 1
    assert answered["tool_call_counts"] == {"Lookup": 2}
    assert len(answered["duplicate_groups"]["duplicate_content_same_label"][0]) == 2
    assert answered["duplicate_groups"]["duplicate_content_diff_label"] == []


def test_a_value_nobody_declared_still_gets_an_axis_of_its_own(
    client: TestClient, attached: None
) -> None:
    """The grid is what the corpus carries, so a domain or a trigger somebody typed is in it the
    moment one sample carries it -- and the route is where that has to still be true, because the
    crossing happens two layers down."""
    store_a_corpus()
    store_one_sample(domain="upsell", call_trigger=["escalation"])

    matrix = client.get(f"{BASE}/records/stats").json()[
        "counted_distribution_by_domain_and_call_trigger"
    ]

    assert sum(len(columns) for columns in matrix.values()) == 3 * 3
    assert matrix["upsell"]["escalation"] == 1
    assert matrix["debt_collection"]["escalation"] == 0


def test_the_same_input_under_two_labels_is_the_queue_the_route_hands_back(
    client: TestClient, attached: None
) -> None:
    """The group that is the point of grouping: one of the two labels is wrong, or the task is
    arguable where the guideline said it was not. A count would not open; row keys do."""
    store_one_sample()
    store_one_sample(label=[{"name": "Lookup", "arguments": {"id": "KH-2"}}])

    duplicates = client.get(f"{BASE}/records/stats").json()["duplicate_groups"]

    assert len(duplicates["duplicate_content_diff_label"][0]) == 2
    assert duplicates["duplicate_content_same_label"] == []


def test_an_empty_corpus_answers_zeros_rather_than_failing(
    client: TestClient, attached: None
) -> None:
    """A database attached and nothing in it is the state a deployment starts in."""
    answered = client.get(f"{BASE}/records/stats").json()

    assert answered["sample_totals"] == {
        "tool_decision_record": 0,
        "tool_decision_dataset": 0,
    }
    assert answered["counted_distribution_by_domain_and_call_trigger"] == {}
    assert set(answered["counted_distribution_by_facet"]) and all(
        counted == {} for counted in answered["counted_distribution_by_facet"].values()
    )
    assert answered["label_summary"]["total"] == 0
    assert answered["duplicate_groups"]["duplicate_content_same_label"] == []


def test_nothing_is_cached_so_a_write_between_two_calls_shows(
    client: TestClient, attached: None
) -> None:
    """Each figure is a query when it is asked, which is what keeps a panel from going stale."""
    first = client.get(f"{BASE}/records/stats").json()

    store_one_sample()
    second = client.get(f"{BASE}/records/stats").json()

    assert first["sample_totals"]["tool_decision_dataset"] == 0
    assert second["sample_totals"]["tool_decision_dataset"] == 1


# ----------------------------------------------------------- one reviewed sample, into both tables

POSTED_ID = "s4471"
POSTED_PHONE = "0912345678"
TICKET_CATALOG = [
    {
        "type": "function",
        "function": {
            "name": "OpenTicket",
            "parameters": {"type": "object", "required": [], "properties": {}},
        },
    }
]
OPENED = [{"name": "OpenTicket", "arguments": {}}]
POSTED_TURN = f"Chào anh {POSTED_PHONE}, mở phiếu"
REDACTED_TURN = "Chào anh <PHONE_1>, mở phiếu"
SCAN_TEXT = f"user: {POSTED_TURN}"
POSTED_SCAN: Mapping[str, Any] = {
    "review_text": SCAN_TEXT,
    "claims": [["PHONE", POSTED_PHONE]],
    "spans": [
        {
            "id": 1,
            "start": SCAN_TEXT.index(POSTED_PHONE),
            "end": SCAN_TEXT.index(POSTED_PHONE) + len(POSTED_PHONE),
            "personal_data_class": "PHONE",
            "placeholder": "<PHONE_1>",
            "reason": None,
        }
    ],
    "outcome": "redacted",
}
TICKED: Mapping[str, Any] = {
    "language": "vi",
    "ambiguous": "LOW",
    "domain": "customer_care",
    "call_trigger": ["user_utterance"],
    "direction": "inbound",
    "have_conversation_flow": False,
}


def build_review(**overridden: Any) -> dict[str, Any]:
    """The thirteen keys as `ui/` assembles them, with every step answered."""
    review: dict[str, Any] = {
        "id": POSTED_ID,
        "messages": [{"role": "user", "content": POSTED_TURN}],
        "tools": TICKET_CATALOG,
        "label": OPENED,
        "new_messages": [{"role": "user", "content": REDACTED_TURN}],
        "new_tools": None,
        "new_label": OPENED,
        "personal_data": dict(POSTED_SCAN),
        "duplicate": None,
        "abnormal": None,
        "llm": None,
        "sft": None,
        "class": dict(TICKED),
    }
    return review | overridden


def test_an_install_nobody_configured_takes_the_first_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_endpoints: None
) -> None:
    """§ *Context* -- unset means a file in the working directory, and startup makes the tables.

    This is the whole of what *a database is already there* has to mean: nothing exported, no
    command run, and the first record lands. `with` rather than a bare `TestClient`, because the
    tables are made in the app's lifespan and a client that never enters it never starts the app.

    `chdir` keeps the file out of the repository, and is also what makes the assertion about it
    honest -- the default is resolved against the working directory.
    """
    monkeypatch.delenv("DATAFORCE_DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    with TestClient(create_app()) as unconfigured:
        resp = unconfigured.post(f"{BASE}/records", json=build_review())

        assert resp.status_code == 200, resp.text
        assert unconfigured.get(f"{BASE}/records/stats").json()["sample_totals"] == {
            "tool_decision_record": 1,
            "tool_decision_dataset": 1,
        }
    assert (tmp_path / DEFAULT_STORE_FILE).exists()


def test_a_record_says_where_to_attach_a_database_rather_than_dropping_it(
    client: TestClient,
) -> None:
    """The store is a place to put the result, never a dependency of the review -- so the refusal
    names the variable and the reviewer still has every answer on their screen."""
    resp = client.post(f"{BASE}/records", json=build_review())

    assert resp.status_code == 503
    assert "DATAFORCE_DATABASE_URL" in resp.json()["detail"]


def test_a_finished_record_lands_in_both_tables_and_the_answer_says_so(
    client: TestClient, attached: None
) -> None:
    """The end of the flow: eight steps, then two rows and a key to say which sample they are."""
    resp = client.post(f"{BASE}/records", json=build_review())

    assert resp.status_code == 200
    answered = resp.json()
    assert answered["created_time"] == answered["modified_time"]
    assert client.get(f"{BASE}/records/stats").json()["sample_totals"] == {
        "tool_decision_record": 1,
        "tool_decision_dataset": 1,
    }


def test_the_corpus_reads_back_as_a_page_of_the_redacted_table(
    client: TestClient, attached: None
) -> None:
    """The gap between the queue and the statistics: a row somebody wrote, readable.

    **Off `tool_decision_dataset` and off nothing else.** The record table keeps what arrived so a
    review can be audited; serving it here would put the phone number on the screen of anyone who
    can open the page, which is what the whole part exists to prevent. So the raw turn must not be
    in this answer, and the redacted one must.
    """
    stored = client.post(f"{BASE}/records", json=build_review())

    resp = client.get(f"{BASE}/records")

    assert resp.status_code == 200
    listed = resp.json()
    assert listed["total"] == 1
    (row,) = listed["samples"]
    # The key the write answered, not one this test derived: how a name becomes a key is the
    # store's, and a test that recomputed it would agree with itself rather than with the store.
    assert row["key"] == stored.json()["id"]
    assert POSTED_PHONE not in resp.text
    assert REDACTED_TURN.startswith(row["said"][:10])
    # The facets it was filed under, which is what the list is read for.
    assert row["domain"] == TICKED["domain"]
    assert row["ambiguous"] == TICKED["ambiguous"]
    assert row["personal_data"] == ["PHONE"]
    assert row["schema_valid"] is True


def test_one_stored_sample_comes_back_whole_and_stats_is_not_read_as_a_key(
    client: TestClient, attached: None
) -> None:
    """The detail behind a row, and the route-order trap `/queue/next` already taught.

    `stats` is this router's own name. Declared after the route that takes a `{key}` it would be
    parsed as one, and asking for the statistics would answer *no stored sample under stats*.
    """
    key = client.post(f"{BASE}/records", json=build_review()).json()["id"]

    resp = client.get(f"{BASE}/records/{key}")

    assert resp.status_code == 200
    one = resp.json()
    assert one["input"]["messages"] == [{"role": "user", "content": REDACTED_TURN}]
    assert one["label"] == OPENED
    assert one["facets"]["schema_valid"] is True
    assert POSTED_PHONE not in resp.text
    assert client.get(f"{BASE}/records/stats").status_code == 200


def test_a_label_naming_a_tool_without_calling_it_reads_back_as_one_nothing_validated(
    client: TestClient, attached: None
) -> None:
    """**The row a person opens this list to find.**

    A corpus line whose label is a bare tool name -- `["VerifyEmail_15d"]`, the argument baked
    into the name instead of supplied -- calls nothing the catalog offers. It is stored, because
    nothing about a corpus is refused here, and it is stored *saying so*: no calls, and nothing
    validated. `0` beside `false` is what tells it from a sample correctly labelled as needing no
    tool, which is `0` beside `true`.
    """
    named_only = build_review(
        id="s-bare", label=["VerifyEmail_15d"], new_label=["VerifyEmail_15d"]
    )
    key = client.post(f"{BASE}/records", json=named_only).json()["id"]

    one = client.get(f"{BASE}/records/{key}").json()

    assert one["label"] == ["VerifyEmail_15d"]
    assert one["facets"]["number_label_tools"] == 0
    assert one["facets"]["schema_valid"] is False
    (row,) = [
        each
        for each in client.get(f"{BASE}/records").json()["samples"]
        if each["key"] == key
    ]
    assert row["schema_valid"] is False
    assert row["number_label_tools"] == 0


def test_the_warning_and_the_stored_column_are_one_rule_and_not_two(
    client: TestClient, attached: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What the route warns about and what the row is marked with have to be the same thing.

    Two readings of *callable* would let the page wave a label through and the corpus mark that
    same label broken -- the failure this check exists to close, arrived at from the other side.
    """
    forbid_model_calls(monkeypatch)
    named_only = build_review(
        id="s-warned", label=["VerifyEmail_15d"], new_label=["VerifyEmail_15d"]
    )

    warned = client.post(f"{BASE}/data-quality/label", json=named_only)
    key = client.post(f"{BASE}/records", json=named_only).json()["id"]

    assert warned.json()["schema_valid"] is False
    assert warned.json()["faults"][0].startswith("call 1 does not read as a tool call")
    assert client.get(f"{BASE}/records/{key}").json()["facets"]["schema_valid"] is False


def test_a_stored_sample_nobody_holds_is_a_sentence_and_not_an_empty_row(
    client: TestClient, attached: None
) -> None:
    """404 naming the key, on the same terms as the queue's: nothing was written and nothing is."""
    resp = client.get(f"{BASE}/records/{uuid.uuid4()}")

    assert resp.status_code == 404
    assert "no stored sample under" in resp.json()["detail"]


def test_the_stored_row_carries_what_ships_and_the_facets_it_was_ticked_with(
    client: TestClient, attached: None
) -> None:
    """Read back through the statistics, which is the only thing that reads the table: the
    redacted turn is what the corpus holds, and the ticks are what it is counted by."""
    client.post(f"{BASE}/records", json=build_review())

    counted = client.get(f"{BASE}/records/stats").json()
    assert counted["counted_distribution_by_facet"]["domain"] == {"customer_care": 1}
    assert counted["counted_distribution_by_facet"]["personal_data"] == {'["PHONE"]': 1}
    assert counted["counted_distribution_by_facet"]["number_turns"] == {"1": 1}
    assert counted["tool_call_counts"] == {"OpenTicket": 1}


def test_a_sample_nobody_scanned_names_the_step_and_writes_nothing(
    client: TestClient, attached: None
) -> None:
    """§ *The precondition*: `khử nhận dạng` is something the `dataset` table has to be able to
    prove about every row it holds, and the cheapest proof is that a row failing it never arrived."""
    resp = client.post(f"{BASE}/records", json=build_review(personal_data=None))

    assert resp.status_code == 422
    assert "personal-data scan" in resp.json()["detail"]
    assert "personal_data is null" in resp.json()["detail"]
    assert client.get(f"{BASE}/records/stats").json()["sample_totals"] == {
        "tool_decision_record": 0,
        "tool_decision_dataset": 0,
    }


def test_a_confirmed_value_still_in_what_ships_names_the_redaction_and_writes_nothing(
    client: TestClient, attached: None
) -> None:
    """The refusal a fine is attached to. The reviewer is told which card to go back to, not that
    something went wrong."""
    resp = client.post(
        f"{BASE}/records",
        json=build_review(new_messages=[{"role": "user", "content": POSTED_TURN}]),
    )

    assert resp.status_code == 422
    assert "redaction" in resp.json()["detail"]
    # The span, never the value. A refusal that echoed it would put personal data in a response
    # body and in whatever logs one -- the corpus is not the only place it must not end up.
    assert "span 1 (PHONE)" in resp.json()["detail"]
    assert POSTED_PHONE not in resp.json()["detail"]
    assert client.get(f"{BASE}/records/stats").json()["sample_totals"] == {
        "tool_decision_record": 0,
        "tool_decision_dataset": 0,
    }


def test_a_declared_facet_nobody_ticked_is_named_rather_than_becoming_a_null_column(
    client: TestClient, attached: None
) -> None:
    """A facet the table has a column for and the review did not answer is a write that must
    fail. Named here so the reviewer reads a facet and not a constraint."""
    ticked = {name: TICKED[name] for name in TICKED if name != "domain"}

    resp = client.post(f"{BASE}/records", json=build_review(**{"class": ticked}))

    assert resp.status_code == 422
    assert "domain" in resp.json()["detail"]


def test_a_facet_posted_as_null_is_as_unanswered_as_one_left_out(
    client: TestClient, attached: None
) -> None:
    """Both reach the same `NOT NULL` column, so both are the same refusal. Read with `is None`
    and not by falsiness, which is the next test's half."""
    ticked = dict(TICKED) | {"domain": None}

    resp = client.post(f"{BASE}/records", json=build_review(**{"class": ticked}))

    assert resp.status_code == 422
    assert "domain" in resp.json()["detail"]


def test_a_facet_answered_false_or_empty_is_answered(
    client: TestClient, attached: None
) -> None:
    """`have_conversation_flow: false` and `call_trigger: []` are claims a reviewer made -- *not
    part of a flow*, and *this sample calls nothing*. A check that refused what is falsy would
    refuse the no-call sample, which is the one § *The facets* is most careful to say is an
    answer."""
    ticked = dict(TICKED) | {"have_conversation_flow": False, "call_trigger": []}

    resp = client.post(f"{BASE}/records", json=build_review(**{"class": ticked}))

    assert resp.status_code == 200


def test_a_label_that_never_parsed_is_refused_at_the_envelope(
    client: TestClient, attached: None
) -> None:
    """The page carries an unparsed label as `{unparsed: ...}` rather than guessing at it, and
    this is where that carrier stops: a column the corpus is counted by does not take one."""
    resp = client.post(
        f"{BASE}/records", json=build_review(new_label={"unparsed": "[{name: "})
    )

    assert resp.status_code == 422


def test_a_record_missing_its_id_is_refused_and_an_unknown_key_is_kept(
    client: TestClient, attached: None
) -> None:
    """Both halves of the envelope: `id` is what a row is, and a key the page added is news about
    the page rather than a reason to refuse a review.

    Kept means *in the row*, so it is read back out of `record.document` -- accepted and then
    dropped on the way to the column would pass a check that only read the status."""
    without = build_review()
    del without["id"]
    assert client.post(f"{BASE}/records", json=without).status_code == 422

    resp = client.post(f"{BASE}/records", json=build_review(annotator="minh"))

    assert resp.status_code == 200
    session = db.open_session()
    assert session is not None
    with session:
        stored = session.get(ToolDecisionRecord, uuid.UUID(resp.json()["id"]))
        assert stored is not None
        assert stored.document["annotator"] == "minh"
        assert stored.document["class"] == dict(TICKED)


def test_a_second_post_under_one_name_replaces_the_sample_rather_than_adding_one(
    client: TestClient, attached: None
) -> None:
    """A record posted twice is one sample reviewed twice. `created_time` stays where it was, so
    when the corpus first got this sample survives the second review of it."""
    first = client.post(f"{BASE}/records", json=build_review()).json()

    again = client.post(
        f"{BASE}/records",
        json=build_review(**{"class": dict(TICKED) | {"domain": "telesale"}}),
    ).json()

    assert again["id"] == first["id"]
    assert again["created_time"] == first["created_time"]
    assert again["modified_time"] > first["modified_time"]
    counted = client.get(f"{BASE}/records/stats").json()
    assert counted["sample_totals"]["tool_decision_dataset"] == 1
    assert counted["counted_distribution_by_facet"]["domain"] == {"telesale": 1}


def test_the_statistics_change_the_moment_a_record_lands(
    client: TestClient, attached: None
) -> None:
    """Nothing is cached and nothing is stored: two calls with a write between them differ, which
    is what lets the page ask again after **approve** rather than on a timer."""
    before = client.get(f"{BASE}/records/stats").json()["sample_totals"]

    client.post(f"{BASE}/records", json=build_review())

    assert before["tool_decision_dataset"] == 0
    assert (
        client.get(f"{BASE}/records/stats").json()["sample_totals"][
            "tool_decision_dataset"
        ]
        == 1
    )
