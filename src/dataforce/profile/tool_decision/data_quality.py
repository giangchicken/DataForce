"""logic · the data-quality checks over a tool-calling sample.

Personal data is the one with a body to write, and it is two calls. `detect` is the frame of
reference every offset indexes, two detectors unioned, and the modality's confirmation over the
spans they earn. `replace_spans_with_placeholders` is the second, over the spans a human handed
back, and `decide_replacement_outcome` says how far it got. `replaced_node` is the third: the same
replacement over the record's own fields rather than over the review text, which is where the
record's `new_` keys come from. What this task reads is the turns
*and* the catalog, because an argument value in a tool call is where a phone number sits.
"""

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from agent_toolkit.file_utils import read_txt
from agent_toolkit.llm import complete, resolve_config
from agent_toolkit.llm.exceptions import LLMError
from agent_toolkit.logging import get_logger
from agent_toolkit.string_utils import extract_json_from_text, slot_filling

from dataforce.errors import ConfigError
from dataforce.modalities.text2text.data_quality import (
    CommonAbnormalChecking,
    DuplicateDataChecking,
    PersonalDataChecking,
    PersonalDataCheckingConfig,
    PersonalDataCheckingInput,
    PersonalDataDetected,
    PersonalDataSpan,
    PiiLlmDetected,
    PiiRuleDetector,
)
from dataforce.modalities.text2text.data_quality.schema import (
    PersonalDataReplacementOutcome,
    VerifierModelConfig,
)

from .utils import conversation_turns, openai_tool_format_to_text

# The deployment's, on the same terms as `config/model/`: read from the working directory and named
# for the method that sends it.
PII_LLM_DETECT_PROMPT = Path("config/prompts/profiles/tool_decision/pii_llm_detect.txt")
# A scan claims a value at a word boundary and a search for one knows none, so `09123456789012`
# would otherwise hold a phone number.
WORD = re.compile(r"\w")

logger = get_logger(__name__)


def find_and_number_spans(
    text: str, detected: Sequence[tuple[str, str]]
) -> tuple[PersonalDataSpan, ...]:
    """Every span those values carry in `text`: numbered, bounded, and the outermost kept.

    Three rules in one pass, all answering where a value stands in the frame of reference:
    `<CLASS_N>` per distinct value, so a value said twice stays co-referent; an occurrence with a
    word character against it is not one; a span inside a longer span is dropped. `id` is 1-based
    over what survives, so the ids a prompt shows have no holes.

    Every entry is one non-empty value that occurs in `text` -- `pii_detect` holds both.
    """
    found: list[PersonalDataSpan] = []
    counted: dict[str, int] = {}
    for personal_data_class, value in detected:
        counted[personal_data_class] = counted.get(personal_data_class, 0) + 1
        placeholder = f"<{personal_data_class}_{counted[personal_data_class]}>"
        start = text.find(value)
        while start >= 0:
            end = start + len(value)
            before = text[start - 1] if start else ""
            after = text[end] if end < len(text) else ""
            if not (WORD.match(before) or WORD.match(after)):
                found.append(
                    PersonalDataSpan(
                        id=0,
                        start=start,
                        end=end,
                        personal_data_class=personal_data_class,
                        placeholder=placeholder,
                    )
                )
            start = text.find(value, end)
    return tuple(
        span.model_copy(update={"id": numbered})
        for numbered, span in enumerate(
            (
                span
                for span in found
                if not any(
                    other.start <= span.start
                    and span.end <= other.end
                    and other.end - other.start > span.end - span.start
                    for other in found
                )
            ),
            start=1,
        )
    )


def span_values(text: str, spans: Sequence[PersonalDataSpan]) -> Mapping[str, str]:
    """What stands in for each value, keyed by the value. The one place a span is read.

    Keyed by value and not by placeholder, because one value gets one placeholder throughout a
    scan and the other direction is not a map: two spans a reviewer typed the same placeholder on
    would be one entry, and the value that lost would never be replaced --
    leaving a record that says it was redacted and was not.

    A span whose offsets read nothing is skipped: these arrive from a reviewer, and replacing the
    empty string puts a placeholder between every character of the text. So is a span with no
    placeholder, for the same reason read the other way round -- there is nothing to put in the
    text, and replacing a value with nothing deletes it silently instead of marking it.
    """
    return {
        text[span.start : span.end]: span.placeholder
        for span in spans
        if text[span.start : span.end] and span.placeholder
    }


