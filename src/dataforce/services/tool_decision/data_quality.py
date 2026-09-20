"""logic · the full logic behind each data-quality endpoint.

Personal data is two calls a reviewer sits between. `detect_personal_data` builds the
checker from its config and the scan's input out of what arrived -- the record whole, and the
language declared beside it -- and answers what a reviewer is shown. `redact_personal_data` takes
that answer back with the spans as the reviewer left them, and replaces those values and nothing
else, over the record's own fields -- the one reach the review text's offsets do not have. It
answers the redacted record, the text that record now reads as, and how far the rewrite got.

**There was a third, and it was the same rewrite with less reach.** `replace_personal_data`
copied `review_text` alone and answered a text nothing read and an outcome measured against the
scan's own copy rather than against what ships. Both halves are here now, over the record.

`check_label_calls` is the one check here with no model behind it at all: the store's own
`schema_valid` rule, asked while the sample is still on the screen, so that a reviewer is told a
label names a tool without calling it *before* they say the label is correct.

`report_duplicates` and `report_abnormalities` take a sample and nothing else: neither declares a shape
to return, so neither has a model to ask, and a config they ignore would be one a caller has to
supply for nothing.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from dataforce.errors import ConfigError
from dataforce.modalities.text2text.data_quality import (
    PersonalDataCheckingConfig,
    PersonalDataCheckingInput,
    PersonalDataDetected,
    PersonalDataRedacted,
)
from dataforce.modalities.text2text.data_quality.schema import Language
from dataforce.profile.tool_decision.data_quality import (
    ToolDecisionPersonalChecking,
    decide_replacement_outcome,
    read_span_values,
    replace_node,
)
from dataforce.profile.tool_decision.label_statistics import list_label_faults
from dataforce.profile.tool_decision.schema import LabelChecked
from dataforce.profile.tool_decision.utils import build_review_text


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


def redact_personal_data(
    detected: PersonalDataDetected, sample: Mapping[str, Any]
) -> PersonalDataRedacted:
    """The sample as the human left it with every handed-back value replaced, and how it reads.

    The second personal-data call and the last one. It copies every field the record carries,
    because an offset indexes the review text and `messages` and `label` are other strings.
    Which is why it is handed the detect answer whole rather than the spans
    alone -- the text they index is what says which value each placeholder stands for.

    Where the record's `new_` keys come from: the page holds what the human
    edited, this replaces over it, and the page composes the record out of what comes back. The
    rule is the service's and not the page's, because a rule a caller can skip is not a rule.

    The text comes back beside the record because it is the only way to *see* what the reach
    bought: the label is rendered into it, so `<EMAIL_1>` standing in a turn and `<EMAIL_1>`
    standing in a call's argument are one line apart on a screen. Rendered forward from the
    redacted record, never read back out of a text -- there is no way back from a review text to
    a sample, and building one would be a second definition of what a turn and a call are.

    Not async, and no model is asked: the spans arrive from the reviewer who ticked, edited or
    added them. Nothing is kept either -- the sample is read, copied and answered.
    """
    placeholders = read_span_values(detected.review_text, detected.spans)
    redacted = {key: replace_node(value, placeholders) for key, value in sample.items()}
    reads_as = build_review_text(redacted)
    return PersonalDataRedacted(
        sample=redacted,
        review_text=reads_as,
        outcome=decide_replacement_outcome(
            detected.review_text, detected.claims, detected.spans, reads_as
        ),
    )


def check_label_calls(label: Any, catalog: Sequence[Any]) -> LabelChecked:
    faults = list_label_faults(label, catalog)
    return LabelChecked(schema_valid=not faults, faults=faults)


async def report_duplicates(sample: Mapping[str, Any]) -> None:
    """None, by declaration. Nothing says what a duplicate report is."""
    return None


async def report_abnormalities(sample: Mapping[str, Any]) -> None:
    """None, by declaration. Nothing says what a common check reports."""
    return None
