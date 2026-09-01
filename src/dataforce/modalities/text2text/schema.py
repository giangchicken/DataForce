"""DEFINITION · the text2text shape: what a detector is.

One shape, and it exists because ``modalities/base.py`` refuses to name it: ``Detector`` is an alias
for ``Any`` there and is this model here (Requirement 47). A stage reads one structurally --
``pipeline/`` may not import this module (I2) -- so every field is named for what a reader does with
it rather than for how this modality happens to hold it.

**A detector is a class name and the scan that finds it.** Requirement 18 puts layer one in
``agent-toolkit``: each of the four scans finds the written form *and* the dictated one, and each
pattern behind one already carries the toned and the tone-stripped spelling, so one pass over the
raw text catches ``khong chin`` and ``không chín`` both. This shape carried two patterns until the
library shipped them; what is left for the modality is the vocabulary its hits are recorded under --
``PHONE``, ``EMAIL``, ``OTP``, ``NAME`` -- and the scan is bound to the declared language before it
gets here, so a stage that may not read a manifest does not have to.
"""

from collections.abc import Callable

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
