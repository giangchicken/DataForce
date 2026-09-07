"""LOGIC · one personal-data scan, declared here and answered by the task.

`scan` is the socket. Layer one's rule scans, layer two's model pass, the placeholders and the
offsets are one answer and not four, because what a sample is scanned *as* differs by task: a
tool-calling sample is its turns and the catalog of tools it was offered, and an argument value in
a call is exactly where personal data sits. So this declares the call and the shape it returns, and
`profile/<task>/data_quality.py` is where it gets a body.

A sample arrives whole for that reason -- the scan has to reach the parts the task reads.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from .schema import PersonalDataScan, VerifierModelConfig


class PersonalDataChecking(ABC):
    def __init__(self, config: VerifierModelConfig) -> None:
        self.config = config

    @abstractmethod
    async def scan(self, sample: Mapping[str, Any]) -> PersonalDataScan:
        """What one sample says about a person, and the text with it replaced.

        Every offset on a returned span indexes `review_text`, which the scan builds and nothing
        afterwards may reorder or reflow.
        """
        pass
