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
    counted: dict[str, int] = {}
    named: dict[str, str] = {}
    for personal_data_class, value in detected:
        if value in named:
            continue
        counted[personal_data_class] = counted.get(personal_data_class, 0) + 1
        named[value] = f"<{personal_data_class}_{counted[personal_data_class]}>"
    return named


def find_and_number_spans(
    record: Mapping[str, Any], detected: Sequence[tuple[str, str]]
) -> tuple[PersonalDataSpan, ...]:
    """Every span those values carry in the record: located, numbered, and the outermost kept.

    `id` is 1-based over what survives, ordered by the claim first and by the walk second -- the
    same order the ids ran in when the frame of reference was one text, so what a confirmation is
    asked about did not move when *where a span is* did. Within one string they run by offset. Every entry of `detected` is one non-empty value -- `pii_detect` holds
    that -- and a value that occurs nowhere in the record simply earns no span, which is a claim
    left unresolved rather than an error.
    """
    placeholders = name_placeholders(detected)
    found = [
        (claimed_at, walked_at, span)
        for walked_at, (path, said) in enumerate(walk_record_strings(record))
        for claimed_at, span in find_spans_in_text(said, path, detected, placeholders)
    ]
    return tuple(
        span.model_copy(update={"id": numbered})
        for numbered, (_, _, span) in enumerate(
            sorted(found, key=lambda one: (one[0], one[1], one[2].start)), start=1
        )
    )


def replace_spans_in_text(said: str, spans: Sequence[PersonalDataSpan]) -> str:
    replaced = said
    lowest = len(said)
    for span in sorted(spans, key=lambda one: -one.start):
        if span.start >= span.end or not span.placeholder or span.end > len(said):
            continue
        if span.end > lowest:
            continue
        replaced = replaced[: span.start] + span.placeholder + replaced[span.end :]
        lowest = span.start
    return replaced


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
    claims: Sequence[tuple[str, str]],
    spans: Sequence[PersonalDataSpan],
    redacted: Mapping[str, Any],
) -> PersonalDataReplacementOutcome:
    """How far replacing got, read off the copy rather than off what was asked for.

    `reported`: nothing was claimed, so there was nothing to rewrite. `redacted`: every claimed
    value resolved -- the copy holds no occurrence of it that anything would detect. `withheld`:
    everything between, including a reviewer who handed back no span at all, because a rewrite
    asked for and not done is not a clean record. That last case needs no branch of its own: a
    claim nobody handed a span for still stands in the copy, so it never resolves.

    **Measured by running the span finder again over the copy**, and not by asking whether the
    value is a substring of it. Those are different questions, and per-span replacement is what
    made the difference show: an order number `09123456789012` holding a phone inside it is not
    that phone left un-redacted -- it earns no span, because a word character butts against it --
    and replacing by value used to hide the distinction by cutting the order number in half.

    Two questions, and a claim resolves only on both. *Is it still standing* -- no occurrence of
    the value that anything would detect is left in the copy. And *did its placeholder land* --
    because a span handed back and then not applied, for overlapping one already replaced, takes
    its value out of the copy by **cutting** it rather than by replacing it, and half a name gone
    is not a name redacted. A claim nothing could ever replace has no usable span, so the second
    question is not asked of it and being absent is enough.
    """
    if not claims:
        return "reported"
    placeholders = name_placeholders(claims)
    standing = {span.placeholder for span in find_and_number_spans(redacted, claims)}
    usable = {
        span.placeholder for span in spans if span.start < span.end and span.placeholder
    }
    landed = {
        placeholder
        for placeholder in set(placeholders.values())
        if any(placeholder in said for _, said in walk_record_strings(redacted))
    }
    resolved = [
        value
        for _, value in claims
        if placeholders[value] not in standing
        and (placeholders[value] not in usable or placeholders[value] in landed)
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

        text = build_review_text(checking_input.sample)
        language = checking_input.language
        prompt = self.build_pii_llm_detect_prompt(text, language)
        claimed = {
            **await self.pii_llm_detector.detect(prompt, text),
            **self.pii_rule_detector.detect(text, language),
        }
        claims = order_claims_by_class(text, claimed, self.pii_rule_detector.classes)
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
