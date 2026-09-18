"""logic · a finished review read as the row it becomes, and the refusal that comes first.

**The refusal is this file's whole reason to be the modality's.** What it reads -- whether anybody
scanned the sample, and whether a value the redaction confirmed is still readable in what ships --
is a text2text shape, and the obligation behind it is the law's rather than one task's: a corpus
derived from personal data is tradeable only once de-identified, so `khử nhận dạng` is something the
`dataset` table has to be able to prove about every row it holds. The cheapest proof is that a row
failing it never arrived. A second text2text task inherits this, and a per-task copy must not exist,
because a copy that drifts is a corpus sold in breach.

**Which is why refusing raises rather than answering.** A precondition that came back as a value
would be a precondition a caller can forget to read, and the one that gets forgotten is the one
whose cost is a fine. Past `build_sample`, a `DatasetSample` is a document that passed.

What the task answers is small and named by the two abstract methods: what its `input` holds, and
which facets only it can read. Everything else -- what ships, what was redacted, what a person
ticked -- is the same for every sample this modality will ever hold.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from typing import Any

from pydantic import ValidationError

from ..data_quality.schema import PersonalDataSpan
from .schema import DatasetSample, ScannedPersonalData, ShippedDatasetSample, StepNotRun

# The two steps a record can arrive without, named as the reviewer's page names them, because the
# refusal is read by the person who has to go back and run one.
PERSONAL_DATA_SCAN = "the personal-data scan"
REDACTION = "the redaction"

# The three fields that have a `new_` copy. One rule over three names, rather than three readings.
SHIPPED_PARTS = ("messages", "tools", "label")


def read_shipped_part(document: Mapping[str, Any], part: str) -> Any:
    shipped = document.get(f"new_{part}")
    return document.get(part) if shipped is None else shipped


def read_shipped_sample(document: Mapping[str, Any]) -> ShippedDatasetSample:
    """The three as they ship. What arrived stays behind in the document and is not read again."""
    label = read_shipped_part(document, "label")
    return ShippedDatasetSample(
        messages=tuple(read_shipped_part(document, "messages") or ()),
        tools=tuple(read_shipped_part(document, "tools") or ()),
        label=None if label is None else tuple(label),
    )


def read_scanned_personal_data(document: Mapping[str, Any]) -> ScannedPersonalData:
    scanned = document.get("personal_data")
    if scanned is None:
        raise StepNotRun(
            f"{PERSONAL_DATA_SCAN} did not run: personal_data is null,"
            " so nobody scanned this sample"
        )
    try:
        return ScannedPersonalData.model_validate(scanned)
    except ValidationError as error:
        raise StepNotRun(
            f"{PERSONAL_DATA_SCAN} did not run: personal_data will not read"
            f" as a scan: {error}"
        ) from error


def list_text(node: Any) -> Iterator[str]:
    if isinstance(node, str):
        yield node
    elif isinstance(node, Mapping):
        for value in node.values():
            yield from list_text(value)
    elif isinstance(node, list | tuple):
        for item in node:
            yield from list_text(item)


def find_surviving_spans(
    scanned: ScannedPersonalData, shipped: ShippedDatasetSample
) -> tuple[PersonalDataSpan, ...]:

    written = tuple(list_text(shipped.model_dump()))
    return tuple(
        span
        for span in scanned.spans
        if (value := scanned.review_text[span.start : span.end])
        and any(value in one for one in written)
    )


def read_redacted_classes(scanned: ScannedPersonalData) -> tuple[str, ...]:
    return tuple(sorted({span.personal_data_class for span in scanned.spans}))


class DatasetSampleBuilding(ABC):
    def build_sample(self, document: Mapping[str, Any]) -> DatasetSample:
        scanned = read_scanned_personal_data(document)
        shipped = read_shipped_sample(document)
        if survived := find_surviving_spans(scanned, shipped):
            raise StepNotRun(
                f"{REDACTION} did not run: a confirmed value is still in what ships, at "
                + ", ".join(
                    f"span {span.id} ({span.personal_data_class})" for span in survived
                )
            )
        return DatasetSample(
            input=self.build_input(shipped),
            label=shipped.label,
            facets={
                **(document.get("class") or {}),
                "personal_data": list(read_redacted_classes(scanned)),
                **self.compute_facets(shipped),
            },
        )

    @abstractmethod
    def build_input(self, shipped: ShippedDatasetSample) -> Mapping[str, Any]:
        """What one sample of this task ships as -- the single `input` column of its table."""

    @abstractmethod
    def compute_facets(self, shipped: ShippedDatasetSample) -> Mapping[str, Any]:
        """The facets reading this task's own sample answers, and only those.

        Computed every time a row is written, from the row, so none of them can disagree with the
        sample. Whatever a person ticks arrives under `class` instead and is not asked for here.
        """
