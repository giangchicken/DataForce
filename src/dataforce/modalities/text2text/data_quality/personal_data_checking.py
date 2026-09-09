"""logic · one personal-data scan, declared here and answered by the task.

`detect` is the socket, and it is given `PersonalDataCheckingInput`. What has a body here is what
every task this modality serves shares: `PiiRuleDetector`, and the confirmation -- `PiiLlmConfirmer`
with `pii_llm_confirm` and the prompt they send. Which model confirms is the task's, and arrives as
the declaration a request carried.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

from agent_toolkit.file_utils import read_txt
from agent_toolkit.llm import complete, resolve_config
from agent_toolkit.llm.exceptions import LLMError
from agent_toolkit.logging import get_logger
from agent_toolkit.string_utils import extract_json_from_text, slot_filling
from pydantic import ValidationError

from dataforce.errors import ConfigError

from .schema import (
    PersonalDataCheckingConfig,
    PersonalDataCheckingInput,
    PersonalDataDetected,
    PersonalDataSpan,
    PiiLlmConfirmed,
    RuleScan,
    VerifierModelConfig,
)

PII_LLM_CONFIRM_PROMPT = Path(
    "config/prompts/modalities/text2text/data_quality/pii_llm_confirm.txt"
)

logger = get_logger(__name__)


class PiiRuleDetector:
    """The rule scans as one thing that detects. Their declared order settles an overlap."""

    def __init__(self, scans: tuple[tuple[str, RuleScan], ...]) -> None:
        self.scans = scans

    @property
    def classes(self) -> tuple[str, ...]:
        """The classes it detects, in claiming order -- the order `<CLASS_N>` numbers."""
        return tuple(personal_data_class for personal_data_class, _ in self.scans)

    def detect(self, text: str, language: str) -> dict[str, str]:
        """Which class claims each value, keyed by value. The first scan to claim one holds it.

        A value not in `text` verbatim is dropped: it can carry no offset, so nothing could
        replace it.
        """
        claimed: dict[str, str] = {}
        for personal_data_class, scan in self.scans:
            for value in scan(text, language):
                if value and value in text:
                    claimed.setdefault(value, personal_data_class)
        return claimed


class PiiLlmConfirmer:
    """One model asked which of the spans it is shown are real. It answers with those spans."""

    def __init__(self, verifier_config: VerifierModelConfig) -> None:
        """The model resolved from what the request declared, or `ConfigError` before any record."""
        try:
            self.model = resolve_config(
                model=verifier_config.model_name,
                api_key=verifier_config.api_key,
                base_url=verifier_config.base_url,
            )
        except LLMError as error:
            raise ConfigError(f"{verifier_config.model_name}: {error}") from error
        if not self.model.base_url:
            raise ConfigError(
                f"{verifier_config.model_name}: no base_url in its config file and none"
                " passed, so there is no endpoint to ask"
            )
        self.settings = verifier_config.settings

    async def confirm(
        self, prompt: str, spans: Sequence[PersonalDataSpan]
    ) -> tuple[PersonalDataSpan, ...]:
        """The spans the model confirmed, each carrying its reason. Never raises (Requirement 8).

        Only ever narrows: an id no span carries is discarded, a span answered twice keeps the
        first answer, and a span nothing came back about is not confirmed -- which is what a
        failed call and an answer of the wrong shape both come to, as one event on stdout.
        """
        failed: Exception
        try:
            resp = await complete(
                prompt,
                model=self.model.model,
                api_key=self.model.api_key,
                base_url=self.model.base_url,
                **self.settings,
            )
        # A refusal, a timeout, a hung-up socket: a provider's failures are its own to name.
        except Exception as error:
            failed = error
        else:
            try:
                answered = PiiLlmConfirmed.model_validate(
                    extract_json_from_text(resp)
                ).confirmed
            # Prose, or JSON that is not the shape asked for.
            except ValidationError as error:
                failed = error
            else:
                real: dict[int, str] = {}
                for one in answered:
                    if one.confirmed:
                        real.setdefault(one.id, one.reason)
                return tuple(
                    span.model_copy(update={"reason": real[span.id]})
                    for span in spans
                    if span.id in real
                )
        logger.warning(
            "pii_llm_confirm_failed",
            extra={
                "model": self.model.model,
                "error": f"{type(failed).__name__}: {failed}",
            },
        )
        return ()


class PersonalDataChecking(ABC):
    def __init__(self, config: PersonalDataCheckingConfig) -> None:
        self.config = config
        self.pii_llm_confirmer = PiiLlmConfirmer(config.verifier_model)

    def build_pii_llm_confirm_prompt(
        self,
        checking_input: PersonalDataCheckingInput,
        text: str,
        spans: Sequence[PersonalDataSpan],
    ) -> str:
        """`pii_llm_confirm.txt` with its three slots filled: the language, the text, the spans.

        `ConfigError` where the file is not there: `read_txt` answers a missing one with an empty
        string, and an empty prompt is a model asked nothing and answering anything.
        """
        template = read_txt(PII_LLM_CONFIRM_PROMPT)
        if not template.strip():
            raise ConfigError(
                f"no prompt at {PII_LLM_CONFIRM_PROMPT}: it is the deployment's file, on"
                " the same terms as config/model/"
            )

        def span_lines(text: str, spans: Sequence[PersonalDataSpan]) -> str:
            """The spans as a prompt carries them: one `id | CLASS | value` per line."""
            return "\n".join(
                f"{span.id} | {span.personal_data_class} | {text[span.start : span.end]}"
                for span in spans
            )

        return slot_filling(
            template,
            {
                "language": checking_input.language,
                "review_text": text,
                "spans": span_lines(text, spans),
            },
        )

    async def pii_llm_confirm(
        self,
        checking_input: PersonalDataCheckingInput,
        text: str,
        spans: Sequence[PersonalDataSpan],
    ) -> tuple[PersonalDataSpan, ...]:
        """Which of those spans are real, each carrying the reason it was confirmed for.

        Nothing detected is nobody asked: an empty list is one call and one bill for nothing.
        """
        if not spans:
            return ()
        prompt = self.build_pii_llm_confirm_prompt(checking_input, text, spans)
        return await self.pii_llm_confirmer.confirm(prompt, spans)

    @abstractmethod
    async def detect(
        self, checking_input: PersonalDataCheckingInput
    ) -> PersonalDataDetected:
        """What one sample says about a person: the text to read it in, and the spans in it.

        Every offset on a returned span indexes `review_text`, which this builds and nothing
        afterwards may reorder or reflow. Replacing is not here: a human ticks and edits these
        spans first, and what they hand back is what gets replaced.
        """
