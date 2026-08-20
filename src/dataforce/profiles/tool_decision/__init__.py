"""The `tool_decision` profile: tool selection over Vietnamese call-centre text.

Composes with the `text` modality. The answer is a set of tool names drawn from the
record's own catalog, and the empty set -- 35.4% of this corpus -- is a first-class
answer rather than a missing one.
"""

from __future__ import annotations

from dataforce.profiles.tool_decision.adapter import (
    PROVENANCE_KEY,
    answer_space,
    build_record,
    catalog_fingerprint,
    catalog_names,
    read_catalog,
)
from dataforce.profiles.tool_decision.answers import (
    ANSWER_SCHEMA,
    answer_distance,
    vote_consensus,
)
from dataforce.profiles.tool_decision.catalog import Catalog, Gap, Tool
from dataforce.profiles.tool_decision.checks import validity_checks
from dataforce.profiles.tool_decision.export import training_example
from dataforce.profiles.tool_decision.profile import TOOL_DECISION, ToolDecisionProfile
from dataforce.profiles.tool_decision.source import SourceContract, read_source_contract

__all__ = [
    "ANSWER_SCHEMA",
    "PROVENANCE_KEY",
    "TOOL_DECISION",
    "Catalog",
    "Gap",
    "SourceContract",
    "Tool",
    "ToolDecisionProfile",
    "answer_distance",
    "answer_space",
    "build_record",
    "catalog_fingerprint",
    "catalog_names",
    "read_catalog",
    "read_source_contract",
    "training_example",
    "validity_checks",
    "vote_consensus",
]
