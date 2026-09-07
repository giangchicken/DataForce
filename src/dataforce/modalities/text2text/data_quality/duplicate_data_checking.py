"""LOGIC · exact and near-duplicate groups, split by label agreement.

Two samples saying the same thing are two answers to one question, and which is right matters
differently depending on whether they agree: same content and same label is a sample to drop one
of, same content and a different label means one of them is wrong. So the report is two groups and
nothing is removed.

**Cost, stated:** the near pass is pairwise over the batch it is handed. One embedding call, then
n²/2 cosines. That is fine for a posted batch and is not how a corpus of twenty thousand should be
compared — the exit is an index, not a smaller batch.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .schema import DuplicateGroups, EmbedderModelConfig


class DuplicateDataChecking(ABC):
    def __init__(self, config: EmbedderModelConfig) -> None:
        self.config = config

    @abstractmethod
    async def embedding(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        pass

    async def duplicate_groups(self, samples: Sequence[str]) -> DuplicateGroups:
        pass
