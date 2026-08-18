"""Every error DataForce raises, so a caller can catch ours without catching bugs."""

__all__ = ["ConfigError", "ConformanceError", "DataForceError"]


class DataForceError(Exception):
    """Base class for every error raised by dataforce."""


class ConfigError(DataForceError):
    """A run is configured in a way that cannot be honoured.

    An unregistered name, or a profile whose declared modality is not the one the
    run asked for. Always a hard stop before any stage runs: coercing either would
    produce a dataset whose provenance says something untrue.
    """


class ConformanceError(DataForceError):
    """A profile does not satisfy the conformance suite, and so cannot be selected.

    Raised at registration rather than at the jury stage, which is the difference
    between a failing test and a hundred-million-token run that means nothing.
    """
