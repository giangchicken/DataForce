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
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from agent_toolkit.llm import set_config_resolver
from fastapi.testclient import TestClient

from dataforce.edge.main import UI, create_app
from dataforce.edge.routers.text2text import tool_decision as route
from dataforce.modalities.text2text.data_quality import (
    PersonalDataDetected,
    personal_data_checking,
)
from dataforce.profile.tool_decision import ai_review, data_quality

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


def answering(monkeypatch: pytest.MonkeyPatch, **answers: Any) -> list[str]:
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


def no_model_answers(monkeypatch: pytest.MonkeyPatch) -> None:
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
    asked = answering(
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
    answering(
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

    monkeypatch.setattr(route, "personal_data_detect", detecting)

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
    no_model_answers(monkeypatch)

    resp = client.post(
        f"{BASE}/data-quality/personal-data",
        json={**SAMPLE, "verifier_model": UNSERVED},
    )

    assert resp.status_code == 422
    assert UNSERVED in resp.json()["detail"]
    assert JUROR in resp.json()["detail"]


# ----------------------------------------------------------------- replacing, with no model


def test_the_replace_route_takes_the_detect_answer_back_and_asks_no_model(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same shape in, the copy out, and no name to refuse.

    Its body carries no model at all, which is why nothing on this route can be refused for a name
    this deployment does not serve -- and why the spans it replaces are the reviewer's rather than
    the detectors'.
    """
    no_model_answers(monkeypatch)

    resp = client.post(f"{BASE}/data-quality/personal-data/replace", json=DETECTED)

    assert resp.status_code == 200
    assert resp.json() == {
        "redacted_text": REVIEW_TEXT.replace(PHONE, "<PHONE_1>"),
        "outcome": "redacted",
    }


# ----------------------------------------------------------------- redacting, with no model


def test_the_redact_route_replaces_a_handed_back_value_in_every_field(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Where the record's three `new_` keys come from, and the reach `replace` does not have.

    A span indexes `review_text`; the turns and the label are other strings, so this replaces by
    value across the record. Its body carries no model either, so there is no name here to refuse.
    """
    no_model_answers(monkeypatch)

    resp = client.post(
        f"{BASE}/data-quality/personal-data/redact",
        json={**SAMPLE, "detected": DETECTED},
    )

    assert resp.status_code == 200
    answer = resp.json()
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


def test_the_spans_handed_back_are_not_a_key_of_the_record(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`detected` is a declaration about this request, on the same terms as the scan's two.

    So what comes back is the record's own keys and nothing about how it was redacted: the page
    composes the record, and this route answers one of its parts.
    """
    no_model_answers(monkeypatch)

    resp = client.post(
        f"{BASE}/data-quality/personal-data/redact",
        json={**SAMPLE, "detected": DETECTED},
    )

    assert set(resp.json()) == set(SAMPLE)


def test_no_span_handed_back_is_nothing_replaced(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reviewer who handed back no span asked for nothing to be rewritten.

    Which is also what the last rectangle sends where the scan was never run: the record comes
    back as it arrived rather than refused, because nothing was confirmed to replace.
    """
    no_model_answers(monkeypatch)

    resp = client.post(
        f"{BASE}/data-quality/personal-data/redact",
        json={
            **SAMPLE,
            "detected": {"review_text": "", "claims": [], "spans": []},
        },
    )

    assert resp.status_code == 200
    assert resp.json() == dict(SAMPLE)


# ----------------------------------------------------------------- the two that report nothing


def test_duplicate_answers_null_at_two_hundred(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing failed, and there is nothing to report."""
    no_model_answers(monkeypatch)

    resp = client.post(f"{BASE}/data-quality/duplicate", json=dict(SAMPLE))

    assert resp.status_code == 200
    assert resp.json() is None


def test_abnormal_answers_null_at_two_hundred(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other check with nothing to report. Neither declares a shape to return."""
    no_model_answers(monkeypatch)

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
    asked = answering(
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
    no_model_answers(monkeypatch)

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

    monkeypatch.setattr(route, "tool_decision_llm_predict", predicting)

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
    no_model_answers(monkeypatch)

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

    This name *is* served -- the directory holds its file -- so `checked_names` passes it. The
    refusal comes from the juror being built, before any record: a config naming no endpoint is a
    call to somewhere nobody declared, never a provider's default.
    """
    no_model_answers(monkeypatch)

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
    no_model_answers(monkeypatch)

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
    asked = answering(
        monkeypatch, **{JUROR: {"reason": "stubbed", "label": OPEN_TICKET}}
    )

    resp = client.post(
        f"{BASE}/ai-review",
        json={**SAMPLE, "jury_models": [JUROR], "sft_model": JUROR},
    )

    assert resp.status_code == 422
    assert asked == []