def replaced_text(text: str, placeholders: Mapping[str, str]) -> str:
    """`text` copied with every value `placeholders` has one for replaced by it, longest first.

    Longest first so a shorter value inside a longer one cannot cut it -- `minh<PHONE_1>@vd.vn` is
    neither redacted nor intact.
    """
    replaced = text
    for value, placeholder in sorted(
        placeholders.items(), key=lambda pair: -len(pair[0])
    ):
        replaced = replaced.replace(value, placeholder)
    return replaced


def replaced_node(node: Any, placeholders: Mapping[str, str]) -> Any:
    """`node` copied with every string under it replaced the same way `replaced_text` does.

    By value and not by offset, which is what makes the rule runnable here at all: the offsets
    index `review_text`, and `messages`, `tools` and `label` are other strings.
    So a value confirmed at one occurrence is replaced at every occurrence in every field -- a
    value redacted in one field and left in another is not redacted.

    Anything that is not a string, a mapping or a list is answered as it arrived: a number, a
    boolean and a `null` carry no value to trade back.
    """
    if isinstance(node, str):
        return replaced_text(node, placeholders)
    if isinstance(node, Mapping):
        return {key: replaced_node(value, placeholders) for key, value in node.items()}
    if isinstance(node, list | tuple):
        return [replaced_node(item, placeholders) for item in node]
    return node


def replace_spans_with_placeholders(
    text: str, spans: Sequence[PersonalDataSpan]
) -> str | None:
    """`text` copied with every span's value replaced by its placeholder, longest value first.

    `None` where there is nothing to replace, which is what `reported` means.
    """
    placeholders = span_values(text, spans)
    return replaced_text(text, placeholders) if placeholders else None


def order_claims_by_class(
    text: str,
    claimed: Mapping[str, str],
    declared: Sequence[str],
) -> tuple[tuple[str, str], ...]:
    """The claims as `(class, value)`, one entry per distinct value, in one order.

    Per class, and within a class by first appearance in `text`, which is the order `<CLASS_N>`
    numbers. The declared classes come first, then a class only the model named, in the order it
    was first claimed -- so adding a detector cannot renumber what a reviewer was already reading.
    """
    named = dict.fromkeys(
        personal_data_class
        for personal_data_class in claimed.values()
        if personal_data_class not in declared
    )
    return tuple(
        (personal_data_class, value)
        for personal_data_class in (*declared, *named)
        for value in sorted(
            (value for value, claim in claimed.items() if claim == personal_data_class),
            key=text.index,
        )
    )


def decide_replacement_outcome(
    text: str,
    claims: Sequence[tuple[str, str]],
    spans: Sequence[PersonalDataSpan],
    redacted: str | None,
) -> PersonalDataReplacementOutcome:
    """How far replacing got, read off the copy rather than off what was asked for.

    `reported`: nothing was claimed, so there was nothing to rewrite. `redacted`: every claimed
    value resolved -- the copy holds it nowhere, and every span kept over it reads as its
    placeholder. `withheld`: everything between, including a reviewer who handed back no span at
    all, because a rewrite asked for and not done is not a clean record.

    Read off the copy because two values overlapping *in part* keep both spans,
    and then replacement by value has the second looking for a string the first already cut: its
    placeholder never lands and the copy holds a fragment of a name. Which span should win is
    undecided; that this is not those values redacted is not. A claim with no span at all is
    resolved by the longer value it sat inside.

    The map is `span_values`' own, so a span nothing could be replaced through -- no value at
    those offsets, or no placeholder to put there -- is not in it, and the value it named has to
    be gone from the copy on its own. It is not, because nothing replaced it: `withheld`.
    """
    if not claims:
        return "reported"
    if redacted is None:
        return "withheld"
    placeholders = span_values(text, spans)
    resolved = [
        value
        for _, value in claims
        if value not in redacted
        and (value not in placeholders or placeholders[value] in redacted)
    ]
    return "redacted" if len(resolved) == len(claims) else "withheld"


