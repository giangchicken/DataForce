"""What every test may assume: the package is importable and nothing reaches the network."""

import pytest


@pytest.fixture(autouse=True)
def no_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test composes a real endpoint. A part that needs one is exercised with a stub."""
    for named in (
        "EMBED_MODEL",
        "VERIFY_MODEL",
        "JURY_MODELS",
        "SFT_MODEL",
        "LABEL_STUDIO_URL",
        "LABEL_STUDIO_API_KEY",
    ):
        monkeypatch.delenv(named, raising=False)
