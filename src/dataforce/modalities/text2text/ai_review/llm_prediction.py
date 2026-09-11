"""logic · N independent LLMs answer the sample's own task.

Independence is the whole point: the signal this service is built on is *models disagreeing*, so
nothing here shows one juror another's answer, and a juror that failed is absent rather than
counted as agreement.

One config or several is the same panel of a different size. `jurors` is that one rule -- it is not
a task's answer, so it has a body here rather than a socket -- and every method below reads the
panel through it, so a deployment that declares one model and one that declares five reach the same
code. What else has a body here is the arithmetic over the answers: a strict majority does not
change with the question being asked, and neither does refusing a judge an answer nobody gave.

*Whether two answers are the same* does change with it, and nothing here can know: what an answer
is made of is the task's, so `normalize_prediction` is a socket and not a default. A task whose
answers can be matched needs no judge; the judge is for one whose answers can only be compared as
meaning.
"""

from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

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
        self, sample: Mapping[str, Any], language: str
    ) -> Sequence[LLMReviewerVote]:
        """One vote per juror that answered, each asked once from the sample alone.

        A juror that failed is absent from the sequence -- never a vote, never an empty label. The
        label is not among the arguments: a juror is asked the sample's own question, and a model
        shown a label answers about the label. The record arrives whole and the task reads what
        its prompt needs out of it, because which keys a sample carries is the task's to know.
        """
        pass

    @abstractmethod
    async def judge_prediction(self, pred_texts: Sequence[str]) -> str | None:
        """What one model, shown those answers and nothing else, says the panel's answer is.

        The socket a task answers only where its answers cannot be matched: `None` is a task that
        needs no judge, and a tie then stands as no answer. Whether what comes back is an answer a
        juror actually gave is settled by `llm_judge_consensus`, not here.
        """
        pass

    @abstractmethod
    def normalize_prediction(self, pred_text: str) -> str:
        """One answer as the text two of them are compared by.

        The arithmetic below counts over this and never over the answers as written, and what an
        answer is made of is the task's to say: nothing at this layer knows whether two answers
        that differ are two answers or one spelled twice.
        """
        pass

    async def verdict(
        self, sample: Mapping[str, Any], label: str, language: str
    ) -> LLMReviewerVerdict:
        """What the panel said: the votes, how many agree with the label, and its one answer.

        `predict` is called once and every number here is read off what it returned, never off the
        panel that was asked: a juror that failed is absent, so a panel of three that answered
        twice agrees out of two. Every juror failing is a verdict with no votes, `0.0` and `None`.
        Agreement is compared here and never asked of a model.
        """
        votes = tuple(await self.predict(sample, language))
        pred_texts = [vote.label for vote in votes]
        wanted = self.normalize_prediction(label)
        agreed = [one for one in pred_texts if self.normalize_prediction(one) == wanted]
        consensus = self.exact_match_consensus(pred_texts)
        if consensus is None:
            consensus = await self.llm_judge_consensus(pred_texts)
        return LLMReviewerVerdict(
            votes=votes,
            label_agreement=len(agreed) / len(pred_texts) if pred_texts else 0.0,
            consensus=consensus,
        )

    def exact_match_consensus(self, pred_texts: Sequence[str]) -> str | None:
        """The answer strictly more than half of them gave, as the juror wrote it. Else `None`.

        A strict majority and never a mode: two of three is an answer, two of
        four is none, and the most-given of five given twice is none. Counted over
        `normalize_prediction`, so two answers that say the same thing count as one, and returned
        as written, because that is what a juror said.
        """
        if not pred_texts:
            return None
        written, given = Counter(
            self.normalize_prediction(one) for one in pred_texts
        ).most_common(1)[0]
        if given * 2 <= len(pred_texts):
            return None
        return next(
            one for one in pred_texts if self.normalize_prediction(one) == written
        )

    async def llm_judge_consensus(self, pred_texts: Sequence[str]) -> str | None:
        """The answer a judge picked out of these, and only ever one a juror actually wrote.

        Asked only where the exact match found nothing, and nothing answered is nobody asked. What
        comes back is matched against the answers the same way they were matched to each other and
        returned as the juror wrote it, so a judge that rewrote the answer it picked resolves to
        that juror's answer and one that invented an answer resolves to nothing.
        """
        if not pred_texts:
            return None
        resp_text = await self.judge_prediction(pred_texts)
        if resp_text is None:
            return None
        picked = self.normalize_prediction(resp_text)
        return next(
            (one for one in pred_texts if self.normalize_prediction(one) == picked),
            None,
        )
