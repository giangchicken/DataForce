"""LOGIC · the data-quality checks over a tool-calling sample.

Personal data is the one with a body to write. What this task scans is the conversation *and* the
catalog of tools it was offered: an argument value in a tool call is where a phone number actually
sits, so a scan that reads only the turns misses the half that matters.
"""

from collections.abc import Mapping
from typing import Any

from dataforce.modalities.text2text.data_quality import (
    CommonAbnormalChecking,
    DuplicateDataChecking,
    PersonalDataChecking,
    PersonalDataScan,
)

from .utils import openai_tool_format_to_text


class ToolDecisionPersonalChecking(PersonalDataChecking):
    """Personal data in a tool-calling sample: the turns and the catalog together."""

    async def scan(self, sample: Mapping[str, Any]) -> PersonalDataScan:
        """The two layers over this sample's review text, and the placeholders they earn.

        The rule scans are called in one declared order and the first class to claim a value keeps
        it; the model pass then sets the precision, and only a confirmed value is replaced.
        """
        raise NotImplementedError

    def review_text(self, sample: Mapping[str, Any]) -> str:
        """The one string every span's offsets index: the turns, the catalog, and the label."""
        raise NotImplementedError

    def tool_catalog(self, sample: Mapping[str, Any]) -> str:
        """The tools this sample was offered, as the text a reviewer and a juror both read."""
        return openai_tool_format_to_text(sample.get("tools") or ())


class ToolDecisionDuplicateChecking(DuplicateDataChecking):
    """Two samples that offer the same tools and say the same thing."""


class ToolDecisionAbnormalChecking(CommonAbnormalChecking):
    """The checks that need no opinion. Undecided, like the base -- returns nothing yet."""
