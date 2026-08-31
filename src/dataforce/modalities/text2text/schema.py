"""DEFINITION · the text2text shapes: what a detector is, and what shows one record to a person.

Two shapes, and both exist because ``modalities/base.py`` refuses to name them: ``Detector`` and
``ContentDisplay`` are aliases for ``Any`` there and are these models here (Requirement 47). A stage
reads one structurally -- ``pipeline/`` may not import this module (I2) -- so every field is named
for what a reader does with it rather than for how this modality happens to hold it.

**A detector is a class name and the scan that finds it.** Requirement 18 puts layer one in
``agent-toolkit``: each of the four scans finds the written form *and* the dictated one, and each
pattern behind one already carries the toned and the tone-stripped spelling, so one pass over the
raw text catches ``khong chin`` and ``không chín`` both. This shape carried two patterns until the
library shipped them; what is left for the modality is the vocabulary its hits are recorded under --
``PHONE``, ``EMAIL``, ``OTP``, ``NAME`` -- and the scan is bound to the declared language before it
gets here, so a stage that may not read a manifest does not have to.

**A content display is a fragment and the task data this half owns.** Neither half of the annotation
config may emit the other's (Requirement 31), so what is here is the ``<Paragraphs>`` tag and the one
``conversation`` key that feeds it. The fragment *reads* one key it does not own -- ``$question`` --
because rendering the question is the display half's job and writing it is
``tool_decision.question_text``'s; ``$tool_names`` is the capture half's on both counts. So neither
config half carries a complete payload, and the module that assembles one out of both is ``publish``
(T24).
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Detector(BaseModel):
    """One class of personal data, and the library scan that finds it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    personal_data_class: str = Field(
        ...,
        description=(
            "The typed class of a hit, which is what picks the placeholder "
            "(`<OTP_1>`) and what the corpus-level report counts. Distinct across "
            "the layer, so a noisy class can be named in a diff."
        ),
    )
    scan: Callable[[str], list[str]] = Field(
        ...,
        description=(
            "The library scan for this class, with the declared language already "
            "bound: one part's text in, the values it found out, in document order. "
            "A scan returns values and never offsets — `pii_check` locates each one "
            "in the text it was handed, because only the raw text has true offsets."
        ),
    )


class ContentDisplay(BaseModel):
    """The display half of the annotation config: what renders a conversation, and what it reads."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tags: str = Field(
        ...,
        description=(
            "The Label Studio fragment this modality contributes, community tags only "
            "(Requirement 52). It references its data by `$name`."
        ),
    )
    data: dict[str, Any] = Field(
        ...,
        description=(
            "The task-payload keys this half *owns*: the conversation, as the array of "
            "message objects `<Paragraphs>` expects. The fragment also reads "
            "`$question`, which is the profile's string — the tag that shows it belongs "
            "to the display half and the words in it do not (Requirement 31)."
        ),
    )
