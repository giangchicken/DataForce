"""§9 · the file that names an endpoint and holds a key is ignored, and the example beside it is not.

`config/model/<model>.json` is where a deployment attaches the embedder `duplicate_check` groups
through -- `base_url` and `api_key`, which is exactly the pair AGENTS.md §9 forbids a public
repository to carry. So the file is git-ignored and a `<model>.json.example` is what ships.

**The ignore rule is over the files and not the directory**, which is the part worth a test: git
cannot re-include anything under an excluded *directory*, so `config/model/` would have taken the
example down with the keys, and the failure would have been silent -- a checkout with no example, an
engine that refuses to compose, and nothing saying which file to write. The pattern below is the fix
and this is what holds it.

**And the example has to stay a usable file.** `JsonDirConfigResolver` ignores keys it does not know,
so an example with a renamed field reads as an example with the field missing. `tests/shells` composes
the shipped configuration through it and would catch that; this states the smaller thing that has to
be true first -- that it names the three fields, and that none of them is real.
"""

from pathlib import Path

from agent_toolkit.file_utils import read_json

from .tree import SRC

ROOT = SRC.parents[1]
ATTACHED = ROOT / "config" / "model"
GITIGNORE = ROOT / ".gitignore"
IGNORED = "config/model/*.json"
EXAMPLE = "*.json.example"
# What the endpoint file says, and the whole of what `edge/bootstrap.py` reads out of it.
READ = ("model", "base_url", "api_key")
# The reserved TLD, which is the one hostname §9 permits a committed file: it resolves nowhere.
NOWHERE = ".invalid/"


def examples() -> list[Path]:
    """Every endpoint example the repository ships, which is what a deployment copies."""
    return sorted(ATTACHED.glob(EXAMPLE))


def test_the_endpoint_file_is_ignored_by_a_pattern_that_lets_the_example_through() -> (
    None
):
    """The rule is over `*.json`, because ignoring the directory would ignore the example too."""
    ignored = GITIGNORE.read_text(encoding="utf-8")

    assert f"\n{IGNORED}\n" in ignored
    assert "config/model/\n" not in ignored, (
        "a directory rule takes the example down with it"
    )


def test_an_example_ships_and_names_what_the_edge_reads() -> None:
    """A deployment with no example has to be told the three fields by someone."""
    assert examples(), f"nothing matching {EXAMPLE} under config/model/"
    for example in examples():
        declared = read_json(example)

        assert all(field in declared for field in READ), example.name


def test_no_example_carries_a_key_or_a_reachable_endpoint() -> None:
    """§9, and the reason the real file is ignored: a placeholder is the only thing that may ship."""
    for example in examples():
        declared = read_json(example)

        assert NOWHERE in declared["base_url"], example.name
        assert " " in declared["api_key"], (
            f"{example.name} carries something key-shaped"
        )
