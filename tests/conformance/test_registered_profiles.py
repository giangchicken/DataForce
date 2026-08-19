"""Every profile a run could name, put through the suite. This is CI's copy.

The composition root is what a run resolves through, so that is what this registers
from: a profile that only conforms when a test constructs it directly is not a
profile any run can select.
"""

from __future__ import annotations

from dataforce.cli import _register_implementations
from dataforce.modalities import registry as modality_registry
from dataforce.profiles import conformance, registry


def test_every_registered_profile_conforms() -> None:
    _register_implementations()
    registered = registry.names()

    assert registered, "the composition root registered no profile"
    for name in registered:
        report = conformance.run(registry.get(name))
        assert report.ok, f"{name}: {[f.detail for f in report.failures]}"


def test_every_profile_composes_with_a_registered_modality() -> None:
    """A profile declaring a modality nobody registered is a run that cannot start."""
    _register_implementations()

    for name in registry.names():
        declared = registry.get(name).modality
        assert modality_registry.get(declared).name == declared
