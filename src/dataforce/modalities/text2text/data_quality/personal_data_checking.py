"""LOGIC · two layers over one review text, and the typed placeholders they earn.

Layer one is `agent_toolkit`'s four rule scans — pure functions over text, so they are called from
here rather than through a port, and the order they are declared in is what resolves an overlap:
the first class to claim a span wins it. Layer two is a model, and is the abstract method below.

A span carries no turn any more, so every offset is into one string: the review text this builds
from the sample's turns and its label together. Building it here rather than taking it is what
keeps the offsets and the string that they index the same module's work.

**Open: where the rewritten text lands.** `Redaction` is gone from `schema.py`, so a scan reports
spans and placeholders and has no field holding the text with the values replaced -- while
`decision` still distinguishes `redacted` from `reported`. `replaced` is declared because the
rewrite is still the job; which field carries it is not decided.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence, str
from typing import Any

from .schema import PersonalDataScan, VerifierModelConfig


class PersonalDataChecking(ABC):
    def __init__(self, config: VerifierModelConfig) -> None:
        self.config = config

    async def scan(self, samples: Sequence[str]) -> PersonalDataScan:
        pass
