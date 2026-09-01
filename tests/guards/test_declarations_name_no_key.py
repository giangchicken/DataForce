"""I25 · `declarations.py` names no manifest key.

The two axes each had their own copy of the manifest reader, and the reason was written down in both:
§ *The two axes* says they share `name`, `version` and `Part` *and nothing else*, so a shared reader
is a fourth shared thing -- and the first key one axis needed and the other did not would put a
profile's vocabulary in a module the modality imports. T56 removed the copies, and this is what pays
for that: the objection is answered by the **signature**, and a signature is a promise until a test
reads it.

`declaration`, `declared_name`, `declared_count` and `declared_roles` take `*path: str`. A key
reaches them from the axis that means it, so there is nothing in that module for either axis to learn
about the other -- and the day someone writes `if path == (EMBEDDING, MODEL)` in there to special-case
one of them, the seam is back and this goes red.

**The vocabulary is derived, not listed.** It is every string either axis assigns to a module-level
constant, read off the tree the same way I6 reads the installed library: a hand-kept list here would
be a second statement of what the axes' keys are, and the two would drift in the direction that makes
this rule vacuous. It is generous on purpose -- `TURN_SEPARATOR`'s `"\\n\\n"` and `CAPTURE_TAGS`'
markup are in it too. Everything an axis names as a constant is that axis's vocabulary, and none of
it belongs in a reader both of them import.

**Docstrings are not literals for this purpose.** The rule is about what the module *reads*, and
prose naming a key as an example is how the module explains itself -- the docstring above names
`EMBEDDING` and `MAX_CALLS` doing exactly that.
"""

import ast

import pytest

from .tree import SRC, Module, axis_implementations, module_at, module_from_source

DECLARATIONS = SRC / "declarations.py"


def axis_vocabulary() -> frozenset[str]:
    """Every string either axis package assigns to a module-level constant."""
    return frozenset(
        node.value.value
        for package in axis_implementations()
        for path in sorted(package.glob("*.py"))
        for node in module_at(path).tree.body
        if isinstance(node, ast.Assign | ast.AnnAssign)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def written_strings(module: Module) -> list[tuple[int, str]]:
    """Every string literal this module holds, by line, with its docstrings left out.

    A docstring is a bare string *statement*, so what is skipped is every string an `Expr` holds --
    which is the same set and needs no scope walk. Matching on the text would skip a real literal
    that happened to read like one of the module's own sentences.
    """
    documentation = {
        id(node.value) for node in ast.walk(module.tree) if isinstance(node, ast.Expr)
    }
    return [
        (node.lineno, node.value)
        for node in ast.walk(module.tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in documentation
    ]


def key_findings(module: Module, vocabulary: frozenset[str]) -> list[str]:
    """Every string this module writes down that is one axis's word rather than both axes'."""
    return [
        f"{module.name}:{line} writes {written!r}, which is one axis's vocabulary"
        for line, written in written_strings(module)
        if written in vocabulary
    ]


def test_the_derivation_reads_the_keys_it_is_supposed_to_find() -> None:
    """Guards the discovery: an empty vocabulary would pass anything written in that module."""
    vocabulary = axis_vocabulary()

    assert {"embedding", "model", "language", "exclude_roles"} <= vocabulary
    assert {"max_calls", "roles", "answer_control", "label"} <= vocabulary


def test_the_shared_reader_names_no_key_either_axis_declares() -> None:
    """I25. The four functions take `*path: str`, and this is what says they mean it."""
    assert key_findings(module_at(DECLARATIONS), axis_vocabulary()) == []


@pytest.mark.parametrize(
    "violation",
    [
        'EMBEDDING = "embedding"',
        'def declared_model(m):\n    return m.declarations["embedding"]',
        'def declaration(m, *path):\n    if path == ("max_calls",):\n        return 1\n    return None',
    ],
    ids=["a-key-constant", "a-key-read", "a-key-special-cased"],
)
def test_the_scan_rejects_a_reader_that_learns_one_axis_s_word(violation: str) -> None:
    """Proved red: the constant, the read, and the special case -- three ways the seam comes back."""
    assert key_findings(module_from_source(violation), axis_vocabulary()) != []


def test_the_scan_permits_the_words_a_reader_needs_of_its_own() -> None:
    """The directory it names and the message it raises are the reader's own, not an axis's."""
    permitted = (
        '"""LOGIC · one declaration."""\n\n'
        'MODALITIES = "config/modalities/"\n\n\n'
        "def declared(m, *path):\n"
        "    raise ValueError(f\"{MODALITIES}{m.name}.yaml declares no {'.'.join(path)}\")"
    )

    assert key_findings(module_from_source(permitted), axis_vocabulary()) == []


def test_a_docstring_may_name_a_key_it_is_explaining() -> None:
    """The rule is about what the module reads. Prose that names a key is how it explains itself."""
    explained = '"""LOGIC · a reader.\n\nThe vocabulary stays in the axis: embedding, max_calls.\n"""'

    assert key_findings(module_from_source(explained), axis_vocabulary()) == []
