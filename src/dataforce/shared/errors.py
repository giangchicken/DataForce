"""Every error DataForce raises, so a caller can catch ours without catching bugs."""

__all__ = ["ConfigError", "DataForceError", "InvariantError"]


class DataForceError(Exception):
    """Base class for every error raised by dataforce."""


class ConfigError(DataForceError):
    """A run is configured in a way that cannot be honoured.

    An unregistered name, or a profile whose declared modality is not the one the
    run asked for. Always a hard stop before any stage runs: coercing either would
    produce a dataset whose provenance says something untrue.
    """


class InvariantError(DataForceError):
    """Something the pipeline asserts about its own output does not hold.

    Raised where the pipeline can still notice, rather than reported downstream:
    `training_example` raises it when the exported example states a different
    answer from the one the record carries, which is invariant 4. The alternative
    is a release that trains on the wrong labels and says nothing.
    """
