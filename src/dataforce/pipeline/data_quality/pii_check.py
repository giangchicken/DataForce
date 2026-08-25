"""STEP · pii_check · two-layer detection, typed placeholders, `content` rewritten.

The only stage that changes what a record already carries, and Requirement 5 names it as the
exception: it writes its own key, rewrites ``content`` and the ``label`` **together**, and bumps
``content_version``. Redacting one of that pair and not the other is worse than redacting neither --
it manufactures a ``label_assistant_mismatch`` downstream and makes ``export`` emit a training
example whose input reads ``<CUSTOMER_ID_1>`` and whose target reads the original value, which
teaches a model to produce an identifier absent from its input. That is a data-poisoning defect
wearing a privacy defect's clothes (Requirement 17).

**Layer one is the modality's patterns; layer two is the edge's model.** The detectors come from
``personal_data_detectors()`` and are read structurally -- ``pipeline/`` may not import an axis
implementation (I2), which is why every field of a detector is named for what a reader does with it.
The model pass is a port on the ``Engine``, because a model call opens a socket and no engine module
may (I1, ``ports.py``). **No verifier is not confirmation by default:** every hit stays unverified,
the record says so, and the content is not rewritten -- an absent second layer must not silently turn
into *everything layer one guessed was right*.

**The tone-stripped scan is normalised per word so an offset survives it.** Requirement 18 runs the
patterns over the raw text *and* over a tone-stripped normalisation, and Requirement 19 records each
span against the content it was found in -- but ``normalize_text`` collapses whitespace and strips the
ends, so an offset into its output is not an offset into ``content`` and the matched string may not
even occur in the raw text, which would make it unreplaceable. ``tone_stripped_view`` is the
resolution: word by word, and only where the stripped word is the same length. The cost is written
down in § *PII, in two layers* -- a word whose NFKC form changes length is left alone rather than
shifting every offset after it.

**Only a confirmed hit is replaced.** Layer two exists to set precision, so the digit run that turns
out to be a price stays in the text and the span says why (§ *Testing Strategy* item 6). That is what
gives ``decision`` three values rather than two: ``reported`` where redaction is off, ``redacted``
where it is on and nothing is unconfirmed, and ``withheld`` where it is on and something is -- the
confirmed hits are still replaced, and the record is held out of a release by ``export``'s
precondition rather than by a count nobody reads.

**The placeholder map is side output and nothing here reads one.** It is the only thing in the
pipeline that holds personal data outside a record, so it goes to the edge, into the privacy tier
`.gitignore` covers, and no stage can read it -- structurally, because a service is handed records and
an engine and never another stage's side output (I13).
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, NamedTuple

from agent_toolkit.string_utils import normalize_text

from dataforce.engine import Engine, ServiceResult
from dataforce.errors import ConfigError
from dataforce.ports import PersonalDataVerifier
from dataforce.record import (
    PersonalDataScan,
    PersonalDataSpan,
    Record,
    redacted_text,
)

from ..params import declared_switch

# Where `params.yaml` says whether a hit is replaced or only reported.
REDACT = ("enable_redact",)

# What the edge persists, and under whose name.
STAGE = "pii_check"
PLACEHOLDERS = "placeholders"

# One whitespace-separated word, which is the unit the tone-stripped view is built in.
WORD = re.compile(r"\S+")


class Hit(NamedTuple):
    """One thing layer one found: where it is, what it says, and what it might be."""

    part: int  # index into `content` of the part it was found in
    start: int  # character offset in that part's text, inclusive
    end: int  # character offset of its end, exclusive
    value: str  # the text itself, which is what gets replaced wherever it appears
    guessed: (
        str  # the class of the first detector that matched it, in the modality's order
    )


def tone_stripped_view(text: str) -> str:
    """The same text with its tone marks gone and every character still at its own index.

    `normalize_text` is the library's (I6) and it collapses whitespace, so it is applied to one word
    at a time and only where the result is the same length -- which for Vietnamese it is, since
    stripping the marks off a precomposed character leaves one character. A word whose NFKC form is a
    different length is left as it was: it is the rarer case by far, and shifting every offset after
    it would cost every span in the part.
    """
    view = list(text)
    for word in WORD.finditer(text):
        stripped = normalize_text(word[0], remove_tone_marks=True)
        if len(stripped) == len(word[0]):
            view[word.start() : word.end()] = stripped
    return "".join(view)


def outermost(found: Sequence[Hit]) -> tuple[Hit, ...]:
    """The hits that are not inside another hit, each keeping the first class that claimed it.

    Layer one's patterns overlap on purpose -- a phone number matches the phone pattern and the
    digit-run pattern, and a digit run inside an email address matches both of those -- so the same
    text arrives two or three times. Keeping all of them would mint a placeholder for a value that is
    already gone by the time its turn comes, and list a class the record does not really carry. The
    sort puts a containing hit before anything inside it and a lower detector index before a higher
    one, so *first in the modality's declared order* is the class that wins.
    """
    kept: list[Hit] = []
    for hit in sorted(found, key=lambda hit: (hit.part, hit.start, -hit.end)):
        if any(
            inside.part == hit.part
            and inside.start <= hit.start
            and hit.end <= inside.end
            for inside in kept
        ):
            continue
        kept.append(hit)
    return tuple(kept)


def hits_in_part(index: int, text: str, detectors: Sequence[Any]) -> tuple[Hit, ...]:
    """Everything layer one flags in one part, both spellings of every pattern (Requirement 18).

    `detectors` is a `Sequence[Any]` because a `Detector` is `modalities/base.py`'s opaque type and
    the concrete model is the modality's `schema.py`, which this module may not import (I2). The
    three fields read here are the three that shape's docstring says a reader reads.
    """
    stripped = tone_stripped_view(text)
    return outermost(
        [
            Hit(
                index,
                match.start(),
                match.end(),
                text[match.start() : match.end()],
                detector.personal_data_class,
            )
            for detector in detectors
            for scanned, pattern in (
                (text, detector.pattern),
                (stripped, detector.tone_stripped_pattern),
            )
            for match in re.finditer(pattern, scanned)
        ]
    )


def confirmed_in_window(
    verifier: PersonalDataVerifier | None, window: str, guessed: Mapping[str, str]
) -> Mapping[str, str]:
    """What layer two confirms in one part, by value, or nothing where there is no layer two.

    A failed call is read as *nothing confirmed*, for the reason § *Error Behavior* gives the jury: a
    model call that failed after the library's own retries is one missing answer and not a reason to
    stop a run of twenty thousand records (Requirement 43). The record carries the consequence --
    `unverified`, and a `decision` of `withheld` -- which is a great deal louder than a log line.
    A class the verifier invents for a value nobody flagged is dropped: the window is evidence about
    the candidates, not an invitation to add some.

    **A `ConfigError` is not read as a failed call.** It is the one exception this codebase raises and
    it means *a human must change configuration* (P23) -- an adapter that cannot reach its endpoint
    raises it on every record, and the run would complete with every hit `unverified` and every
    record `withheld`. That fails safe, unlike `jury`'s version of the same hole, which fails
    silent; but *safe* here means nothing ships and no line says why, and the wrong reason for
    holding a corpus back is the expensive kind of quiet.
    """
    if verifier is None or not guessed:
        return {}
    try:
        confirmed = verifier.confirmed_personal_data(window, dict(guessed))
    except ConfigError:
        raise
    except Exception:
        return {}
    return {value: str(named) for value, named in confirmed.items() if value in guessed}


def placeholders_for(classes: Mapping[str, str]) -> dict[str, str]:
    """One typed placeholder per value: `<CUSTOMER_ID_1>`, numbered per class within the record.

    Scoped per record (Requirement 17) and numbered in the order the scan first met each value, so
    two runs over one record mint the same names. A value used twice keeps one placeholder, which is
    the whole reason this is keyed by value rather than by span.
    """
    counted: dict[str, int] = {}
    minted: dict[str, str] = {}
    for value, named in classes.items():
        counted[named] = counted.get(named, 0) + 1
        minted[value] = f"<{named}_{counted[named]}>"
    return minted


def label_check_has_run(record: Record) -> bool:
    """This stage's precondition (Requirement 42): the key `label_check` writes is on the record.

    The *value* is not the condition. A quarantined record is still scanned -- personal data in a
    record that failed a label check is still personal data -- which is why § *Per-service contracts*
    said this stage skips "never": no verdict is a reason to skip. What it skips is a record that
    never went through `label_check` at all, and every later service sees the same absence and skips
    too.
    """
    return record.data_quality.label_check is not None


def scanned(
    engine: Engine, record: Record, detectors: Sequence[Any], redact: bool
) -> tuple[Record, Mapping[str, str]]:
    """One record scanned, rewritten where a hit was confirmed, and its placeholder map.

    The spans are recorded against `content_version_scanned` -- the version *before* the rewrite
    (Requirement 19) -- because replacing a value changes every offset after it. Replacement is by
    value and not by offset for the same reason: one placeholder per value means one pass.
    """
    hits = tuple(
        hit
        for index, part in enumerate(record.content)
        if part.text is not None
        for hit in hits_in_part(index, part.text, detectors)
    )
    confirmed: dict[str, str] = {}
    for index, part in enumerate(record.content):
        found = {hit.value: hit.guessed for hit in hits if hit.part == index}
        for value, named in confirmed_in_window(
            engine.personal_data_verifier, part.text or "", found
        ).items():
            confirmed.setdefault(value, named)

    classes: dict[str, str] = {}
    for hit in hits:
        classes.setdefault(hit.value, confirmed.get(hit.value, hit.guessed))
    placeholders = placeholders_for(classes)
    unverified = sum(1 for hit in hits if hit.value not in confirmed)
    scan = PersonalDataScan(
        decision=("withheld" if unverified else "redacted") if redact else "reported",
        content_version_scanned=record.content_version,
        spans=tuple(
            PersonalDataSpan(
                part=hit.part,
                start=hit.start,
                end=hit.end,
                # `class` is a keyword, so the record aliases the field and this is the spelling
                # `mypy --strict` accepts -- the same one `tests/stages/test_record.py` uses.
                **{"class": classes[hit.value]},
                verified=hit.value in confirmed,
                placeholder=placeholders[hit.value],
            )
            for hit in hits
        ),
        classes=tuple(sorted(set(classes.values()))),
        unverified=unverified,
    )
    written: dict[str, Any] = {
        "data_quality": record.data_quality.model_copy(update={STAGE: scan})
    }
    replacements = {value: placeholders[value] for value in confirmed}
    if not (redact and replacements):
        return record.model_copy(update=written), {}
    written["content"] = tuple(
        part
        if part.text is None
        else part.model_copy(update={"text": redacted_text(part.text, replacements)})
        for part in record.content
    )
    written["content_version"] = record.content_version + 1
    written["label"] = engine.profile.redact_label(record.label, replacements)
    return record.model_copy(update=written), {
        placeholder: value for value, placeholder in replacements.items()
    }


def pii_check(engine: Engine, records: Iterable[Record]) -> ServiceResult:
    """Every record scanned, and one map of everything that was replaced, for the edge.

    The map is keyed by `record_id` because a placeholder is scoped per record: `<CUSTOMER_ID_1>` in
    one record and in the next are two different people, and a map that flattened them would be
    unusable for the one thing it exists for.
    """
    detectors = engine.modality.personal_data_detectors()
    redact = declared_switch(engine, *REDACT)
    written: list[Record] = []
    mapped: dict[str, Mapping[str, str]] = {}
    for record in records:
        if not label_check_has_run(record):
            written.append(record)
            continue
        record_written, placeholders = scanned(engine, record, detectors, redact)
        written.append(record_written)
        if placeholders:
            mapped[record.record_id] = placeholders
    return ServiceResult(
        records=tuple(written),
        side_output={STAGE: {PLACEHOLDERS: mapped}} if mapped else {},
    )
