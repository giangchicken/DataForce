"""I21 · each axis protocol has the members its section of the document writes down.

`Modality` and `Profile` are written three times: as a `Protocol` block in `spec.md`, as a count in
words in that section *and* in the module's own docstring -- "Six members, closed" -- and as the
class itself. Three statements, and until this guard nothing compared any two of them (P31).

**The names are compared, not only the count.** A renamed member keeps the count and breaks every
implementation, which is the drift worth catching; the count is compared as well because the word
is what a reader believes, and a word is exactly the thing nobody updates.

*Closed* is the claim being checked. Both axes are meant to be a fixed set of members that an
implementation answers in full -- Requirement 47's opaque types exist so the set can stay small --
so a member appearing in the class and not in the document is as much a finding as the reverse.
"""

import ast
import re

import pytest

from dataforce.modalities import Modality
from dataforce.profiles import Profile

from .tree import SPEC, SRC, module_at

# The document writes its counts in words, and so do the two modules. A word this tuple does not
# know fails loudly rather than being skipped -- a silent skip is how the count stops being checked.
NUMBER_WORDS = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
)
COUNT = re.compile(r"\b(\w+) members, closed\b")

AXES = [
    pytest.param("modalities", "### Modality", Modality, id="modality"),
    pytest.param("profiles", "### Profile", Profile, id="profile"),
]


def section(heading: str) -> str:
    """One § of the document, up to the next heading of the same depth."""
    text = SPEC.read_text(encoding="utf-8")
    start = text.index(heading)
    return text[start : text.index("\n### ", start + 1)]


def drawn_members(heading: str) -> set[str]:
    """The protocol as the document writes it: its annotated attributes and its defs."""
    block = section(heading).split("```python")[1].split("```")[0]
    declared = next(
        node for node in ast.parse(block).body if isinstance(node, ast.ClassDef)
    )
    return {
        node.target.id if isinstance(node, ast.AnnAssign) else node.name
        for node in declared.body
        if isinstance(node, ast.AnnAssign | ast.FunctionDef)
        and isinstance(getattr(node, "target", None), ast.Name | type(None))
    }


def stated_count(text: str) -> int:
    """The number a "<word> members, closed" sentence states, as a number."""
    written = COUNT.search(text)

    assert written, f"no '<word> members, closed' sentence in: {text[:60]}…"
    return NUMBER_WORDS.index(written[1].lower())


@pytest.mark.parametrize(("axis", "heading", "protocol"), AXES)
def test_the_protocol_has_the_members_the_document_writes(
    axis: str, heading: str, protocol: type
) -> None:
    """I21: a member renamed, added or dropped on one side only."""
    assert set(protocol.__protocol_attrs__) == drawn_members(heading)


@pytest.mark.parametrize(("axis", "heading", "protocol"), AXES)
def test_the_count_in_the_document_is_the_number_of_members(
    axis: str, heading: str, protocol: type
) -> None:
    """ "Six members, closed" is a fact about the code, so it is compared to the code."""
    assert stated_count(section(heading)) == len(protocol.__protocol_attrs__)


@pytest.mark.parametrize(("axis", "heading", "protocol"), AXES)
def test_the_count_in_the_module_docstring_is_the_same_number(
    axis: str, heading: str, protocol: type
) -> None:
    """The third statement, and the one a reader of `base.py` sees without opening the spec."""
    docstring = ast.get_docstring(module_at(SRC / axis / "base.py").tree) or ""

    assert stated_count(docstring) == len(protocol.__protocol_attrs__)


def test_the_parser_found_a_protocol_and_not_an_empty_class() -> None:
    """Guards the parse: an empty set on both sides would make the comparison vacuous."""
    assert len(drawn_members("### Modality")) == 6
    assert "content_parts" in drawn_members("### Modality")
    assert "answer_from_response" in drawn_members("### Profile")


@pytest.mark.parametrize(
    ("drawn", "reason"),
    [
        (
            "class Modality(Protocol):\n    name: str",
            "a member the class has and the document lost",
        ),
        (
            "class Modality(Protocol):\n"
            "    name: str\n    version: str\n"
            "    def content_parts(self): ...\n"
            "    def embedding(self): ...\n"
            "    def personal_data_detectors(self): ...\n"
            "    def display_config(self): ...\n"
            "    def transcribe(self): ...\n",
            "a member the document gained and the class did not",
        ),
    ],
    ids=["dropped", "added"],
)
def test_the_scan_rejects_a_protocol_that_drifted(drawn: str, reason: str) -> None:
    """P29, both directions, against a synthetic block rather than by editing the document."""
    declared = next(
        node for node in ast.parse(drawn).body if isinstance(node, ast.ClassDef)
    )
    members = {
        node.target.id if isinstance(node, ast.AnnAssign) else node.name
        for node in declared.body
        if isinstance(node, ast.AnnAssign | ast.FunctionDef)
    }

    assert members != set(Modality.__protocol_attrs__), reason


def test_the_scan_rejects_a_count_that_no_longer_matches() -> None:
    """P29 for the word: "Five members, closed" over six members."""
    assert stated_count("Five members, closed.") != len(Modality.__protocol_attrs__)
