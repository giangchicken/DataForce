"""logic · the data-quality checks over a tool-calling sample.

Personal data is the one with a body to write, and it is two calls with a human between them.
`detect` is the frame of reference every offset indexes, two detectors unioned, and the modality's
confirmation over the spans they earn. `replace_node` is the second, over the spans that human
handed back: the replacement runs over the record's own fields rather than over the review text,
because an offset indexes the text and `messages`, `tools` and `label` are other strings -- which
is where the record's `new_` keys come from. `decide_replacement_outcome` says how far it got.
What this task reads is `build_review_text`: the turns, the catalog *and* the label, because an
argument value in a tool call is where a phone number sits and a label is a tool call.
"""

import re
from collections.abc import Iterator, Mapping, Sequence
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

from .utils import build_review_text

# The deployment's, on the same terms as `config/model/`: read from the working directory and named
# for the method that sends it.
PII_LLM_DETECT_PROMPT = Path("config/prompts/profiles/tool_decision/pii_llm_detect.txt")
# A scan claims a value at a word boundary and a search for one knows none, so `09123456789012`
# would otherwise hold a phone number.
WORD = re.compile(r"\w")

logger = get_logger(__name__)


def walk_record_strings(
    node: Any, path: tuple[str | int, ...] = ()
) -> Iterator[tuple[tuple[str | int, ...], str]]:
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, Mapping):
        for key, value in node.items():
            yield from walk_record_strings(value, (*path, key))
    elif isinstance(node, list | tuple):
        for at, value in enumerate(node):
            yield from walk_record_strings(value, (*path, at))


def find_spans_in_text(
    text: str,
    path: tuple[str | int, ...],
    detected: Sequence[tuple[str, str]],
    placeholders: Mapping[str, str],
) -> list[tuple[int, PersonalDataSpan]]:
    here: list[tuple[int, PersonalDataSpan]] = []
    for claimed_at, (personal_data_class, value) in enumerate(detected):
        start = text.find(value)
        while start >= 0:
            end = start + len(value)
            before = text[start - 1] if start else ""
            after = text[end] if end < len(text) else ""
            if not (WORD.match(before) or WORD.match(after)):
                here.append(
                    (
                        claimed_at,
                        PersonalDataSpan(
                            id=0,
                            path=path,
                            start=start,
                            end=end,
                            personal_data_class=personal_data_class,
                            placeholder=placeholders[value],
                        ),
                    )
                )
            start = text.find(value, end)
    return [
        (claimed_at, span)
        for claimed_at, span in here
        if not any(
            other.start <= span.start
            and span.end <= other.end
            and other.end - other.start > span.end - span.start
            for _, other in here
        )
    ]


def name_placeholders(detected: Sequence[tuple[str, str]]) -> Mapping[str, str]:
    """`<CLASS_N>` per distinct value, numbered per class in the order the claims arrive.

    Which value gets `_1` is read off the claim order, which `order_claims_by_class` set from
    `review_text` -- the string a reviewer reads in order. Only *where* a span is moved into the
    record; which placeholder a value wears did not.
    """
    number_by_class: dict[str, int] = {}
    placeholder_by_value: dict[str, str] = {}
    for personal_data_class, value in detected:
        if value in placeholder_by_value:
            continue
        number_by_class[personal_data_class] = (
            number_by_class.get(personal_data_class, 0) + 1
        )
        placeholder_by_value[value] = (
            f"<{personal_data_class}_{number_by_class[personal_data_class]}>"
        )
    return placeholder_by_value


def find_and_number_spans(
    record: Mapping[str, Any], detected: Sequence[tuple[str, str]]
) -> tuple[PersonalDataSpan, ...]:

    placeholders = name_placeholders(detected)
    spans_with_order = [
        (claimed_at, walked_at, span)
        for walked_at, (path, text) in enumerate(walk_record_strings(record))
        for claimed_at, span in find_spans_in_text(text, path, detected, placeholders)
    ]
    return tuple(
        span.model_copy(update={"id": numbered})
        for numbered, (_, _, span) in enumerate(
            sorted(spans_with_order, key=lambda one: (one[0], one[1], one[2].start)),
            start=1,
        )
    )


