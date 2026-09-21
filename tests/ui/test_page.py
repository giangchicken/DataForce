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
from dataforce.tables import Base
from tests.edge.test_endpoints import BASE, POSTED_PHONE, build_review

CHECKS = Path(__file__).parent / "page.js"
READING = Path(__file__).parent / "reading.js"
LOADING = Path(__file__).parent / "loading.js"
UI = Path(__file__).parents[2] / "src" / "dataforce" / "ui"
PAGE = (UI / "index.html").read_text(encoding="utf-8")
STYLE = (UI / "style.css").read_text(encoding="utf-8")

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

# Every script the page loads, as one text: `app.js` alone today. The sweeps below read what `ui/`
# holds rather than one name, so a module cut out of it is swept the day it exists rather than the
# day somebody remembers to add it here.
SCRIPTS = "\n".join(
    path.read_text(encoding="utf-8") for path in sorted(UI.glob("*.js"))
)
GUIDE = PAGE[PAGE.index('id="sheet-guide"') : PAGE.index('id="sheet-import"')]


def run_node(*taken: str) -> None:
    """One node script, skipped loudly where node is absent rather than passing quietly.

    `--experimental-vm-modules` is what lets `dom.js` link the page: `index.html` loads `app.js`
    as a module, and the only thing in node that compiles the module goal inside a context is
    `vm.SourceTextModule`, which is behind that flag.
    """
    node = shutil.which("node")
    if node is None:
        pytest.skip(
            "node is not installed, so the page's own checks have nothing to run in"
        )
    done = subprocess.run(
        [node, "--experimental-vm-modules", *taken],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, f"\n{done.stdout}\n{done.stderr}"


def test_the_harness_links_modules_and_a_broken_one_takes_the_run_down(
    tmp_path: Path,
) -> None:
    """`app.js` imports nothing yet, so loading it proves only that a module compiles.

    The rest of the loader is what the split will rest on, and it is held here rather than
    discovered halfway through it: a specifier resolved against the file that wrote it, one
    instance of a module two others import, and a module that throws while it is evaluated failing
    the run instead of leaving an empty page every check passes against.
    """
    run_node(str(LOADING), str(tmp_path))


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
    wanted = set(re.findall(r'\$\("([a-z0-9-]+)"\)', SCRIPTS))
    declared = set(re.findall(r'id="([a-z0-9-]+)"', PAGE))

    assert not wanted - declared, (
        f"ui/ reaches for ids the page does not declare: {wanted - declared}"
    )


def unremarked(source: str) -> str:
    """`source` with the comments taken out, so markup quoted in one is not read as markup.

    This repository quotes a tag in a comment freely, and a class named in an explanation is a
    class nobody asked to style. Only a comment that owns its whole line is taken, because `//`
    lives inside a string and inside a regex too.
    """
    source = re.sub(r"<!--.*?-->", " ", source, flags=re.S)
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    return re.sub(r"^[ \t]*//.*$", "", source, flags=re.M)


def classes_written(source: str) -> set[str]:
    """Every class name `source` writes, including the ones a template expression decides.

    `class="${out ? "out" : ""}"` is how half the states on this page are written, so a sweep that
    reads the attribute as a flat string sees no name at all and a renamed rule goes unnoticed.
    This walks the attribute instead: bare words outside `${...}`, string literals inside it.
    """
    source = unremarked(source)
    found: set[str] = set()

    def keep(held: str) -> None:
        found.update(
            word for word in held.split() if re.fullmatch(r"[A-Za-z][\w-]*", word)
        )

    def skip_literal(text: str, at: int) -> int:
        shut = text[at]
        at += 1
        while at < len(text) and text[at] != shut:
            at += 2 if text[at] == "\\" else 1
        return at + 1

    for opened in re.finditer(r'class="', source):
        at, depth, inside, word, quote = opened.end(), 0, 0, "", ""
        while at < len(source):
            here = source[at]
            if quote:
                if here == quote:
                    keep(word)
                    word, quote = "", ""
                else:
                    word += here
            elif depth:
                # Inside `${...}`: a name is only a class where the expression writes it as a
                # string in its own right. An identifier is the expression choosing between
                # them, and a string inside a call is that call's argument -- `offList("domain",
                # row) ? " gone" : ""` names one class, and `domain` is not it.
                if here in "\"'`":
                    if inside:
                        at = skip_literal(source, at)
                        continue
                    quote = here
                elif here in "([":
                    inside += 1
                elif here in ")]":
                    inside -= 1
                elif here == "{":
                    depth += 1
                elif here == "}":
                    depth -= 1
            elif source.startswith("${", at):
                keep(word)
                word, depth, at = "", 1, at + 1
            elif here == '"':
                keep(word)
                break
            else:
                word += here
            at += 1

    for held in re.findall(r"""className\s*=\s*["'`]([^"'`]*)""", source):
        keep(held)
    for held in re.findall(r"""classList\.\w+\(\s*["']([\w-]+)["']""", source):
        found.add(held)
    return found


def test_every_class_the_page_writes_has_a_rule() -> None:
    """A class with no rule is markup that claims a treatment `style.css` never gave it.

    `shown`, `editor`, `num` and the keep table's `value` cell were each written and never
    defined, so the row that says a span's offsets do not slice read as ordinary text. Nothing
    else catches it: an unknown class is not an error in a browser or in the stub, and the page
    renders whatever it is handed.

    Two limits, both stated rather than implied. The *name* is what is held to have a rule, which
    is as far as a sweep goes without a rendering engine: `#dataset-rows td.bad` defines `bad`
    here even where the cell carrying it is in another table. And a class whose name is data --
    `class="turn ${who}"`, `class="row ${row.state}"` -- is not a name this reads, because the
    names are in `held.js` rather than in the markup.
    """
    defined: set[str] = set()
    bare = re.sub(r"/\*.*?\*/", "", STYLE, flags=re.S)
    for selector in re.findall(r"([^{}]+)\{", bare):
        if selector.strip().startswith("@"):
            continue
        defined |= set(re.findall(r"\.([A-Za-z][\w-]*)", selector))

    written = classes_written(PAGE) | classes_written(SCRIPTS)

    assert not written - defined, (
        f"ui/ writes classes style.css does not define: {sorted(written - defined)}"
    )


# The four classes no sweep can read off the markup, because their names are values rather than
# text: a turn's `role` (`class="turn ${who}"`), a queue row's `state` (`class="row ${row.state}"`,
# whose names are `STATE_SAID`'s keys in `held.js`), and the kind a check's verdict is said in
# (`checks.js`'s state map). A fifth belongs here only with the same kind of answer beside it.
FROM_DATA = {"assistant", "busy", "done", "skipped"}


def test_every_rule_has_a_user() -> None:
    """A rule nobody writes is a treatment for a screen that does not exist.

    `h3.way` and `.mono` were both defined and never used -- `git log -S` finds no commit that
    used either, so they were written against a page that was never built. Nothing else catches
    it: dead CSS costs nothing at runtime and shows up in no output.
    """
    defined: set[str] = set()
    bare = re.sub(r"/\*.*?\*/", "", STYLE, flags=re.S)
    for selector in re.findall(r"([^{}]+)\{", bare):
        if selector.strip().startswith("@"):
            continue
        defined |= set(re.findall(r"\.([A-Za-z][\w-]*)", selector))

    written = classes_written(PAGE) | classes_written(SCRIPTS) | FROM_DATA

    assert not defined - written, (
        f"style.css defines classes nothing in ui/ writes: {sorted(defined - written)}"
    )


def test_no_module_calls_a_name_it_did_not_import() -> None:
    """A function that moved to another module and is still called by name is a dead button.

    Modules are strict mode, so reaching one is a `ReferenceError` at *call* time -- the page
    loads, every other check passes, and the control throws the first time somebody presses it.
    Nothing else here catches it: the behavioural checks drive the controls they were written for,
    and a control nobody drives is exactly the one a split leaves behind.
    """
    declared = re.compile(
        r"^(?:export )?(?:async )?(?:function|const|let|var|class) (\w+)", re.M
    )
    home: dict[str, str] = {}
    for path in sorted(UI.glob("*.js")):
        for name in declared.findall(path.read_text(encoding="utf-8")):
            home.setdefault(name, path.name)

    reached = []
    for path in sorted(UI.glob("*.js")):
        source = path.read_text(encoding="utf-8")
        brought = {
            name.strip()
            for head in re.findall(r'import \{([^}]*)\} from "[^"]+";', source)
            for name in head.replace("\n", " ").split(",")
            if name.strip()
        }
        mine = set(
            re.findall(
                r"^\s*(?:export )?(?:async )?(?:function|const|let|var) (\w+)",
                source,
                re.M,
            )
        )
        body = re.sub(r'import \{[^}]*\} from "[^"]+";', "", source)
        for name, wrote in home.items():
            if wrote == path.name or name in brought or name in mine:
                continue
            if re.search(rf"(?<![\w$.]){re.escape(name)}\s*\(", body):
                reached.append(f"{path.name} calls {name}(), which {wrote} declares")

    assert not reached, "\n".join(reached)


def test_each_check_names_the_cell_it_answers_in() -> None:
    """Two columns: which check, and what it said.

    They were three, and the middle one -- which model answers -- was the whole point: a picker
    further down the page is one nobody finds, and a run that stops on *tick a verifier first*
    with no tick box in sight is a dead end. `T20` kept that reason and outgrew the table, because
    a picker now travels with the button that spends it rather than with a row standing in for one.

    The answer cells are reached with a built-up id, which the sweep above cannot see -- that
    regex reads literal `$("...")` calls. So the declaration is read here instead, and a row
    renamed without a cell to write in fails by name.
    """
    rows = re.findall(r'\{ step: (\d+), what: "([^"]+)", said: "([^"]+)" \}', SCRIPTS)
    assert [what for _, what, _ in rows] == ["Personal data", "Label"]

    panel = PAGE[PAGE.index('id="panel-checks"') : PAGE.index('id="panel-data"')]
    assert panel.count("<th>") == 2
    # And each answer cell carries the state word's own class. `dom.js` mints an element on first
    # reach with no class at all, so no check driving the page can see what the markup says here:
    # a cell left spelled `said` would render unstyled from load until the first paint, and every
    # behavioural claim would still pass.
    for _, _, said in rows:
        assert f'id="{said}"' in panel
        assert re.search(rf'<td class="verdict" id="{said}">', panel), (
            f"{said} is the cell a check answers in, so it is a state word like the others"
        )
    # And nothing is spent from here: the button that runs a check and the picker it spends both
    # sit on the card that check fills -- `layout.md` § *The two acts, and where each one sits*.
    for moved in (
        "run-detect",
        "run-review",
        "verifier-ticks",
        "jury-ticks",
        "sft-ticks",
    ):
        assert f'id="{moved}"' not in panel, moved


def test_the_page_answers_no_question_about_where_a_value_stands() -> None:
    """A span is a value and a class. Offsets are answered, never typed.

    The containment rule -- *a span inside a longer span is dropped* -- was written twice, once in
    `find_and_number_spans` and once in this page's JavaScript, character for character. The
    pipeline spec paid for that in writing: *the cost of a reviewer being able to edit an offset
    at all*. This is what says the offset stayed gone, because nothing else would notice a second
    copy of the rule creeping back in beside a table of numbers.

    Reading a span is not holding a rule: the page still slices the review text to show what a
    span stands in for, which is what `read_span_values` does on the other side of the call.
    """
    assert "other.end - other.start" not in SCRIPTS
    for gone in ("span-table", "span-check", "span-add", "span-note", '"auto"'):
        assert gone not in SCRIPTS, gone
        assert gone not in PAGE, gone
    card = PAGE[PAGE.index('id="panel-data"') : PAGE.index('id="panel-label"')]
    assert card.count("<input") == 1
    assert 'id="value-new"' in card


def test_what_a_value_may_be_said_to_be_is_asked_for_and_not_declared_here() -> None:
    """The class picker is filled from the route that declares the scans.

    A list written into this page would offer a class no scan declares and put the rest in another
    order -- and the order is the one `<CLASS_N>` counts in, so a page with its own list would
    renumber what a reviewer was already reading.
    """
    assert "/data-quality/personal-data/classes" in SCRIPTS
    for named in ("EMAIL", "PHONE", "OTP", "NAME"):
        assert named not in PAGE, named
        assert named not in SCRIPTS, named


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

    # What the scan answers, from the route that numbers a value -- which takes no model, so the
    # spans a reviewer is shown here are the service's own and not three keys written out by hand.
    detected = attached_client.post(
        f"{BASE}/data-quality/personal-data/spans",
        json={**queued.json()["sample"], "claimed": [["PHONE", POSTED_PHONE]]},
    )
    assert detected.status_code == 200, detected.text
    assert detected.json()["spans"], (
        "the fixture claims a value the text does not carry"
    )

    # The shipping copy, from the route that makes one. Two halves the page reads by name -- the
    # record under `sample`, the text under `review_text` -- and a stub cannot catch either being
    # renamed, because a stub answers whatever shape the page was written against.
    redacted = attached_client.post(
        f"{BASE}/data-quality/personal-data/redact",
        json={**queued.json()["sample"], "detected": detected.json()},
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
    (tmp_path / "detected.json").write_text(detected.text, encoding="utf-8")

    run_node(str(READING), str(tmp_path))


def test_the_two_acts_sit_at_the_ends_of_the_card_they_fill() -> None:
    """Requirements 20 and 21: the scan fills card 1, the vote is spent on what card 1 produced.

    *Find personal data* heads the card because what it claims is the table under it. *Ask the
    reviewers* is at the foot, directly above the card it fills, so a reviewer who has just
    finished ticking does not go back to a band at the top of the pane to spend what they ticked.
    Each picker is in the same block as the button that spends it, and neither exists twice.
    """
    card = PAGE[PAGE.index('id="panel-data"') : PAGE.index('id="panel-label"')]
    for picker, button in (
        ("verifier-ticks", "run-detect"),
        ("jury-ticks", "run-review"),
        ("sft-ticks", "run-review"),
    ):
        assert PAGE.count(f'id="{picker}"') == 1, picker
        assert f'id="{picker}"' in card, picker
        assert f'id="{button}"' in card, button
    assert PAGE.count('id="run-detect"') == 1
    assert PAGE.count('id="run-review"') == 1
    assert card.index('id="run-detect"') < card.index('id="keep-table"')
    assert card.index('id="run-review"') > card.index('id="review-text"')
    # Disabled in the markup and not only once a script has run: the page is served before
    # `app.js` is fetched, and a live button in that window is a vote spent on nothing.
    assert re.search(r'<button id="run-review"[^>]*\bdisabled\b', card)
    # The two ids the split replaced, gone from the page and from every module in it.
    for gone in ("run-checks", "checks-verdict", "checks-note"):
        assert gone not in PAGE, gone
        assert gone not in SCRIPTS, gone


def test_the_panel_is_asked_with_the_redacted_record_and_nothing_else() -> None:
    """Requirement 20: a juror reads `<EMAIL_1>` and writes `<EMAIL_1>`.

    Read off the source because it is a claim about which object is sent, and the behavioural
    check beside it proves the placeholder arrives -- but a page that sent `held.sample` while a
    stub happened to answer the same shape would pass that and still hand a customer's number to
    a model. `held.shipped` is the route's own redacted record; nothing else may be posted there.
    """
    body = re.search(r'asking\(\s*6,\s*\{(.*?)\},\s*"/ai-review"\)', SCRIPTS, re.S)
    assert body, 'the panel is asked through one `asking(6, …, "/ai-review")`'
    assert "...handed" in body.group(1)
    assert "held." not in body.group(1), body.group(1)
    assert SCRIPTS.count('"/ai-review"') == 1
    assert re.search(r"review\(held\.shipped\.sample\)", SCRIPTS)


def test_card_two_leads_with_the_proposal_and_offers_three_acts() -> None:
    """Requirement 22: the thing worth confirming is the prediction, not what arrived.

    Each juror is handed the conversation and the catalog and *not* the label, so `consensus` is a
    prediction rather than an opinion about what arrived -- and what arrives is often a tool named
    and never called. The card that led with that and hid the panel's full call behind a button was
    optimised for the weaker of the two.
    """
    card = PAGE[PAGE.index('id="panel-label"') :]
    card = card[: card.index("</article>")]
    assert card.index('id="proposed-call"') < card.index('id="arrived-call"')
    for act in ("v-take", "v-keep", "v-write"):
        assert f'id="{act}"' in card, act
        assert PAGE.count(f'id="{act}"') == 1, act
    # None of the three is ticked in the markup either: which label ships is a thing a person says,
    # and a page that ticks one before it is read has answered for them.
    acts = card[
        card.index('class="choice"') : card.index(
            "</div>", card.index('class="choice"')
        )
    ]
    assert "checked" not in acts
    # What the three replaced, gone from the page and from every module in it.
    for gone in (
        "v-correct",
        "v-modify",
        "take-consensus",
        "consensus-line",
        "consensus-note",
    ):
        assert gone not in PAGE, gone
        assert gone not in SCRIPTS, gone
    # And the two ids that drew one label into one block, which is now two blocks.
    for gone in ('id="calls"', 'id="calls-which"'):
        assert gone not in PAGE, gone


def test_a_label_is_written_on_a_form_built_from_the_sample_s_catalog() -> None:
    """Requirement 24: the tool is picked from the tools that sample offers.

    It was a `<textarea>` of JSON with a button that said *Check it is JSON*. A reviewer who does
    not write software could not use it at all, and the one who could still had to retype a call
    the panel had already spelled out. Everything the form needs was on the page already --
    `tools` carries each tool's `parameters.properties`, its `description` and its `required`.

    *This turn needs no tool at all* is a box rather than an emptied field, because **no call is an
    answer** and an answer is a thing somebody gives.
    """
    card = PAGE[PAGE.index('id="panel-label"') :]
    card = card[: card.index("</article>")]
    for named in ("call-form", "call-add", "call-none"):
        assert f'id="{named}"' in card, named
        assert PAGE.count(f'id="{named}"') == 1, named
    assert re.search(r'<div id="call-form"[^>]*\bhidden\b', card), (
        "the form opens on *write it myself* and not before"
    )
    assert '<input type="checkbox" id="call-none">' in card
    # The four the form replaced, gone from the page and from every module in it.
    for gone in ("label-text", "label-check", "label-note", "label-editor"):
        assert gone not in PAGE, gone
        assert gone not in SCRIPTS, gone
    # And the one textarea left on the page is the paste box, which takes a sample and not a call.
    assert PAGE.count("<textarea") == 1
    assert (
        'id="paste-text"' in PAGE[PAGE.index("<textarea") : PAGE.index("</textarea>")]
    )


def test_nothing_in_the_page_reads_a_call_out_of_free_text() -> None:
    """Requirement 24, last line: the page builds a call and never parses one.

    Three modules read JSON, and each reads something that is JSON by declaration: `wire.js` a
    response body, `importing.js` a `.jsonl` line somebody pasted, and `conversation.js` a call's
    own `arguments` field -- which the store says is *an object or JSON text* in
    `read_call_arguments`, so reading both spellings is not a second definition of a call.

    `label.js` is the one that had to stop. It parsed the editor's text into a label and each
    juror's sentence into a call, and the second of those drew a juror that answered in prose as
    *no call* -- a different answer from the one it gave.
    """
    reads = {
        path.name
        for path in sorted(UI.glob("*.js"))
        if "JSON.parse" in path.read_text(encoding="utf-8")
    }
    assert reads == {"wire.js", "importing.js", "conversation.js"}, reads


def test_the_page_draws_the_panel_s_calls_and_parses_none() -> None:
    """Requirement 23 and Decision 9: a call is read by the service, drawn by the page.

    `consensus` is the text a juror wrote; `consensus_calls` is that text read as calls by
    `parse_text_to_tools`. The page draws the second and never reads the first, because a client
    that turned prose into a call would be a second definition of what a call is, in another
    language -- which is the whole reason `T19` added the field.
    """
    assert "consensus_calls" in SCRIPTS
    # The juror's own sentence is never read into a call at all -- it is drawn as the sentence it
    # is, which is what the disclosure it sits behind is called.
    assert "extract_json" not in SCRIPTS
    # `consensus` itself -- the juror's sentence -- is never reached for. Only `consensus_calls`,
    # which is the service's reading of it.
    assert not re.search(r"\.consensus\b(?!_calls)", SCRIPTS)
