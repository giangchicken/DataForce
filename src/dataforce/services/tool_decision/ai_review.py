"""logic · the full logic behind the ai-review endpoint: both reviewers over one sample.

Each function takes the config for the model it asks and builds its own reviewer. The panel and the
finetuned reviewer are asked separately and neither is folded into the other -- one carries reasons
and no confidence, the other a confidence and no reason. A config that is `None` is a reviewer the
deployment did not declare, and answers `None`, which is not a reviewer that disagreed. A config
that is *not* `None` for the finetuned reviewer is refused while § *Open* stands, so the only
answer it gives today is that one.

The language is declared beside the sample rather than read out of it, and is typed
here as text: the two the scans know are the boundary's own restriction, and this is a prompt slot
that nothing can `KeyError` on.
"""

import json
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
)


async def tool_decision_llm_predict(
    config: LLMModelConfig | Sequence[LLMModelConfig] | None,
    sample: Mapping[str, Any],
    language: str,
) -> LLMReviewerVerdict | None:
    """What the panel said. None where no model was declared.

    One config is a panel of one and several are a panel of several; `LLMPrediction` reads either
    through `jurors`, so nothing here counts models.

    The sample goes over whole and only the label is unpacked -- as JSON and not as a Python
    string, because it is a tool-call array and the panel matches the calls in one answer against
    the calls in another, so `str()` of a list would hand it a spelling no model would ever
    write.
    """
    if config is None:
        return None
    return await ToolDecisionLLMPrediction(config).verdict(
        sample, json.dumps(sample.get("label"), ensure_ascii=False), language
    )


async def tool_decision_sft_predict(
    config: SFTModelConfig | None, sample: Mapping[str, Any], language: str
) -> SFTReviewerVerdict | None:
    """What the finetuned reviewer said. None where no model was declared.

    Nothing else comes back today: a request that ticks one is refused, because where its
    confidence comes from is undecided (spec § *Open*).
    """
    if config is None:
        return None
    return await ToolDecisionSFTPrediction(config).predict(sample, language)
