"""LOGIC · the rule that picks the label, and the seam a deployment replaces it at.

`DecisionLogic` is the rule as a socket: everything a rule may read is on `Evidence`, so a
deployment's own rule is one subclass with one method and needs nothing else from this package.
`MajorityDecision` is the one this modality ships.

The default rule, in order:

1. **Anyone answered** — the majority verdict decides. Endorsed keeps the sample's label
   (`original`); otherwise a strict majority over the corrections replaces it (`corrected`); a
   correction nobody agreed on leaves the sample's label standing and says so (`unresolved`).
2. **Nobody answered** — the label stands as `unvalidated`, with what the reviewers said beside
   it on the sample.

**`unvalidated` does not promote a model's answer into `label`.** Training on labels a model wrote
is the failure this whole service exists to catch, so a status is the honest output and an
overwrite is not.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .schema import Annotation, Answer, Evidence, LabelDecision


class DecisionLogic(ABC):
    @abstractmethod
    def decide(self, evidence: Evidence) -> LabelDecision:
        """The label that ships, and how it was decided."""
        pass


class MajorityDecision(DecisionLogic):
    """The rule at the top of this module."""

    def decide(self, evidence: Evidence) -> LabelDecision:
        """The label that ships, by the rule at the top of this module."""
        pass

    def latest_per_person(
        self, annotations: Sequence[Annotation]
    ) -> tuple[Annotation, ...]:
        """The latest answer per person, in the order they first appear.

        Two rows from one annotator are a revision, not a second opinion. A person correcting
        themselves is legitimate; a self-pair scoring as a corroboration is not.
        """
        pass

    def strict_majority(self, values: Sequence[str]) -> str | None:
        """The value more than half of them gave, or None. A strict majority, never a mode.

        Used for the verdicts and, over canonical strings, for the corrections -- one rule, so a
        correction and a verdict cannot be decided by two different notions of *most*.
        """
        pass

    def pair_agreement(self, values: Sequence[str]) -> float:
        """The share of pairs that match, 0 to 1. Fewer than two scores 0.0, not 1.0."""
        pass

    def canonical_answer(self, answer: Answer) -> str:
        """One answer as the one string that means it, so two that mean the same compare as one."""
        pass
