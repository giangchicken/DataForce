"""logic · the full logic behind the ai-review endpoint: both reviewers over one sample.

Each function takes the config for the model it asks and builds its own reviewer. The panel and the
finetuned reviewer are asked separately and neither is folded into the other -- one carries reasons
and no confidence, the other a confidence and no reason. A config that is `None` is a reviewer the
deployment did not declare, and answers `None`, which is not a reviewer that disagreed.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from dataforce.modalities.text2text.ai_review import (
    LLMReviewerVerdict,
    SFTReviewerVerdict,
)
from dataforce.modalities.text2text.ai_review.schema import (
    LLMModelConfig,
    SFTModelConfig,
)
from dataforce.profile.tool_decision import (
    ToolDecisionLLMPrediction,
    ToolDecisionSFTPrediction,
    conversation_turns,
)


async def tool_decision_llm_predict(
    config: LLMModelConfig | Sequence[LLMModelConfig] | None, sample: Mapping[str, Any]
) -> LLMReviewerVerdict | None:
    """What the panel said. None where no model was declared.

    One config is a panel of one and several are a panel of several; `LLMPrediction` reads either
    through `jurors`, so nothing here counts models.
    """
    if config is None:
        return None
    return await ToolDecisionLLMPrediction(config).verdict(
        conversation_turns(sample), str(sample.get("label", ""))
    )


async def tool_decision_sft_predict(
    config: SFTModelConfig | None, sample: Mapping[str, Any]
) -> SFTReviewerVerdict | None:
    """What the finetuned reviewer said. None where no model was declared."""
    if config is None:
        return None
    return await ToolDecisionSFTPrediction(config).predict(
        conversation_turns(sample), str(sample.get("label", ""))
    )
