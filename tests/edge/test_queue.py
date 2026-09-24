"""The queue routes: a file of raw samples in, one sample at a time out, and the row leaving it.

**Three writes or none** is the claim these are mostly about. A queue row marked done against a
record that was never written is the one failure a corpus cannot detect later -- the sample is
simply never offered to anybody again, and nothing in either table says it was lost. So the refused
record and the unknown key are tested as hard as the write that succeeds.
"""

import json
import uuid
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from dataforce.edge.database import DEFAULT_STORE_FILE, Database, db
from dataforce.edge.main import create_app
from dataforce.profile.tool_decision.sample_building import (
    PREVIEW_CHARACTERS,
    create_tables,
)
from dataforce.profile.tool_decision.schema import (
    QueueState,
    ToolDecisionQueuedSample,
    ToolDecisionRecord,
    ToolDecisionSample,
)
from dataforce.tables import Base
from tests.conftest import attach
from tests.edge.test_endpoints import BASE, build_review

ASKED = {"role": "user", "content": "cho tôi xem hóa đơn tháng này"}
THANKED = {"role": "user", "content": "cảm ơn nhé"}


def write_lines(*samples: Any) -> bytes:
    """A .jsonl file's bytes, which is what the page posts: one JSON value per line."""
    return "\n".join(json.dumps(one, ensure_ascii=False) for one in samples).encode()


@pytest.fixture
def labelling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_endpoints: None
) -> Iterator[TestClient]:
    """The app over a database of this test's own.

    No model directory, unlike `tests/edge/test_endpoints.py`'s client: not one route here reaches
    a model, so a fixture that wrote one would be describing a dependency these routes do not have.
    """
    attach(monkeypatch, f"sqlite+pysqlite:///{tmp_path / 'store.sqlite3'}")
    engine = db.open_engine()
    create_tables(engine)

    yield TestClient(create_app())

    Base.metadata.drop_all(engine)


@pytest.fixture
def unreachable(monkeypatch: pytest.MonkeyPatch, no_endpoints: None) -> TestClient:
    """The app over a database that is named and cannot be reached, which is the state left.

    A deployment that names nothing writes to a file of its own, so *no database at all* is not
    reachable any more -- what is, is a name behind a typo or a firewall, and that is refused
    rather than quietly replaced with a second place to write.
    """
    attach(monkeypatch, "postgresql+psycopg://user:pw@nosuchhost.invalid/db")
    return TestClient(create_app(), raise_server_exceptions=False)


