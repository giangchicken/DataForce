"""DEFINITION · the text2text shapes: what a detector is, and what its display config holds.

Two shapes, and both exist because ``modalities/base.py`` refuses to name them: ``Detector`` and
``DisplayConfig`` are aliases for ``Any`` there and are these models here (Requirement 47). A stage
reads one structurally -- ``pipeline/`` may not import this module (I2) -- so every field is named
for what a reader does with it rather than for how this modality happens to hold it.

**A detector carries the same pattern twice.** Requirement 18 runs layer one over the raw text
*and* over ``normalize_text(text, remove_tone_marks=True)``, so a pattern written in correct
Vietnamese -- ``không``, ``a còng`` -- cannot match the tone-stripped half of its own scan. Writing
it out twice by hand is two strings that drift on the first edit, so ``utils.py`` derives the
second from the first and this shape carries both, each named for the text it runs over. Where a
pattern holds no tone mark at all the two are equal and the scan sees one hit twice: layer one is
tuned for recall and is *allowed* to be noisy, and layer two is what sets precision.

**A display config is a fragment and the task data this half owns.** Neither half of the annotation
config may emit the other's (Requirement 31), so what is here is the ``<Paragraphs>`` tag and the one
``conversation`` key that feeds it. The fragment *reads* one key it does not own -- ``$question`` --
because rendering the question is the display half's job and writing it is
``tool_decision.question_text``'s; ``$tool_names`` is the capture half's on both counts. So neither
config half carries a complete payload, and the module that assembles one out of both is ``publish``
(T24).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Detector(BaseModel):
    """One high-recall pattern, in both the spellings layer one scans."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(
        ...,
        description=(
            "What this detector finds, for the report and for tuning it. Distinct "
            "across the layer, so a noisy one can be named in a diff."
        ),
    )
    personal_data_class: str = Field(
        ...,
        description=(
            "The typed class of a hit, which is what picks the placeholder "
            "(`<CUSTOMER_ID_1>`) and what the corpus-level report counts."
        ),
    )
    pattern: str = Field(
        ...,
        description=(
            "The regular expression over the raw text, written in correct Vietnamese."
        ),
    )
    tone_stripped_pattern: str = Field(
        ...,
        description=(
            "The same expression over `normalize_text(text, remove_tone_marks=True)`, "
            "derived from `pattern` so a pattern is written once."
        ),
    )


class DisplayConfig(BaseModel):
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
