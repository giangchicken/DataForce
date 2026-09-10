"""logic · the finetuned reviewer's own answer, and how sure it is.

A second opinion and not a second juror. It carries a confidence and no reason, the panel carries
reasons and no confidence, and folding them into one vote would weigh one model's training set
against N zero-shot opinions without saying so. Two keys keep them weighable apart.

Whether its answer agrees with the label is not asked here. Comparing two answers means knowing
what an answer is made of, and this layer serves every text2text task -- so that rule, like the
prompt, belongs to the task, and lands with the rest of this reviewer's half (spec § *Open*).
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .schema import SFTModelConfig, SFTReviewerVerdict


class SFTPrediction(ABC):
    def __init__(self, config: SFTModelConfig) -> None:
        self.config = config

    @abstractmethod
    async def predict(
        self, turns: Sequence[str], tools: Sequence[object], language: str
    ) -> SFTReviewerVerdict | None:
        """Its own answer and how sure it is, or `None` where it did not answer.

        `None` on the same terms as an absent juror: a reviewer that failed said nothing, and a
        label of `""` compared against the sample's is a disagreement nobody expressed. The label
        is not among the arguments -- it is asked the sample's own question, like a juror.
        """
        pass
