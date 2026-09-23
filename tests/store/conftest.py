"""The two databases one store suite runs against: a temporary file, and a server someone attached.

*One code path, two DSNs* is a claim the spec makes about SQLite and Postgres, and a suite that only
ever runs on one of them is not evidence for it. So every test here is written once and run twice:
under `make check` against a file in `tmp_path`, with no server and no network, and under
`make integration` against `DATAFORCE_TEST_DATABASE_URL`. The second half is deselected by
`-m "not integration"` rather than skipped, so the commit gate never reports it as passed.

**The server is a throwaway.** Teardown drops every table the metadata knows, on whichever target
answered, and then asserts the target is as it was found -- a leaked table on a shared server is
invisible to every test that measures a difference, which is all of them. That is also why the
variable may not name a database anybody wants to keep.

A Postgres DSN has to name the driver: `postgresql+psycopg://...`, because the bare
`postgresql://` spelling resolves to psycopg2, which this repository does not install.

`store_engine` creates no table. Phase 0's tests are about what `create_tables` does, so each calls
it itself and the fixture does not answer that question on their behalf.
"""

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, inspect

from dataforce.edge.database import db
from dataforce.tables import Base
from tests.conftest import attach

TEST_DSN_VARIABLE = "DATAFORCE_TEST_DATABASE_URL"


@pytest.fixture(
    params=[
        pytest.param("file", id="sqlite-file"),
        pytest.param("server", id="postgres", marks=pytest.mark.integration),
    ]
)
def store_url(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> str:
    """A DSN nothing else is using: a file of this test's own, or the declared server."""
    if request.param == "file":
        return (
            f"sqlite+pysqlite:///{tmp_path_factory.mktemp('store') / 'store.sqlite3'}"
        )
    declared = os.environ.get(TEST_DSN_VARIABLE, "").strip()
    if not declared:
        pytest.skip(
            f"{TEST_DSN_VARIABLE} is unset, so the server half of this suite has nothing to reach"
        )
    return declared


@pytest.fixture
def store_engine(
    store_url: str, monkeypatch: pytest.MonkeyPatch, no_endpoints: None
) -> Iterator[Engine]:
    """An engine on that DSN, reached the way the edge reaches one, with no table made yet.

    `no_endpoints` is named rather than left to run on its own: it clears
    a database of its own, and it has to do that before this names the server's.
    """
    attach(monkeypatch, store_url)
    engine = db.open_engine()
    found = set(inspect(engine).get_table_names())

    yield engine

    Base.metadata.drop_all(engine)
    assert set(inspect(engine).get_table_names()) == found, (
        "the suite left a table behind, and every test here measures a difference"
    )
