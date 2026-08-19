"""The `tool_decision` profile: tool selection over Vietnamese call-centre text.

Composes with the `text` modality. The answer is a set of tool names drawn from the
record's own catalog, and the empty set -- 35.4% of this corpus -- is a first-class
answer rather than a missing one.
"""

from __future__ import annotations

from dataforce.profiles.tool_decision.adapter import (
    PROVENANCE_KEY,
    adapt,
    answer_space_for,
    catalog_fingerprint,
    catalog_names,
    catalog_of,
)
from dataforce.profiles.tool_decision.answers import ANSWER_SCHEMA, consensus, delta
from dataforce.profiles.tool_decision.catalog import Catalog, Gap, Tool
from dataforce.profiles.tool_decision.checks import validity_checks
from dataforce.profiles.tool_decision.export import export
from dataforce.profiles.tool_decision.profile import TOOL_DECISION, ToolDecisionProfile
from dataforce.profiles.tool_decision.source import SourceContract

__all__ = [
    "ANSWER_SCHEMA",
    "PROVENANCE_KEY",
    "Catalog",
    "Gap",
    "SourceContract",
    "TOOL_DECISION",
    "Tool",
    "ToolDecisionProfile",
    "adapt",
    "answer_space_for",
    "catalog_fingerprint",
    "catalog_names",
    "catalog_of",
    "consensus",
    "delta",
    "export",
    "validity_checks",
]
