"""LOGIC · the ai-review part for this profile: which tool the models say the sample should call."""

from dataforce.modalities.text2text.ai_review import LLMPrediction, SFTPrediction


class ToolDecisionLLMPrediction(LLMPrediction):
    """N jurors answering the sample's own question: which tool, with which arguments."""


class ToolDecisionSFTPrediction(SFTPrediction):
    """The finetuned reviewer's own answer to the same question."""
