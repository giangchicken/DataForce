"""logic · the full logic behind each data-quality endpoint.

Personal data is two calls a reviewer sits between, and a third over the record they left. `detect_personal_data` builds the
checker from its config and the scan's input out of what arrived -- the record whole, and the
language declared beside it -- and answers what a reviewer is shown. `replace_personal_data` takes
that answer back with the spans as the reviewer left them, and replaces those and nothing else.
`redact_personal_data` runs the same replacement over the record's own fields, which is the one
place the review text's offsets cannot reach.

`report_duplicates` and `report_abnormalities` take a sample and nothing else: neither declares a shape
to return, so neither has a model to ask, and a config they ignore would be one a caller has to
supply for nothing.
"""

from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from dataforce.errors import ConfigError
from dataforce.modalities.text2text.data_quality import (
    PersonalDataCheckingConfig,
    PersonalDataCheckingInput,
    PersonalDataDetected,
    PersonalDataReplaced,
)
from dataforce.modalities.text2text.data_quality.schema import Language
from dataforce.profile.tool_decision.data_quality import (
    ToolDecisionPersonalChecking,
    decide_replacement_outcome,
    read_span_values,
    replace_node,
    replace_spans_with_placeholders,
)


async def detect_personal_data(
    config: PersonalDataCheckingConfig,
    sample: Mapping[str, Any],
    language: Language,
) -> PersonalDataDetected:
    """What one sample says about a person, in the text a reviewer reads it in.

    The language is declared beside the record and not read out of it: a sample is what a corpus
    carries, and what language to scan in is the caller's declaration about this request.

    A language this deployment cannot scan in is a `ConfigError` and so answers 422: this is the
    boundary where an outside body becomes the scan's input, so the refusal is a declaration
    error rather than a `ValidationError` reaching a handler as a 500.
    """
    try:
        checking_input = PersonalDataCheckingInput.model_validate(
            {"sample": sample, "language": language}
        )
    except ValidationError as error:
        raise ConfigError(f"the scan cannot read this record: {error}") from error
    return await ToolDecisionPersonalChecking(config).detect(checking_input)


def replace_personal_data(detected: PersonalDataDetected) -> PersonalDataReplaced:
    """The review text copied with those spans replaced, and how far that got.

    Not async, because nothing here is asked: the spans arrive from the reviewer who ticked,
    edited or added them, and replacing what they handed back reaches no model and no endpoint.

    The outcome is measured against `claims`, which is why the detect answer carries them: a
    reviewer who hands back no span leaves a record that was asked to be rewritten and was not.
    """
    redacted = replace_spans_with_placeholders(detected.review_text, detected.spans)
    return PersonalDataReplaced(
        redacted_text=redacted,
        outcome=decide_replacement_outcome(
            detected.review_text, detected.claims, detected.spans, redacted
        ),
    )


def redact_personal_data(
    detected: PersonalDataDetected, sample: Mapping[str, Any]
) -> dict[str, Any]:
    """The sample as the human left it, with every handed-back span's value replaced.

    The third personal-data call, and the same rule as the second over a different reach:
    `replace_personal_data` copies `review_text`, and this copies every field the record carries,
    because an offset indexes the review text and `messages` and `label` are other strings.
    Which is why it is handed the detect answer whole rather than the spans
    alone -- the text they index is what says which value each placeholder stands for.

    Where the record's `new_` keys come from: the page holds what the human
    edited, this replaces over it, and the page composes the record out of what comes back. The
    rule is the service's and not the page's, because a rule a caller can skip is not a rule.

    Not async, and no model is asked: the spans arrive from the reviewer who ticked, edited or
    added them. Nothing is kept either -- the sample is read, copied and answered.
    """
    placeholders = read_span_values(detected.review_text, detected.spans)
    return {key: replace_node(value, placeholders) for key, value in sample.items()}


async def report_duplicates(sample: Mapping[str, Any]) -> None:
    """None, by declaration. Nothing says what a duplicate report is."""
    return None


async def report_abnormalities(sample: Mapping[str, Any]) -> None:
    """None, by declaration. Nothing says what a common check reports."""
    return None
