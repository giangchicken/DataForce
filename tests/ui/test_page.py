"""`ui/` run for real: the page's own behaviour in node, and the markup facts read here.

**Why node and not a browser.** This repository installs no browser and no `jsdom`. A page whose
behaviour nothing runs is a page nobody has checked, so `dom.js` is the smallest DOM `app.js` will
start against and `page.js` drives the real script in it. What the page *looks* like -- whether a
panel is cramped, whether a colour can be read -- is not checkable here and is not claimed to be.

`reading.js` answers the one thing a stub cannot: that the field names the page reads are the field
names the service writes. Those are declared in `profile/tool_decision/schema.py` and read in
JavaScript, and nothing but this holds the two together.
"""

import json
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dataforce.edge.database import db
from dataforce.edge.main import create_app
from dataforce.profile.tool_decision.sample_building import create_tables
from dataforce.profile.tool_decision.utils import build_review_text
from dataforce.tables import Base
from tests.edge.test_endpoints import BASE, POSTED_PHONE, build_review

CHECKS = Path(__file__).parent / "page.js"
READING = Path(__file__).parent / "reading.js"
UI = Path(__file__).parents[2] / "src" / "dataforce" / "ui"
PAGE = (UI / "index.html").read_text(encoding="utf-8")

# Words that would mean the guide is explaining the wiring rather than the work.
WIRING = (
    "POST ",
    "GET ",
    "config/",
    ".py",
    "/data-quality",
    "/records",
    "/ai-review",
    "endpoint",
)

APP = (UI / "app.js").read_text(encoding="utf-8")
GUIDE = PAGE[PAGE.index('id="sheet-guide"') : PAGE.index('id="sheet-import"')]


