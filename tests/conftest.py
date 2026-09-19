"""What every test may assume: events land on stdout, and nothing reaches the network."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from dataforce.edge.database import DEFAULT_STORE_FILE, NO_STORE
from dataforce.edge.events import install_structured_events

# Where the suite is run from, which is where an unset DSN would put its file.
CHECKOUT = Path.cwd()


@pytest.fixture(autouse=True)
def no_database_in_the_checkout(request: pytest.FixtureRequest) -> Iterator[None]:
    """No test may leave the default SQLite file in the working directory.

    `no_endpoints` sets the variable to `off` so nothing resolves the default in the first place.
    This is the second line: if that ever slips, or a new code path reaches a real database some
    other way, the test that did it fails **by name** rather than a file quietly appearing in
    somebody's checkout and being noticed a week later. The file is removed as well as reported,
    so one slip does not then poison every test after it.

    Checked before as well as after, because *left behind by this test* and *was already there*
    are different findings and only the first names a culprit. A file already sitting in the
    checkout -- from a server somebody ran, or an earlier suite -- is cleared without failing
    anything, so the blame lands on the test that actually reaches a database and not on whichever
    one happened to run next.
    """
    left = CHECKOUT / DEFAULT_STORE_FILE
    left.unlink(missing_ok=True)

    yield

    if left.exists():
        left.unlink()
        pytest.fail(
            f"{request.node.nodeid} left {DEFAULT_STORE_FILE} in the checkout: it reached a real "
            "database. Declare a DSN of this test's own, or leave the store off."
        )


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

    `DATAFORCE_DATABASE_URL` is the one that is *set* rather than cleared, and set to `off`: unset
    means the default SQLite file in the working directory, so clearing it would point every test
    that does not declare its own DSN at one shared file in the checkout -- and the store suite
    drops every table it made. `off` is the same *no store* state these tests were always written
    against. `DATAFORCE_TEST_DATABASE_URL` is left alone: it names a throwaway server and is read
    on purpose.
    """
    monkeypatch.setenv("DATAFORCE_DATABASE_URL", NO_STORE)
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
