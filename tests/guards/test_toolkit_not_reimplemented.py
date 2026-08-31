"""I6 · nothing re-implements an `agent-toolkit` function, or imports a dependency it owns.

The library is pinned to a git tag and exists because these things were written once already. A
second `compute_hash` here is not a duplicate function, it is a second definition of what a
`record_id` *is*, and the two drift on the first bug fixed in one of them.

**The owned names are read off the installed library, not off a list kept here.** They were a
hand-written tuple until this commit, and that tuple and the spec's sentence agreed with each other
while both disagreed with `agent-toolkit`: seventeen exported functions appeared in neither, among
them `split_thinking`, `read_json` and `get_logger`, and nothing would have stopped a module here
from defining one. A pairing over two hand-maintained copies of a fact proves the copies match;
it cannot prove either is *true*. The third party -- the library a run actually imports -- is the
only thing that can say, and it was the one party the rule never asked.

*Installed* is the load-bearing word. The pin is `@v0.2.0` and the checkout beside this repository
is not: what `uv.lock` resolved is what `import agent_toolkit` gets, so that is what the rule is
written against. A tag that moves under a name this package defines shows up here as a red guard
rather than as a function that quietly stopped being ours -- and T54 is the case: the four
personal-data scans became owned names the day that pin moved, and the rule covered them without an
edit here.

**One level deep, and functions only.** `pkgutil.iter_modules` reaches the package's front doors --
`string_utils`, `file_utils`, `json_utils`, `llm` -- and not `llm/executors.py`, whose `__all__` is
that module's own surface rather than the library's; `sdk_complete` is importable but is not a name
`agent-toolkit` offers, and denying it here would be the rule overreaching into someone's internals.
Functions only because the finding is a `def`: `ToolkitError` is a class and `DEFAULT_BUFFER_SIZE`
is a value, and neither is a way to re-implement anything.

The owned roots are `agent-toolkit`'s own dependencies, and reaching past the library to one of
them is how the re-implementation starts: `yaml` because it reads the manifests, `openai` and
`tiktoken` because it is the LLM client, `jsonschema` because it owns validation. `jsonschema` is a
dev dependency here and is used by the tests that prove `answer_schema` means what it says -- this
guard is what keeps it out of `src/`.

`hashlib` is on a second list, and deliberately not on the first: it is the standard library, not
a root `agent-toolkit` owns, and the library reaches for it itself. It is scanned because it is the
one import that makes a second `compute_hash` possible without naming one -- and since T8 that
function *is* the definition of a `record_id`, so a digest computed any other way is a second answer
to what a record is called. A digest over **bytes** is a real need the first media modality will
have, since `compute_hash` takes a `str`; that is what the exemption hatch is for, annotated on the line
rather than by widening the rule for everyone.

Importing the library is not a finding. Naming one of its functions as a `def` is.
"""

import ast
import importlib
import inspect
import pkgutil
import re
from pathlib import Path

import pytest

from .tree import Module, imports, module_from_source, modules_in, not_exempt

LIBRARY = "agent_toolkit"
OWNED_ROOTS = ("jsonschema", "openai", "tiktoken", "yaml")
RE_IMPLEMENTATION_ROOTS = ("hashlib",)

SPEC = Path(__file__).resolve().parents[2] / "docs" / "annotation-pipeline" / "spec.md"
OWNERSHIP = re.compile(
    r"\*\*What `agent-toolkit` already owns\*\* and must not be re-implemented:.*?\n\n",
    re.DOTALL,
)
# Named in that sentence and not exported functions: the library itself, an argument to
# `normalize_text`, and the mechanism this guard reads.
NOT_FUNCTIONS = {"agent-toolkit", "remove_tone_marks", "__all__"}


def owned_functions() -> frozenset[str]:
    """Every function the installed `agent-toolkit` exports from a front door."""
    package = importlib.import_module(LIBRARY)
    facades = [package] + [
        importlib.import_module(f"{LIBRARY}.{found.name}")
        for found in pkgutil.iter_modules(package.__path__)
    ]
    return frozenset(
        name
        for facade in facades
        for name in getattr(facade, "__all__", ())
        if inspect.isfunction(getattr(facade, name, None))
    )


OWNED_FUNCTIONS = owned_functions()