def run_node(*taken: str) -> None:
    """One node script, skipped loudly where node is absent rather than passing quietly."""
    node = shutil.which("node")
    if node is None:
        pytest.skip(
            "node is not installed, so the page's own checks have nothing to run in"
        )
    done = subprocess.run([node, *taken], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, f"\n{done.stdout}\n{done.stderr}"


def test_the_page_behaves_as_the_spec_says() -> None:
    """Every sentence § *The page* makes about what happens, run against `app.js` itself."""
    run_node(str(CHECKS))


def test_the_screen_is_two_panes_and_two_fixed_bars() -> None:
    """§ *The page* -- the sample on the left, the review on the right, and neither bar scrolling.

    Read off the markup because the shape is the markup's: a stub has no layout, so *the sample
    never leaves the screen* is proven there by the left pane not being rewritten, and here by
    there being a left pane at all.
    """
    assert '<main class="work">' in PAGE
    assert 'id="pane-sample"' in PAGE
    assert 'id="pane-review"' in PAGE
    assert '<header class="top">' in PAGE
    assert '<footer class="actions">' in PAGE
    # The two acts the bar is allowed to hold, and nothing else that posts anything.
    bar = PAGE[PAGE.index('<footer class="actions">') : PAGE.index("</footer>")]
    assert bar.count("<button") == 2
    assert 'id="skip"' in bar
    assert 'id="submit"' in bar


def test_the_review_pane_is_the_checks_and_two_decisions() -> None:
    """Eight steps are two decisions: only three of the eight ever held one, and the facets belong
    to the second because they describe the label's sample."""
    review = PAGE[
        PAGE.index('id="pane-review"') : PAGE.index('<footer class="actions">')
    ]
    assert review.count('<article class="panel"') == 3
    for panel in ("panel-checks", "panel-data", "panel-label"):
        assert f'id="{panel}"' in review
    # One button for the machine work, and it is in the checks panel rather than beside a step.
    assert review.count('id="run-checks"') == 1
    assert 'id="facet-ticks"' in review[review.index('id="panel-label"') :]


def test_the_guide_says_what_to_do_and_nothing_about_wiring() -> None:
    """§ *The page* -- written for the person labelling. No route name, no file path, no sentence
    about how the page is wired: that belongs on the page whose job is explaining the flow."""
    for said in WIRING:
        assert said not in GUIDE, f"the guide explains the wiring: {said!r}"
    assert "What a sample is" in GUIDE
    assert "What makes a label right" in GUIDE
    assert "No call is an answer" in GUIDE
    assert "What you tick, and when" in GUIDE
    assert "What gets a sample refused" in GUIDE
    assert 'id="guide-facets"' in GUIDE


def test_the_guide_and_the_statistics_open_over_the_sample() -> None:
    """A panel the reviewer opens, not a card they pass through: a reviewer who needs the guide
    needs it in the middle of a sample, and the statistics are what say which cells are short."""
    assert 'id="sheet-guide" hidden' in PAGE
    assert 'id="stats"' in GUIDE
    assert 'id="open-guide"' in PAGE[PAGE.index("<header") : PAGE.index("</header>")]


def test_the_strip_and_the_store_are_in_the_bar_that_does_not_scroll() -> None:
    """The numbers read sideways while the reviewer works, and *which database* beside them: a
    reviewer needs to know where a record lands before they write four hundred of them."""
    header = PAGE[PAGE.index('<header class="top">') : PAGE.index("</header>")]
    assert '<div class="strip" id="strip">' in header
    assert 'id="store"' in header
    for named in ("open-import", "open-list", "open-guide"):
        assert f'id="{named}"' in header


def test_a_sample_can_be_pasted_into_the_pane_that_holds_the_sample() -> None:
    """**Where a person looks to put a sample in is the thing called *the sample*.**

    Behind a button in a sheet somewhere else, a paste box is one nobody finds. So it lives in the
    left pane, and the two acts are there with it: one that needs no database at all, and one that
    adds to the queue.
    """
    pane = PAGE[PAGE.index('id="pane-sample"') : PAGE.index('id="pane-review"')]
    assert 'id="paste-open"' in pane
    assert 'id="paste-text"' in pane
    assert 'id="paste-now"' in pane
    assert 'id="paste-queue"' in pane


def test_a_corpus_still_arrives_as_a_file() -> None:
    """The other way in, and the one a sheet is right for: a file is not a thing you paste."""
    sheet = PAGE[PAGE.index('id="sheet-import"') : PAGE.index('id="sheet-list"')]
    assert 'id="file"' in sheet
    assert 'id="paste-text"' not in sheet


def test_every_element_the_script_reaches_for_is_on_the_page() -> None:
    """A handler attached to an element that is not there is a control that does nothing.

    Nothing else catches it: `document.getElementById` answers `null` rather than raising, so a
    renamed id is a dead button and a silent page — and a DOM stub that invents an element for
    every id asked of it would pass every behavioural check against exactly that page.
    """
    wanted = set(re.findall(r'\$\("([a-z0-9-]+)"\)', APP))
    declared = set(re.findall(r'id="([a-z0-9-]+)"', PAGE))

    assert not wanted - declared, (
        f"app.js reaches for ids the page does not declare: {wanted - declared}"
    )


def test_each_check_names_its_model_and_the_cell_it_answers_in() -> None:
    """Three columns: which check, which model answers it, and what it said.

    The middle one is the whole point. A model picked further down the page is a picker nobody
    finds, and a run that stops on *tick a verifier first* with no tick box in sight is a dead end.

    The answer cells are reached with a built-up id, which the sweep above cannot see -- that
    regex reads literal `$("...")` calls. So the declaration is read here instead, and a row
    renamed without a cell to write in fails by name.
    """
    rows = re.findall(r'\{ step: (\d+), what: "([^"]+)", said: "([^"]+)" \}', APP)
    assert [what for _, what, _ in rows] == ["Personal data", "Label"]

    panel = PAGE[PAGE.index('id="panel-checks"') : PAGE.index('id="panel-data"')]
    assert panel.count("<th>") == 3
    for _, _, said in rows:
        assert f'id="{said}"' in panel
    # And each picker is in that panel, once: a second copy anywhere else is a second control for
    # the same choice, and the reviewer cannot tell which one the run reads.
    for picker in ("verifier-ticks", "jury-ticks", "sft-ticks"):
        assert f'id="{picker}"' in panel
        assert PAGE.count(f'id="{picker}"') == 1


def test_a_domain_can_be_added_beside_the_domains() -> None:
    """The box that adds a domain sits with the list it adds to, inside the panel that holds the
    facets -- a control for one facet, filed under another, is one nobody connects to it."""
    label = PAGE[
        PAGE.index('id="panel-label"') : PAGE.index('<footer class="actions">')
    ]
    assert 'id="domain-ticks"' in label
    assert 'id="domain-new"' in label
    assert 'id="domain-add"' in label
    # `domain` is drawn on its own, so it must not also be drawn into the list of the rest.
    assert label.index('id="domain-ticks"') < label.index('id="facet-ticks"')


def test_the_list_is_pick_one_or_tick_many() -> None:
    """Clicking a row opens it; ticking rows walks just those. Both, because they answer different
    questions — *this one* and *this group*."""
    listing = PAGE[PAGE.index('id="sheet-list"') : PAGE.index("<script")]
    assert 'id="list-rows"' in listing
    assert 'id="list-walk"' in listing


# Two model names this deployment serves. Named here rather than left to `config/model`, which is
# the developer's own directory and holds whatever they wrote after cloning: a check on what the
# models route answers cannot be read off a list that differs per machine.
PAGE_MODELS = ("a-juror", "a-verifier")


@pytest.fixture
def attached_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_endpoints: None
) -> Iterator[TestClient]:
    """The app over a database and a model directory of this test's own, reached as a deployment
    reaches them.

    `no_endpoints` is named rather than left to run on its own: it sets `DATAFORCE_DATABASE_URL`
    to `off`, and it has to do that before this sets a DSN.
    """
    monkeypatch.setenv(
        "DATAFORCE_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'store.sqlite3'}"
    )
    served = tmp_path / "model"
    served.mkdir()
    for name in PAGE_MODELS:
        (served / f"{name}.json").write_text(
            json.dumps({"model": name, "base_url": f"http://{name}.invalid/v1"}),
            encoding="utf-8",
        )
    monkeypatch.setenv("DATAFORCE_MODEL_DIR", str(served))
    engine = db.open_engine()
    assert engine is not None
    create_tables(engine)

    yield TestClient(create_app())

    Base.metadata.drop_all(engine)