def replace_spans_in_text(text: str, spans: Sequence[PersonalDataSpan]) -> str:
    replaced_text = text
    lowest = len(text)
    for span in sorted(spans, key=lambda one: -one.start):
        if span.start >= span.end or not span.placeholder or span.end > len(text):
            continue
        if span.end > lowest:
            continue
        replaced_text = (
            replaced_text[: span.start] + span.placeholder + replaced_text[span.end :]
        )
        lowest = span.start
    return replaced_text


def replace_node(
    node: Any,
    spans: Mapping[tuple[str | int, ...], Sequence[PersonalDataSpan]],
    path: tuple[str | int, ...] = (),
) -> Any:
    if isinstance(node, str):
        return replace_spans_in_text(node, spans.get(path, ()))
    if isinstance(node, Mapping):
        return {
            key: replace_node(value, spans, (*path, key)) for key, value in node.items()
        }
    if isinstance(node, list | tuple):
        return [replace_node(item, spans, (*path, at)) for at, item in enumerate(node)]
    return node


def group_spans_by_path(
    spans: Sequence[PersonalDataSpan],
) -> Mapping[tuple[str | int, ...], tuple[PersonalDataSpan, ...]]:
    """The spans keyed by the string each one is in, which is what `replace_node` walks against."""
    grouped: dict[tuple[str | int, ...], list[PersonalDataSpan]] = {}
    for span in spans:
        grouped.setdefault(tuple(span.path), []).append(span)
    return {path: tuple(here) for path, here in grouped.items()}


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
    spans: Sequence[PersonalDataSpan], redacted: Mapping[str, Any]
) -> PersonalDataReplacementOutcome:

    if not spans:
        return "reported"
    text_by_path = dict(walk_record_strings(redacted))
    number_by_place: dict[tuple[tuple[str | int, ...], str], int] = {}
    for span in spans:
        if span.start >= span.end or not span.placeholder:
            return "withheld"
        place = (tuple(span.path), span.placeholder)
        number_by_place[place] = number_by_place.get(place, 0) + 1
    return (
        "redacted"
        if all(
            text_by_path[path].count(placeholder) >= number
            for (path, placeholder), number in number_by_place.items()
            if path in text_by_path
        )
        else "withheld"
    )


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

        except Exception as error:
            logger.warning(
                "pii_llm_detect_failed",
                extra={
                    "model": self.model.model,
                    "error": f"{type(error).__name__}: {error}",
                },
            )
            return {}
        class_by_value: dict[str, str] = {}
        for finding in json_parsed:
            personal_data_class = "_".join(finding.label.upper().split())
            if finding.text and personal_data_class and finding.text in text:
                class_by_value.setdefault(finding.text, personal_data_class)
        return class_by_value


class ToolDecisionPersonalChecking(PersonalDataChecking):
    """Personal data in a tool-calling sample: the turns and the catalog together."""

    def __init__(self, config: PersonalDataCheckingConfig) -> None:
        super().__init__(config)
        self.pii_rule_detector = PiiRuleDetector(self.config.list_scan_functions)
        self.pii_llm_detector = PiiLlmDetector(self.config.verifier_model)

    async def detect(
        self, checking_input: PersonalDataCheckingInput
    ) -> PersonalDataDetected:

        text = build_review_text(checking_input.sample)
        language = checking_input.language
        prompt = self.build_pii_llm_detect_prompt(text, language)
        class_by_value = {
            **await self.pii_llm_detector.detect(prompt, text),
            **self.pii_rule_detector.detect(text, language),
        }
        claims = order_claims_by_class(
            text, class_by_value, self.pii_rule_detector.classes
        )
        spans = await self.confirm_pii_by_llm(
            checking_input,
            text,
            find_and_number_spans(checking_input.sample, claims),
        )
        return PersonalDataDetected(review_text=text, claims=claims, spans=spans)

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


class ToolDecisionAbnormalChecking(CommonAbnormalChecking):
    """The checks that need no opinion. Undecided, like the base -- returns nothing yet."""
