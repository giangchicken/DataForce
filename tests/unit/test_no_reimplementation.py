"""The library is not re-implemented, and cannot be by accident.

A helper added under deadline is how a codebase acquires a second JSONL writer,
and the second one is the one that is not atomic. Everything below has exactly one
implementation, in `agent-toolkit`, and a module that grows its own fails here.
"""

from __future__ import annotations

import ast
import re

from conftest import SOURCE_ROOT, parsed_sources

# What a re-implementation tends to be called, and what to use instead.
REIMPLEMENTED = {
    r"^_?(compute_)?(sha256|sha1|md5|hash)(_\w+)?$": "string_utils.compute_hash",
    r"^_?(read|write|load|dump|save)_json_?lines?$": "file_utils.read_jsonlines / write_jsonlines",
    r"^_?atomic_write(_\w+)?$": "file_utils writes atomically already",
    r"^_?(extract|parse)_json(_from_text)?$|^_?loads_repair$": "string_utils.extract_json_from_text",
    r"^_?(slot_fill\w*|fill_template|render_template)$": "string_utils.slot_filling",
    r"^_?(with_)?retry(_\w+)?$|^_?backoff$": "llm.complete retries and rate-limits already",
}

# Dependencies the library owns. The pipeline talks to it, not to them.
NOT_OURS = frozenset({"openai", "tenacity", "tiktoken", "jsonschema"})


def reimplementations(tree: ast.Module) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for pattern, instead in REIMPLEMENTED.items():
            if re.match(pattern, node.name):
                found.append(f"{node.name}() -- use {instead}")
    return found


def foreign_imports(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots & NOT_OURS


def test_no_module_re_implements_a_toolkit_function() -> None:
    scanned = 0
    for path, tree in parsed_sources():
        scanned += 1
        found = reimplementations(tree)
        assert not found, f"{path.relative_to(SOURCE_ROOT)}: {found}"
    assert scanned, "no module was scanned -- this test would pass vacuously"


def test_no_module_imports_a_dependency_the_library_owns() -> None:
    for path, tree in parsed_sources():
        found = foreign_imports(tree)
        assert not found, (
            f"{path.relative_to(SOURCE_ROOT)} imports {sorted(found)}; "
            "reach it through agent_toolkit instead"
        )


def test_the_check_catches_a_second_hash_helper() -> None:
    offending = ast.parse("def sha256(text):\n    return text\n")
    assert reimplementations(offending)

    also = ast.parse("def write_jsonlines(path, rows):\n    return None\n")
    assert reimplementations(also)

    innocent = ast.parse("def compute_rid(parts):\n    return None\n")
    assert not reimplementations(innocent)


def test_the_check_catches_a_direct_provider_import() -> None:
    assert foreign_imports(ast.parse("import tiktoken\n")) == {"tiktoken"}
    assert foreign_imports(ast.parse("from jsonschema import validate\n")) == {
        "jsonschema"
    }
    assert not foreign_imports(ast.parse("from agent_toolkit.llm import complete\n"))
