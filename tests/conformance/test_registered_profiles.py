"""Every profile a run could name, put through the suite. This is CI's copy.

Registration happens when a profile package is imported, so this test sees
whatever `dataforce.profiles` has registered -- which is what a run would see.
"""

from __future__ import annotations

import pytest

from dataforce.profiles import conformance, registry


def test_every_registered_profile_conforms() -> None:
    registered = registry.names()
    if not registered:
        pytest.skip(
            "no profile is registered yet; the first one lands with tool_decision"
        )
    for name in registered:
        report = conformance.run(registry.get(name))
        assert report.ok, f"{name}: {[f.detail for f in report.failures]}"
