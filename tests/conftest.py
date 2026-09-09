"""What every test may assume: events land on stdout, and nothing reaches the network."""

import pytest

from dataforce.edge.events import structured_events


@pytest.fixture(autouse=True)
def events_on_stdout() -> None:
    """The handler the edge installs, installed here too, so a test reads the real event.

    `H-6` is about what a deployment sees, so the formatting is not stubbed: what these tests
    assert on stdout is the same handler `create_app` adds.
    """
    structured_events()


@pytest.fixture(autouse=True)
def no_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test composes a real endpoint. A part that needs one is exercised with a stub.

    The three `LLM_*` names are `agent_toolkit`'s own: with no resolver registered, its
    `EnvConfigResolver` reads them, so a machine that exports `LLM_BASE_URL` is one unstubbed
    `resolve_config` away from a real call. The rest are this deployment's.
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
