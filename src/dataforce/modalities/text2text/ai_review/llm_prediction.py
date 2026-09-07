"""logic · N independent LLMs answer the sample's own task.

Independence is the whole point: the signal this service is built on is *models disagreeing*, so
nothing here shows one juror another's answer, and a juror that failed is absent rather than
counted as agreement.

One config or several is the same panel of a different size. `jurors` is that one rule -- it is not
a task's answer, so it has a body here rather than a socket -- and every method below reads the
panel through it, so a deployment that declares one model and one that declares five reach the same
code.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .schema import LLMModelConfig, LLMReviewerVerdict, LLMReviewerVote


class LLMPrediction(ABC):
    def __init__(self, config: LLMModelConfig | Sequence[LLMModelConfig]) -> None:
        self.config = config

    @property
    def jurors(self) -> tuple[LLMModelConfig, ...]:
        """The panel, whether one model was declared or several."""
        if isinstance(self.config, LLMModelConfig):
            return (self.config,)
        return tuple(self.config)

    @abstractmethod
    async def predict(
        self, turns: Sequence[str], label: str
    ) -> Sequence[LLMReviewerVote]:
        """One vote per juror that answered, each asked once from the sample alone.

        A juror that failed is absent from the sequence -- never a vote, never an empty label.
        """
        pass

    async def verdict(self, turns: Sequence[str], label: str) -> LLMReviewerVerdict:
        """What the panel said: the votes, how many agree with the label, and its one answer."""
        raise NotImplementedError

    def exact_match_consensus(self, answers: Sequence[str]) -> str | None:
        raise NotImplementedError

    def llm_judge_consensus(self, answers: Sequence[str]) -> str | None:
        raise NotImplementedError
