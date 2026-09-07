"""logic · the finetuned reviewer's own answer, and its verdict on the label.

A second opinion and not a second juror. It carries a confidence and no reason, the panel carries
reasons and no confidence, and folding them into one vote would weigh one model's training set
against N zero-shot opinions without saying so. Two keys keep them weighable apart.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .schema import SFTModelConfig, SFTReviewerVerdict


class SFTPrediction(ABC):
    def __init__(self, config: SFTModelConfig) -> None:
        self.config = config

    @abstractmethod
    async def predict(self, turns: Sequence[str], label: str) -> SFTReviewerVerdict:
        pass

    def verdict(self, answered: SFTReviewerVerdict, label: str) -> bool:
        raise NotImplementedError
