"""I6 · nothing re-implements an `agent-toolkit` function, or imports a dependency it owns.

The library is pinned to a git tag and exists because these things were written once already. A
second `compute_hash` here is not a duplicate function, it is a second definition of what a
`record_id` *is*, and the two drift on the first bug fixed in one of them.

The owned roots are `agent-toolkit`'s own dependencies, and reaching past the library to one of
them is how the re-implementation starts: `yaml` because it reads the manifests, `openai` and
`tiktoken` because it is the LLM client, `jsonschema` because it owns validation. `jsonschema` is a
dev dependency here and is used by the tests that prove `answer_schema` means what it says -- this
guard is what keeps it out of `src/`.

Importing the library is not a finding. Naming one of its functions as a `def` is.
"""

import ast
import re
from pathlib import Path

import pytest

from .tree import Module, imports, module_from_source, modules_in, not_exempt

OWNED_FUNCTIONS = (
    "compute_hash",
    "complete",
    "complete_structured",
    "count_tokens",
    "extract_json_from_text",
    "normalize_text",
    "read_jsonlines",
    "read_yaml",
    "slot_filling",
    "write_jsonlines",
)
OWNED_ROOTS = ("jsonschema", "openai", "tiktoken", "yaml")

SPEC = Path(__file__).resolve().parents[2] / "docs" / "annotation-pipeline" / "spec.md"
OWNERSHIP = re.compile(
    r"\*\*What `agent-toolkit` already owns\*\* and must not be re-implemented:.*?\n\n",
    re.DOTALL,
)


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
        "class Reader:\n    def read_yaml(self, path):\n        return {}",
        "import yaml",
        "from yaml import safe_load",
        "import jsonschema",
        "from openai import OpenAI",
        "import tiktoken",
    ],
    ids=[
        "compute_hash",
        "async-complete",
        "normalize_text",
        "method",
        "yaml",
        "from-yaml",
        "jsonschema",
        "openai",
        "tiktoken",
    ],
)
def test_the_scan_rejects_a_module_that_does_the_library_s_job(violation: str) -> None:
    """P29: proved red against a synthetic violation, one per name and one per root."""
    assert toolkit_findings(module_from_source(violation)) != []


@pytest.mark.parametrize(
    "permitted",
    [
        "from agent_toolkit.string_utils import compute_hash",
        "from agent_toolkit.file_utils import read_yaml, write_jsonlines",
        "from agent_toolkit.llm import complete_structured",
    ],
    ids=["hash", "files", "llm"],
)
def test_the_scan_permits_using_the_library(permitted: str) -> None:
    """The rule is against a second implementation, not against the dependency."""
    assert toolkit_findings(module_from_source(permitted)) == []


def test_the_owned_names_are_the_ones_the_document_lists() -> None:
    """P31: the list above is the spec's sentence, not a second opinion about it.

    Two names in that sentence are not functions and are named as exceptions here rather than
    filtered by a rule that would also swallow a real omission: `agent-toolkit` is the library and
    `remove_tone_marks` is an argument to `normalize_text`.
    """
    sentence = OWNERSHIP.search(SPEC.read_text(encoding="utf-8"))

    assert sentence, "spec.md § *Context* no longer says what agent-toolkit owns"
    named = set(re.findall(r"`([A-Za-z_][\w-]*)`", sentence[0]))
    assert named - {"agent-toolkit", "remove_tone_marks"} == set(OWNED_FUNCTIONS)
