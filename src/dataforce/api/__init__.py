"""The published surface. Every caller enters here, the CLI included.

Two layers below this one do the work: the engine computes and opens no file, and
`declared/` turns the committed policy into what the engine accepts. This package is
what sequences them and what persists anything -- so a web handler, a notebook or
another codebase uses exactly what `dataforce` uses, rather than a second path kept
in step by hand.

    engine = api.open_engine(
        modality="text", profile="tool_decision",
        config_root=Path("config"), params=Path("params.yaml"),
    )
    records = list(api.build_records(engine, raw_items))   # no filesystem at all

The surface is small because it grows one function per stage as the stage arrives.
`stage_outputs` is what sequences them and asserts each gate between them -- named for
what comes back, every artifact written, rather than for the command it implements:
`run` would have been a name shared with `dataforce run`, which says nothing about what
a caller gets. It lands with `load`, the first stage there was anything to sequence.
"""

from dataforce.api.artifacts import (
    GATE_FAILED_FILENAME,
    METRICS_FILENAME,
    RUN_MANIFEST_FILENAME,
    file_digest,
    profile_corpus,
    record_gates,
    require_upstream_ok,
    run_manifest,
)
from dataforce.api.engine import (
    Engine,
    build_records,
    open_engine,
    text_modality,
    tool_decision_profile,
)
from dataforce.api.run import STAGES, Stage, interim_directory, stage_outputs

__all__ = [
    "GATE_FAILED_FILENAME",
    "METRICS_FILENAME",
    "RUN_MANIFEST_FILENAME",
    "STAGES",
    "Engine",
    "Stage",
    "build_records",
    "file_digest",
    "interim_directory",
    "open_engine",
    "profile_corpus",
    "record_gates",
    "require_upstream_ok",
    "run_manifest",
    "stage_outputs",
    "text_modality",
    "tool_decision_profile",
]