def toolkit_findings(module: Module) -> list[str]:
    """Every function this module defines that the library already owns, and every root it skips to."""
    found = [
        (node.lineno, f"re-implements agent-toolkit's {node.name}()")
        for node in ast.walk(module.tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name in OWNED_FUNCTIONS
    ]
    found += [
        (reached.line, f"imports {reached.module}, which agent-toolkit owns")
        for reached in imports(module)
        if reached.module.split(".")[0] in OWNED_ROOTS
    ]
    found += [
        (reached.line, f"imports {reached.module}: a second compute_hash starts here")
        for reached in imports(module)
        if reached.module.split(".")[0] in RE_IMPLEMENTATION_ROOTS
    ]
    return not_exempt(module, "I6", found)


@pytest.mark.parametrize("module", modules_in(), ids=lambda m: m.name)
def test_no_module_re_implements_the_library(module: Module) -> None:
    """I6, over the whole package. The edge reads files too, and reads them through the library."""
    assert toolkit_findings(module) == []


@pytest.mark.parametrize(
    "violation",
    [
        "def compute_hash(content):\n    return content",
        "async def complete(prompt):\n    return prompt",
        "def normalize_text(text, remove_tone_marks=False):\n    return text",
        "def split_thinking(text):\n    return text, ''",
        "def read_json(path):\n    return {}",
        "class Reader:\n    def read_yaml(self, path):\n        return {}",
        "import yaml",
        "from yaml import safe_load",
        "import jsonschema",
        "from openai import OpenAI",
        "import tiktoken",
        "import hashlib",
        "from hashlib import sha256",
        "import hashlib\n\n\ndef record_digest(text):\n    return hashlib.sha256(text).hexdigest()[:16]",
    ],
    ids=[
        "compute_hash",
        "async-complete",
        "normalize_text",
        "split_thinking",
        "read_json",
        "method",
        "yaml",
        "from-yaml",
        "jsonschema",
        "openai",
        "tiktoken",
        "hashlib",
        "from-hashlib",
        "a-second-record-id",
    ],
)
def test_the_scan_rejects_a_module_that_does_the_library_s_job(violation: str) -> None:
    """Proved red against a synthetic violation, one per root and one per shape of name.

    `split_thinking` and `read_json` are the two the hand-written tuple let through, kept here as
    the standing proof that the derivation is what makes them findings.
    """
    assert toolkit_findings(module_from_source(violation)) != []


@pytest.mark.parametrize(
    "permitted",
    [
        "from agent_toolkit.string_utils import compute_hash",
        "from agent_toolkit.file_utils import read_yaml, write_jsonlines",
        "from agent_toolkit.llm import complete_structured",
        "def sdk_complete(prompt):\n    return prompt",
    ],
    ids=["hash", "files", "llm", "not-a-front-door"],
)
def test_the_scan_permits_using_the_library(permitted: str) -> None:
    """The rule is against a second implementation of what the library *offers*.

    `sdk_complete` is in `llm/executors.py`'s `__all__` and in no façade's, so it is that module's
    business and not a name this package is forbidden. The rule stops where the library's public
    surface does.
    """
    assert toolkit_findings(module_from_source(permitted)) == []


def test_an_annotated_exemption_covers_a_digest_over_bytes() -> None:
    """`compute_hash` takes a `str`, so the first media part's sha256 has nowhere else to go."""
    excused = (
        "import hashlib"
        "  # guard-exempt: I6 · a media digest is over bytes · the modality · 2026-08-24"
    )

    assert toolkit_findings(module_from_source(excused)) == []


def test_the_derivation_reads_the_library_it_is_supposed_to_find() -> None:
    """Guards the discovery: a derivation that resolved nothing would pass every module above.

    The four positives are one per front door. `split_thinking` is the regression: it is what the
    tuple missed, and its presence here is what says the rule now comes from the library.
    """
    assert {"compute_hash", "read_yaml", "iter_json_array", "complete_structured"} <= (
        OWNED_FUNCTIONS
    )
    assert "split_thinking" in OWNED_FUNCTIONS
    assert "ToolkitError" not in OWNED_FUNCTIONS, "a class is not a way to write a def"
    assert "DEFAULT_BUFFER_SIZE" not in OWNED_FUNCTIONS, "nor is a constant"
    assert "sdk_complete" not in OWNED_FUNCTIONS, "llm/executors.py is not a front door"


def test_the_document_claims_nothing_the_library_does_not_own() -> None:
    """The comparison, in the one direction that is still the document's to get wrong.

    That sentence was compared for *equality* against a tuple in this file, which is what let the
    two of them be wrong together. Completeness belongs to the library now, so what is left for the
    document is accuracy: every name it tells a reader not to re-implement has to be a name
    `agent-toolkit` really exports, or the sentence sends someone looking for a function that was
    renamed or removed. `NOT_FUNCTIONS` names the three exceptions rather than filtering by a rule
    that would also swallow a real omission.
    """
    sentence = OWNERSHIP.search(SPEC.read_text(encoding="utf-8"))

    assert sentence, "spec.md § *Context* no longer says what agent-toolkit owns"
    named = set(re.findall(r"`([A-Za-z_][\w-]*)`", sentence[0]))
    assert named - NOT_FUNCTIONS <= OWNED_FUNCTIONS
