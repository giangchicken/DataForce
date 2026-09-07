"""logic · the full logic behind each data-quality endpoint.

`personal_data_scan` takes the config for the model layer two asks and builds its own checker.
`duplicate_report` and `abnormal_report` take a sample and nothing else: neither declares a shape
to return, so neither has a model to ask, and a config they ignore would be one a caller has to
supply for nothing.
"""

from collections.abc import Mapping
from typing import Any

from dataforce.modalities.text2text.data_quality import PersonalDataScan
from dataforce.modalities.text2text.data_quality.schema import VerifierModelConfig
from dataforce.profile.tool_decision import ToolDecisionPersonalChecking


async def personal_data_scan(
    config: VerifierModelConfig, sample: Mapping[str, Any]
) -> PersonalDataScan:
    """What one sample says about a person, and the text with it replaced."""
    return await ToolDecisionPersonalChecking(config).scan(sample)


async def duplicate_report(sample: Mapping[str, Any]) -> None:
    """None, by declaration. Nothing says what a duplicate report is."""
    return None


async def abnormal_report(sample: Mapping[str, Any]) -> None:
    """None, by declaration. Nothing says what a common check reports."""
    return None
