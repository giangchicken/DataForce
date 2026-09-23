"""What every test may assume: events land on stdout, and nothing reaches the network."""

from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.engine import make_url

from dataforce.edge import database
from dataforce.edge.database import DEFAULT_STORE_FILE, db
from dataforce.edge.events import install_structured_events

# Where the suite is run from, which is where an unset DSN would put its file.
CHECKOUT = Path.cwd()


def attach(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    """Point the process-wide `Database` at one of this test's own."""
    monkeypatch.setattr(db, "database_url", make_url(url))


@pytest.fixture(autouse=True)
def a_database_of_this_test_s_own(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Every test writes to a file of its own, and none of them to the one in the checkout.

    There is no *no database* state to fall back on any more: a deployment that names nothing still
    writes somewhere, so a test that names nothing would write to the checkout's own file -- one
    shared corpus, carried between tests in whatever order they ran.

    The second half is the guard, and it is placed on the engine rather than on the file. Asking
    afterwards whether a file appeared cannot answer this: the file is already there, because
    somebody is running a service over it, and reading a database that already holds every table
    changes neither its size nor its time. The engine is where *reaching* one is decided, so the
    test that does it is named as it does it -- and nothing in the checkout is moved, renamed or
    removed to find that out. Deleting it is how the corpus behind a running service was lost.
    """
    attach(monkeypatch, f"sqlite+pysqlite:///{tmp_path / 'store.sqlite3'}")
    forbidden = str(CHECKOUT / DEFAULT_STORE_FILE)
    reached = database.create_engine

    def refuse_the_checkout(url: object, *read: object, **named: object) -> Engine:
        if forbidden in str(url):
            pytest.fail(
                f"{request.node.nodeid} reached {DEFAULT_STORE_FILE} in the checkout, which "
                "belongs to whoever is running a service over it. Declare a database of this "
                "test's own with `attach`."
            )
        return reached(url, *read, **named)

    monkeypatch.setattr(database, "create_engine", refuse_the_checkout)


@pytest.fixture(autouse=True)
def events_on_stdout() -> None:
    """The handler the edge installs, installed here too, so a test reads the real event.

    `H-6` is about what a deployment sees, so the formatting is not stubbed: what these tests
    assert on stdout is the same handler `create_app` adds.
    """
    install_structured_events()


@pytest.fixture(autouse=True)
def no_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test composes a real endpoint. A part that needs one is exercised with a stub.

    The three `LLM_*` names are `agent_toolkit`'s own: with no resolver registered, its
    `EnvConfigResolver` reads them, so a machine that exports `LLM_BASE_URL` is one unstubbed
    `resolve_config` away from a real call. The rest are this deployment's.

    `DATAFORCE_TEST_DATABASE_URL` is left alone: it names a throwaway server and is read on
    purpose, by the fixture that attaches one.
    """
    for named in (
        "LLM_MODEL",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "EMBED_MODEL",
        "VERIFY_MODEL",
        "JURY_MODELS",
        "SFT_MODEL",
        "LABEL_STUDIO_URL",
        "LABEL_STUDIO_API_KEY",
    ):
        monkeypatch.delenv(named, raising=False)