def test_the_page_reads_what_the_routes_actually_answer(
    attached_client: TestClient, tmp_path: Path
) -> None:
    """The one seam nothing else holds: field names written in Python and read in JavaScript.

    Every other check hands the page answers this file made up, which proves it reads *those* -- so
    a field renamed on one side and not the other passes all of them. This one imports a file
    through the real route, asks the real queue for a sample, stores two records through the real
    route, asks the real statistics, and hands the page exactly what came back. A renamed field
    shows up as a strip that cannot count and a matrix with no axes.

    Two samples and not one, ticked with different facets, because a grid of a single cell would
    not show a row and a column being read in the right order.
    """
    arrived = build_review()
    line = json.dumps(
        {
            "messages": arrived["messages"],
            "tools": arrived["tools"],
            # The number the customer gave, carried into the call that was labelled. A label with
            # nothing personal in it cannot show whether the label is redacted at all.
            "label": [{"name": "OpenTicket", "arguments": {"ma_khach": POSTED_PHONE}}],
        },
        ensure_ascii=False,
    )
    imported = attached_client.post(f"{BASE}/queue/import", content=line.encode())
    assert imported.status_code == 200, imported.text
    assert imported.json()["imported"] == 1

    queued = attached_client.get(f"{BASE}/queue/next")
    assert queued.status_code == 200, queued.text

    # The shipping copy, from the route that makes one. Two halves the page reads by name -- the
    # record under `sample`, the text under `review_text` -- and a stub cannot catch either being
    # renamed, because a stub answers whatever shape the page was written against.
    scanned = build_review_text(queued.json()["sample"])
    at = scanned.index(POSTED_PHONE)
    redacted = attached_client.post(
        f"{BASE}/data-quality/personal-data/redact",
        json={
            **queued.json()["sample"],
            "detected": {
                "review_text": scanned,
                "claims": [["PHONE", POSTED_PHONE]],
                "spans": [
                    {
                        "id": 1,
                        "start": at,
                        "end": at + len(POSTED_PHONE),
                        "personal_data_class": "PHONE",
                        "placeholder": "<PHONE_1>",
                        "reason": None,
                    }
                ],
            },
        },
    )
    assert redacted.status_code == 200, redacted.text
    # The turn and the label both, which is what the reach is for.
    assert POSTED_PHONE not in redacted.text
    assert "<PHONE_1>" in redacted.json()["review_text"].split("label: ")[1]

    # One domain the page declares and one it does not. The second is what an *added* domain
    # becomes once a sample carries it, and the page has to offer it back -- which is the whole of
    # why adding one outlasts the tab it was typed in.
    for number, (domain, trigger) in enumerate(
        [
            ("telesale", ["condition_met"]),
            ("insurance_claims", ["user_utterance", "every_turn"]),
        ]
    ):
        posted = build_review(id=f"page-{number}")
        posted["class"] = dict(posted["class"], domain=domain, call_trigger=trigger)
        assert attached_client.post(f"{BASE}/records", json=posted).status_code == 200

    answered = attached_client.get(f"{BASE}/records/stats")
    assert answered.status_code == 200
    # The models route too. It is the one whose answer the page had wrong -- a bare array read as
    # though it carried a `models` key -- and no stub can catch that, because a stub answers
    # whatever shape the page was written against.
    served = attached_client.get(f"{BASE}/models")
    assert served.status_code == 200
    assert served.json() == sorted(PAGE_MODELS)
    # And a line with no `id`, which is what a corpus really arrives as. The page has to get a
    # name from the service before it can do anything with one, and this is the answer it gets.
    anonymous = json.dumps(
        {
            "messages": [{"role": "user", "content": "chưa có tên"}],
            "tools": [],
            "label": [],
        },
        ensure_ascii=False,
    )
    named = attached_client.post(
        f"{BASE}/samples/named",
        content=anonymous.encode(),
        headers={"content-type": "application/x-ndjson"},
    )
    assert named.status_code == 200, named.text
    assert named.json()["samples"][0]["id"]
    (tmp_path / "stats.json").write_text(answered.text, encoding="utf-8")
    (tmp_path / "queued.json").write_text(queued.text, encoding="utf-8")
    (tmp_path / "models.json").write_text(served.text, encoding="utf-8")
    (tmp_path / "named.json").write_text(named.text, encoding="utf-8")
    (tmp_path / "anonymous.json").write_text(anonymous, encoding="utf-8")
    (tmp_path / "redacted.json").write_text(redacted.text, encoding="utf-8")

    run_node(str(READING), str(tmp_path))
