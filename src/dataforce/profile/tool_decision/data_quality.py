"""LOGIC · the data-quality part for this profile: the checks over a tool-calling sample."""

from collections.abc import Mapping, Sequence
from typing import Any

from dataforce.modalities.text2text.data_quality import (
    CommonAbnormalChecking,
    DuplicateDataChecking,
    PersonalDataChecking,
)

from .utils import openai_tool_format_to_text


class ToolDecisionPersonalChecking(PersonalDataChecking):
    """Personal data in a tool-calling sample, over the tools and the turns together."""
    pass


class ToolDecisionDuplicateChecking(DuplicateDataChecking):
    """Two samples that offer the same tools and say the same thing."""


class ToolDecisionAbnormalChecking(CommonAbnormalChecking):
    """The checks that need no opinion. Undecided, like the base -- returns nothing yet."""
    pass
