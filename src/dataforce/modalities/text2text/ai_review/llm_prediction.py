"""LOGIC · N independent LLMs answer the sample's own task.

Independence is the whole point: the signal this service is built on is *models disagreeing*, so
nothing here shows one juror another's answer, and a juror that failed is absent rather than
counted as agreement.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .schema import LLMModelConfig, LLMReviewerVerdict, LLMReviewerVote


class LLMPrediction(ABC):
    def __init__(self, config: LLMModelConfig) -> None:
        self.config = config

    @abstractmethod
    async def predict(self, turns: Sequence[str], label: str) -> Sequence[LLMReviewerVote]:
        pass

    async def verdict(self, turns: Sequence[str], label: str) -> LLMReviewerVerdict:
        pass

    def exact_match_consensus(self, answers: Sequence[str]) -> str | None:
        pass

    def llm_judge_consensus(self, answers: Sequence[str]) -> str | None:
        pass
