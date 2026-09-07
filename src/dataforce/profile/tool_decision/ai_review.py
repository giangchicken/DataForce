"""logic · which tool the two reviewers say this sample should call.

The prompt is built here, not in the modality: `tool_prediction.txt` asks for a tool call, and what
a juror is asked is the task's question. Each juror is handed the catalog, the conversation and
nothing else -- not the sample's label, because a model shown a label answers about the label.
"""

from collections.abc import Sequence

from dataforce.modalities.text2text.ai_review import (
    LLMPrediction,
    LLMReviewerVote,
    SFTPrediction,
    SFTReviewerVerdict,
)

from .utils import openai_tool_format_to_text


class ToolDecisionLLMPrediction(LLMPrediction):
    """N jurors answering the sample's own question: which tool, with which arguments."""

    async def predict(
        self, turns: Sequence[str], label: str
    ) -> Sequence[LLMReviewerVote]:
        """One vote per juror that answered, each asked once and shown no other juror's answer.

        `label` is compared against, never sent: the prompt returns `reason` and `label`, and
        `model_name` is set from the juror this asked.
        """
        raise NotImplementedError

    def rendered_prompt(self, turns: Sequence[str], tools: Sequence[object]) -> str:
        """`tool_prediction.txt` with its four slots filled, ready to send."""
        raise NotImplementedError

    def tool_catalog(self, tools: Sequence[object]) -> str:
        """The tools this sample was offered, as the text the prompt's catalog slot takes."""
        return openai_tool_format_to_text(tools)


class ToolDecisionSFTPrediction(SFTPrediction):
    """The finetuned reviewer's own answer to the same question."""

    async def predict(self, turns: Sequence[str], label: str) -> SFTReviewerVerdict:
        """Its own answer and how sure it is, from the same prompt the jurors read."""
        raise NotImplementedError