def import_two(labelling: TestClient) -> Mapping[str, Any]:
    """Two samples imported, as the answer the route gave."""
    resp = labelling.post(
        f"{BASE}/queue/import",
        content=write_lines({"messages": [ASKED]}, {"messages": [THANKED]}),
        headers={"content-type": "application/x-ndjson"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_a_file_of_lines_becomes_rows_waiting_to_be_labelled(
    labelling: TestClient,
) -> None:
    """§ *Raw data in* -- one sample per line, every line a row."""
    assert import_two(labelling) == {
        "read": 2,
        "imported": 2,
        "already_held": 0,
        "unreadable": [],
    }
    assert labelling.get(f"{BASE}/queue/next").json()["waiting"] == 2


def test_importing_the_same_file_twice_imports_nothing_the_second_time(
    labelling: TestClient,
) -> None:
    """The key is the line's own content, which is the whole of what makes an import re-runnable
    after it failed half way."""
    import_two(labelling)

    assert import_two(labelling) == {
        "read": 2,
        "imported": 0,
        "already_held": 2,
        "unreadable": [],
    }
    assert labelling.get(f"{BASE}/queue/next").json()["waiting"] == 2


def test_the_same_sample_twice_in_one_file_is_one_row(labelling: TestClient) -> None:
    """The same rule within a file as across two: the key is the content, so the second is held."""
    resp = labelling.post(
        f"{BASE}/queue/import",
        content=write_lines({"messages": [ASKED]}, {"messages": [ASKED]}),
    )

    assert resp.json() == {
        "read": 2,
        "imported": 1,
        "already_held": 1,
        "unreadable": [],
    }


def test_an_unreadable_line_is_named_by_number_and_the_rest_import(
    labelling: TestClient,
) -> None:
    """A corpus assembled by hand has a bad line in it more often than not. Refusing the file
    wholesale makes the reviewer find it with no help at all."""
    resp = labelling.post(
        f"{BASE}/queue/import",
        content=b'{"messages": []}\nnot json at all\n["a list is not a sample"]\n{"messages": [{}]}\n',
    )

    assert resp.json() == {
        "read": 4,
        "imported": 2,
        "already_held": 0,
        # Line 2 is not JSON; line 3 is JSON that is not an object.
        "unreadable": [2, 3],
    }


def test_a_blank_line_is_not_a_line(labelling: TestClient) -> None:
    """A trailing newline is how every file ends, and reporting it as a fault is a fault."""
    resp = labelling.post(f"{BASE}/queue/import", content=b'{"messages": []}\n\n   \n')

    assert resp.json()["read"] == 1
    assert resp.json()["unreadable"] == []


def test_a_file_in_the_wrong_encoding_names_the_file_and_not_a_line(
    labelling: TestClient,
) -> None:
    """There are no readable lines at all, so sending the reviewer to fix line 1 is a lie."""
    resp = labelling.post(f"{BASE}/queue/import", content=b"\xff\xfe{")

    assert resp.status_code == 422
    assert "UTF-8" in resp.json()["detail"]


def test_an_imported_sample_is_named_by_its_key_where_the_line_had_no_name(
    labelling: TestClient,
) -> None:
    """Every route downstream reads a sample by name, so an anonymous corpus is unlabellable."""
    import_two(labelling)

    answered = labelling.get(f"{BASE}/queue/next").json()
    assert answered["sample"]["id"] == answered["key"]


def test_a_name_the_line_carried_is_kept(labelling: TestClient) -> None:
    """Only the missing name is filled in. A corpus that names its own samples keeps its names,
    because that name is how its owner finds the row again."""
    labelling.post(
        f"{BASE}/queue/import", content=write_lines({"id": "KH-1", "messages": [ASKED]})
    )

    assert labelling.get(f"{BASE}/queue/next").json()["sample"]["id"] == "KH-1"


def test_a_corpus_is_walked_in_the_order_its_file_was_written(
    labelling: TestClient,
) -> None:
    """A curated file is curated in an order, and that is the order it is handed back in.

    Every row of one import carries the same `imported_time`, written in one breath, so ordering by
    it leaves the tie to the key -- a hash of the content, which is to say an order nobody chose.
    Three lines and not two, because two in the wrong order is a coin coming up tails.
    """
    said = ["một", "hai", "ba"]
    labelling.post(
        f"{BASE}/queue/import",
        content=write_lines(
            *({"messages": [{"role": "user", "content": one}]} for one in said)
        ),
    )

    walked = []
    for _ in said:
        answered = labelling.get(f"{BASE}/queue/next").json()
        walked.append(answered["sample"]["messages"][0]["content"])
        labelling.post(f"{BASE}/queue/{answered['key']}/skip")

    assert walked == said


def test_a_second_import_lands_behind_the_first(labelling: TestClient) -> None:
    """Counting on from what the table holds, rather than starting again at one and interleaving.

    Two lines then one, and the whole walk asserted: a single line in each import would collide at
    the same number and leave the order to the tie, which is the database's to break and not an
    answer this can measure.
    """
    turn = lambda said: {"messages": [{"role": "user", "content": said}]}  # noqa: E731
    labelling.post(
        f"{BASE}/queue/import", content=write_lines(turn("một"), turn("hai"))
    )
    labelling.post(f"{BASE}/queue/import", content=write_lines(turn("ba")))

    walked = []
    for _ in range(3):
        answered = labelling.get(f"{BASE}/queue/next").json()
        walked.append(answered["sample"]["messages"][0]["content"])
        labelling.post(f"{BASE}/queue/{answered['key']}/skip")

    assert walked == ["một", "hai", "ba"]


def test_an_empty_queue_answers_an_empty_sample_and_not_an_error(
    labelling: TestClient,
) -> None:
    """Nothing is wrong with being done."""
    resp = labelling.get(f"{BASE}/queue/next")

    assert resp.status_code == 200
    assert resp.json() == {
        "sample": None,
        "key": None,
        "waiting": 0,
        "done": 0,
        "skipped": 0,
    }


def test_a_skipped_row_stays_and_is_not_offered_again(labelling: TestClient) -> None:
    """§ *Raw data in* -- skipping is a state, not a deletion: a corpus can be asked what was
    passed over, and *not me, not now* is a fact about the sample worth keeping."""
    import_two(labelling)
    first = labelling.get(f"{BASE}/queue/next").json()

    after = labelling.post(f"{BASE}/queue/{first['key']}/skip").json()

    assert after["skipped"] == 1
    assert after["waiting"] == 1
    assert after["key"] != first["key"]
    session = db.open_session()
    assert session is not None
    with session:
        row = session.get(ToolDecisionQueuedSample, uuid.UUID(first["key"]))
        assert row is not None
        assert row.state == QueueState.SKIPPED


def test_skipping_a_row_nobody_holds_is_a_404(labelling: TestClient) -> None:
    """A key that names nothing is the caller's mistake, not an empty queue."""
    resp = labelling.post(f"{BASE}/queue/{uuid.uuid4()}/skip")

    assert resp.status_code == 404


def test_a_submitted_sample_leaves_the_queue_as_the_record_lands(
    labelling: TestClient,
) -> None:
    """§ *Raw data in* -- three writes or none."""
    import_two(labelling)
    key = labelling.get(f"{BASE}/queue/next").json()["key"]

    resp = labelling.post(
        f"{BASE}/records", params={"queue_key": key}, json=build_review()
    )

    assert resp.status_code == 200, resp.text
    after = labelling.get(f"{BASE}/queue/next").json()
    assert after["done"] == 1
    assert after["waiting"] == 1
    assert after["key"] != key


def test_deleting_a_stored_sample_leaves_the_queue_row_it_came_from(
    labelling: TestClient,
) -> None:
    """Requirement 54's cost, measured rather than asserted in prose.

    The queue row is keyed by the raw line's own content and says a line was imported, which stays
    true of a sample taken back out of the corpus -- so the sample is still in the list, still
    openable, and labelling it again writes it back. **What that means is that the delete does not
    reach the un-redacted copy the queue holds**, and a deletion demand is not finished by it.
    """
    import_two(labelling)
    key = labelling.get(f"{BASE}/queue/next").json()["key"]
    stored = labelling.post(
        f"{BASE}/records", params={"queue_key": key}, json=build_review()
    ).json()["id"]

    resp = labelling.request("DELETE", f"{BASE}/records", json={"keys": [stored]})

    assert resp.status_code == 204, resp.text
    listed = labelling.get(f"{BASE}/queue").json()
    assert listed["done"] == 1
    assert [row["state"] for row in listed["samples"] if row["key"] == key] == ["done"]
    assert labelling.get(f"{BASE}/queue/{key}").status_code == 200


def test_a_refused_record_leaves_its_row_waiting(labelling: TestClient) -> None:
    """The failure a corpus cannot detect later: a row marked done whose record was never written
    is a sample nobody is ever shown again, and neither table says so."""
    import_two(labelling)
    key = labelling.get(f"{BASE}/queue/next").json()["key"]

    resp = labelling.post(
        f"{BASE}/records",
        params={"queue_key": key},
        json=build_review(personal_data=None),
    )

    assert resp.status_code == 422
    after = labelling.get(f"{BASE}/queue/next").json()
    assert after["done"] == 0
    assert after["waiting"] == 2
    assert after["key"] == key


def test_a_write_that_fails_after_the_mark_leaves_the_row_waiting(
    labelling: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The claim *three writes or none* is only worth anything on this path.

    The refused record never reaches the mark, and the unknown key never reaches the write, so
    neither of those proves a transaction -- only a write that fails *after* the row was marked
    does. The row is marked, then the two tables refuse, and what has to be true afterwards is that
    the sample is still waiting for somebody.
    """

    def refuse(*taken: Any, **named: Any) -> None:
        raise RuntimeError("the disk went away")

    import_two(labelling)
    key = labelling.get(f"{BASE}/queue/next").json()["key"]
    monkeypatch.setattr(
        "dataforce.edge.routers.text2text.tool_decision.merge_tool_decision_db", refuse
    )

    with pytest.raises(RuntimeError):
        labelling.post(
            f"{BASE}/records", params={"queue_key": key}, json=build_review()
        )

    after = labelling.get(f"{BASE}/queue/next").json()
    assert after["done"] == 0
    assert after["waiting"] == 2
    assert after["key"] == key


def test_a_record_against_a_key_nobody_holds_writes_nothing(
    labelling: TestClient,
) -> None:
    """Three writes or none, from the other side: the two tables stay empty too."""
    resp = labelling.post(
        f"{BASE}/records", params={"queue_key": str(uuid.uuid4())}, json=build_review()
    )

    assert resp.status_code == 404
    session = db.open_session()
    assert session is not None
    with session:
        assert session.query(ToolDecisionRecord).count() == 0
        assert session.query(ToolDecisionSample).count() == 0


def test_a_record_posted_with_no_queue_key_still_lands(labelling: TestClient) -> None:
    """The queue is a way to reach a sample, never a condition on storing one: a record assembled
    from a sample nobody imported is still a record."""
    resp = labelling.post(f"{BASE}/records", json=build_review())

    assert resp.status_code == 200, resp.text


def test_the_list_shows_every_sample_with_its_state(labelling: TestClient) -> None:
    """The list is what a reviewer picks from, and *what has already been done* is half of what
    they are looking for -- a list of only the waiting ones cannot answer whether a sample was
    skipped or labelled by somebody else."""
    import_two(labelling)
    first = labelling.get(f"{BASE}/queue/next").json()
    labelling.post(f"{BASE}/queue/{first['key']}/skip")

    listed = labelling.get(f"{BASE}/queue").json()

    assert [one["state"] for one in listed["samples"]] == ["skipped", "waiting"]
    assert [one["walk_position"] for one in listed["samples"]] == [1, 2]
    assert listed["samples"][0]["preview"] == ASKED["content"]
    assert listed == {**listed, "waiting": 1, "skipped": 1, "done": 0}


def test_a_listed_row_carries_a_preview_and_not_the_conversation(
    labelling: TestClient,
) -> None:
    """A list of three hundred rows carrying three hundred transcripts is a response nobody should
    send. The cap is the route's, so no page has to decide it."""
    long_said = "x" * 900
    labelling.post(
        f"{BASE}/queue/import",
        content=write_lines({"messages": [{"role": "user", "content": long_said}]}),
    )

    listed = labelling.get(f"{BASE}/queue").json()

    assert len(listed["samples"][0]["preview"]) == PREVIEW_CHARACTERS
    assert "messages" not in listed["samples"][0]


def test_a_sample_with_no_turns_is_still_listed(labelling: TestClient) -> None:
    """Empty rather than hidden: a sample nothing was said in is one worth seeing in the list."""
    labelling.post(f"{BASE}/queue/import", content=write_lines({"messages": []}))

    assert labelling.get(f"{BASE}/queue").json()["samples"][0]["preview"] == ""


def test_the_list_is_paged_and_the_counts_are_of_the_whole_queue(
    labelling: TestClient,
) -> None:
    """A page is an artefact of asking; *how much is left* is not."""
    turn = lambda said: {"messages": [{"role": "user", "content": said}]}  # noqa: E731
    labelling.post(
        f"{BASE}/queue/import", content=write_lines(turn("a"), turn("b"), turn("c"))
    )

    page = labelling.get(f"{BASE}/queue", params={"limit": 2, "offset": 1}).json()

    assert [one["preview"] for one in page["samples"]] == ["b", "c"]
    assert page["waiting"] == 3


@pytest.mark.parametrize("limit", [0, -5], ids=["nought", "negative"])
def test_a_limit_below_one_is_clamped_to_one_row(
    labelling: TestClient, limit: int
) -> None:
    """A limit of nought would answer a page of nothing over a queue that has samples in it, which
    reads as an empty queue. Clamped, so the answer is always the smallest useful page."""
    import_two(labelling)

    answered = labelling.get(f"{BASE}/queue", params={"limit": limit}).json()

    assert len(answered["samples"]) == 1
    assert answered["waiting"] == 2


def test_a_limit_past_the_cap_answers_the_cap(labelling: TestClient) -> None:
    """A corpus is as large as somebody's file, and one request asking for all of it is one
    response nobody can render. Asked for a billion, the route answers what it holds."""
    import_two(labelling)

    answered = labelling.get(f"{BASE}/queue", params={"limit": 10**9})

    assert answered.status_code == 200
    assert len(answered.json()["samples"]) == 2


def test_one_sample_can_be_picked_out_of_the_list_by_key(
    labelling: TestClient,
) -> None:
    """Clicking a row opens that sample, whatever state it is in: picking a row already labelled is
    asking to look at it again, and a second record under the same key replaces the first."""
    import_two(labelling)
    listed = labelling.get(f"{BASE}/queue").json()["samples"]
    labelling.post(f"{BASE}/queue/{listed[1]['key']}/skip")

    answered = labelling.get(f"{BASE}/queue/{listed[1]['key']}")

    assert answered.status_code == 200
    assert answered.json()["key"] == listed[1]["key"]
    assert answered.json()["sample"]["messages"][0] == THANKED


def test_picking_a_key_nobody_holds_is_a_404(labelling: TestClient) -> None:
    """`next` and `import` are the route's own names and are declared before the one that takes a
    key, so neither is ever read as one."""
    assert labelling.get(f"{BASE}/queue/{uuid.uuid4()}").status_code == 404


def test_the_store_says_which_database_and_never_the_dsn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_endpoints: None
) -> None:
    """This route is reachable by anyone who can open the page, and a DSN carries a password.

    Postgres rather than the SQLite the other tests use, because SQLite is the one dialect whose
    DSN has no password in it to leak.
    """
    attach(
        monkeypatch,
        "postgresql+psycopg://alice:s3cret-do-not-leak@db.internal:5432/corpus",
    )
    client = TestClient(create_app())

    said = client.get(f"{BASE}/store").json()["describes"]

    assert "s3cret-do-not-leak" not in said
    assert "alice" not in said
    assert "corpus" in said and "db.internal" in said


def test_the_store_names_the_default_where_a_deployment_named_nothing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, no_endpoints: None
) -> None:
    """Unlike every route that keeps something, *which database* always has an answer -- and it is
    the answer the page puts in its own header."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(db, "database_url", Database().database_url)

    answered = TestClient(create_app()).get(f"{BASE}/store")

    assert answered.status_code == 200
    assert answered.json() == {"describes": DEFAULT_STORE_FILE}


@pytest.mark.parametrize(
    "call",
    [
        lambda client: client.post(f"{BASE}/queue/import", content=b"{}"),
        lambda client: client.get(f"{BASE}/queue/next"),
        lambda client: client.get(f"{BASE}/queue"),
        lambda client: client.get(f"{BASE}/queue/{uuid.uuid4()}"),
        lambda client: client.post(f"{BASE}/queue/{uuid.uuid4()}/skip"),
    ],
    ids=["import", "next", "list", "one", "skip"],
)
def test_the_queue_refuses_a_database_it_cannot_reach_in_the_service_s_own_words(
    unreachable: TestClient, call: Any
) -> None:
    """Every one of these names the database rather than answering with a stack trace, and the
    URL's password reaches neither the screen nor the statement that would carry it."""
    resp = call(unreachable)

    assert resp.status_code == 503
    said = resp.json()["detail"]
    assert "nosuchhost.invalid" in said
    assert "pw" not in said
    assert "[SQL:" not in resp.text


# ------------------------------------------------------------------ naming what was pasted in


def name_lines(client: TestClient, *samples: Any) -> Mapping[str, Any]:
    """The same bytes a paste sends, answered with each line named."""
    resp = client.post(
        f"{BASE}/samples/named",
        content=write_lines(*samples),
        headers={"content-type": "application/x-ndjson"},
    )
    assert resp.status_code == 200, resp.text
    read: Mapping[str, Any] = resp.json()
    return read


def test_a_pasted_sample_is_given_the_name_an_import_would_have_given_it(
    labelling: TestClient,
) -> None:
    """**The two ways in name one sample the same.**

    A raw line carries `{messages, tools, label}` and no `id`, so something has to name it before
    a record can be stored under one. If pasting named it differently from importing, the same
    sample would sit in the corpus twice under two names and nothing would say so -- so this
    imports a line, pastes the same line, and asserts one name.
    """
    line = {"messages": [ASKED], "tools": [], "label": []}
    labelling.post(
        f"{BASE}/queue/import",
        content=write_lines(line),
        headers={"content-type": "application/x-ndjson"},
    )
    queued = labelling.get(f"{BASE}/queue/next").json()

    named = name_lines(labelling, line)

    assert named["read"] == 1
    assert named["samples"][0]["id"] == queued["sample"]["id"]
    assert named["samples"][0]["messages"] == [ASKED]


def test_a_pasted_sample_that_named_itself_keeps_its_name(
    unreachable: TestClient,
) -> None:
    """What a corpus calls its own rows is not this service's to overwrite. The key is still the
    content's, so a re-paste lands on the row it landed on last time either way."""
    named = name_lines(unreachable, {"id": "theirs-4", "messages": [THANKED]})

    assert named["samples"][0]["id"] == "theirs-4"


def test_naming_a_sample_never_reaches_the_database(unreachable: TestClient) -> None:
    """**The one sample path that touches no store**, proven against one that cannot be reached:
    a route that went near it would refuse, and a paste that needed a database to get a name would
    take the pasting path away from anyone whose database is down."""
    named = name_lines(unreachable, {"messages": [ASKED]})

    assert uuid.UUID(named["samples"][0]["id"])


def test_a_line_that_will_not_read_is_named_by_its_number_and_the_rest_are_answered(
    unreachable: TestClient,
) -> None:
    """One bad line in a paste of three is not a reason to refuse the other two, and *which line*
    is the only thing a person can act on."""
    resp = unreachable.post(
        f"{BASE}/samples/named",
        content=b'{"messages": []}\n[1, 2]\n{"messages": [{"role": "user"}]}',
        headers={"content-type": "application/x-ndjson"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["read"] == 3
    assert resp.json()["unreadable"] == [2]
    assert len(resp.json()["samples"]) == 2


def test_naming_refuses_bytes_that_are_not_utf8_without_blaming_a_line(
    unreachable: TestClient,
) -> None:
    """A paste in the wrong encoding has no readable lines at all, so naming one would send the
    person to go and fix a line that is not the problem."""
    resp = unreachable.post(
        f"{BASE}/samples/named",
        content="số điện thoại".encode("utf-16"),
        headers={"content-type": "application/x-ndjson"},
    )

    assert resp.status_code == 422
    assert "UTF-8" in resp.json()["detail"]
    assert "line" not in resp.json()["detail"]


# --------------------------------------------------- a raw line, on the routes that never name it

# A sample exactly as a corpus holds one: no `id`, tools written flat rather than wrapped in
# `{type, function}`, and a label that is a list of tool names. Nothing writes an `id` into a
# corpus line, so this is the shape every route has to survive.
RAW_LINE: Mapping[str, Any] = {
    "messages": [
        {"role": "system", "content": "determine which tool(s) to call next"},
        {"role": "user", "content": "email của anh là nam123@vd.vn"},
    ],
    "tools": [
        {
            "name": "VerifyEmail_15d",
            "description": "kiểm tra tính hợp lệ của một địa chỉ email",
            "parameters": {
                "type": "object",
                "properties": {"email": {"type": "string", "description": "email"}},
                "required": ["email"],
            },
        }
    ],
    "label": ["VerifyEmail_15d"],
}


@pytest.mark.parametrize(
    "path, extra",
    [
        ("/data-quality/duplicate", {}),
        ("/data-quality/abnormal", {}),
        (
            "/data-quality/personal-data/redact",
            {"detected": {"review_text": "", "claims": [], "spans": []}},
        ),
    ],
    ids=["duplicate", "abnormal", "redact"],
)
def test_a_line_with_no_name_is_read_by_the_routes_that_never_read_a_name(
    unreachable: TestClient, path: str, extra: Mapping[str, Any]
) -> None:
    """**A route may not demand a field it never uses.**

    One place in this service reads a sample's name -- the key a record is stored under. These
    read the text and nothing else, so a raw corpus line was being refused for a field that would
    have gone straight back out unread, and the reviewer was shown a validation dump with their
    own conversation echoed inside it.

    The two model routes are the same claim and are not here: they would need a served model, and
    what is under test is whether the body is *read*, not what a model says about it.
    """
    resp = unreachable.post(f"{BASE}{path}", json=dict(RAW_LINE, **extra))

    assert resp.status_code == 200, resp.text


def test_the_scan_reads_a_line_with_no_name(unreachable: TestClient) -> None:
    """The route the reviewer actually hits first, on the shape a corpus actually holds.

    Asserted by what it does *not* say: with no model directory the scan refuses for the model,
    which is a refusal that only happens once the body has been read.
    """
    resp = unreachable.post(
        f"{BASE}/data-quality/personal-data",
        json=dict(RAW_LINE, language="vi", verifier_model="nobody-serves-this"),
    )

    assert resp.status_code == 422
    assert isinstance(resp.json()["detail"], str)
    assert "not served here" in resp.json()["detail"]


def test_a_record_with_no_name_is_refused_in_a_sentence(labelling: TestClient) -> None:
    """The one route where the name is load-bearing says so, and says where to get one.

    Not as a validation list: that answer carries the whole sample back inside it, and *which
    field* is lost in the echo -- which is exactly how this went unnoticed.
    """
    unnamed = build_review()
    del unnamed["id"]

    resp = labelling.post(f"{BASE}/records", json=unnamed)

    assert resp.status_code == 422
    assert isinstance(resp.json()["detail"], str)
    assert "/samples/named" in resp.json()["detail"]
    assert labelling.get(f"{BASE}/records/stats").json()["sample_totals"] == {
        "tool_decision_record": 0,
        "tool_decision_dataset": 0,
    }