class PiiLlmDetector:
    """One model reading the text itself, and answering with the values it found."""

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

    async def detect(self, prompt: str, text: str) -> dict[str, str]:
        """Which class the model claims each value as, keyed by value. Never raises (Req. 8).

        The class is upper case and one word, because it is what picks `<CLASS_N>` and
        `<home address_1>` beside `<HOME_ADDRESS_1>` reads as two kinds of thing; a finding
        missing either half names nothing. A failed call and an answer of the wrong shape are one
        event and one empty answer (`H-6`).

        `text` is what the answer is about, and what a claim is checked against: a value not in it
        verbatim is dropped, because the model was asked to copy and a number it normalised
        carries no offset.
        """
        try:
            resp_text = await complete(
                prompt,
                model=self.model.model,
                api_key=self.model.api_key,
                base_url=self.model.base_url,
                **self.settings,
            )
            json_parsed = PiiLlmDetected.model_validate(
                extract_json_from_text(resp_text)
            ).detected
        # A refusal, a timeout, a hung-up socket, prose where JSON was asked for: whatever went
        # wrong, this step detected nothing, which leaves the record to the rule scans.
        except Exception as error:
            logger.warning(
                "pii_llm_detect_failed",
                extra={
                    "model": self.model.model,
                    "error": f"{type(error).__name__}: {error}",
                },
            )
            return {}
        found: dict[str, str] = {}
        for finding in json_parsed:
            named = "_".join(finding.label.upper().split())
            if finding.text and named and finding.text in text:
                found.setdefault(finding.text, named)
        return found


class ToolDecisionPersonalChecking(PersonalDataChecking):
    """Personal data in a tool-calling sample: the turns and the catalog together."""

    def __init__(self, config: PersonalDataCheckingConfig) -> None:
        super().__init__(config)
        self.pii_rule_detector = PiiRuleDetector(self.config.list_scan_functions)
        self.pii_llm_detector = PiiLlmDetector(self.config.verifier_model)

    async def detect(
        self, checking_input: PersonalDataCheckingInput
    ) -> PersonalDataDetected:
        """Both detectors over this sample's review text, and the spans that survive the asking.

        Spans first, then the confirmation, because what it is asked about is a span. Nothing is
        replaced here: what comes back is what a reviewer is shown.
        """
        text = self.build_review_text(checking_input.sample)
        language = checking_input.language
        prompt = self.build_pii_llm_detect_prompt(text, language)
        claimed = {
            **await self.pii_llm_detector.detect(prompt, text),
            **self.pii_rule_detector.detect(text, language),
        }
        claims = order_claims_by_class(text, claimed, self.pii_rule_detector.classes)
        spans = await self.pii_llm_confirm(
            checking_input, text, find_and_number_spans(text, claims)
        )
        return PersonalDataDetected(review_text=text, claims=claims, spans=spans)

    def build_review_text(self, sample: Mapping[str, Any]) -> str:
        """The one string every span's offsets index: the turns, the catalog, then the label.

        The catalog is in it because an argument value in a tool call is where personal data sits,
        and the label because a label is a tool call.
        """
        turns = conversation_turns(sample)
        catalog = openai_tool_format_to_text(sample.get("tools") or ())
        label = json.dumps(sample.get("label"), ensure_ascii=False)
        return "\n".join([*turns, *([catalog] if catalog else []), f"label: {label}"])

    def build_pii_llm_detect_prompt(self, text: str, language: str) -> str:
        """`pii_llm_detect.txt` with its two slots filled: the language, and the text to read.

        The task's own file, because the text it reads is a tool-calling sample. `ConfigError`
        where it is missing, so a deployment with no prompt is not a provider having a bad day.
        """
        template = read_txt(PII_LLM_DETECT_PROMPT)
        if not template.strip():
            raise ConfigError(
                f"no prompt at {PII_LLM_DETECT_PROMPT}: it is the deployment's file, on"
                " the same terms as config/model/"
            )
        return slot_filling(template, {"language": language, "review_text": text})


class ToolDecisionDuplicateChecking(DuplicateDataChecking):
    """Two samples that offer the same tools and say the same thing."""


class ToolDecisionAbnormalChecking(CommonAbnormalChecking):
    """The checks that need no opinion. Undecided, like the base -- returns nothing yet."""
