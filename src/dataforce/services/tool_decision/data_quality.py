"""logic · the full logic behind each data-quality endpoint.

Personal data is two calls, because a human sits between them. `personal_data_detect` builds the
checker from its config and the scan's input out of what arrived -- the record whole, and the
language declared beside it -- and answers what a reviewer is shown. `personal_data_replace` takes
that answer back with the spans as the reviewer left them, and replaces those and nothing else.

`duplicate_report` and `abnormal_report` take a sample and nothing else: neither declares a shape
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
from dataforce.profile.tool_decision import ToolDecisionPersonalChecking
from dataforce.profile.tool_decision.data_quality import (
    decide_replacement_outcome,
    replace_spans_with_placeholders,
)


async def personal_data_detect(
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


def personal_data_replace(detected: PersonalDataDetected) -> PersonalDataReplaced:
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


async def duplicate_report(sample: Mapping[str, Any]) -> None:
    """None, by declaration. Nothing says what a duplicate report is."""
    return None


async def abnormal_report(sample: Mapping[str, Any]) -> None:
    """None, by declaration. Nothing says what a common check reports."""
    return None
