"""logic · what this task's label can be measured by.

Every measurement here says `tool`, which is why none of them is the modality's.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from agent_toolkit.string_utils import extract_json_from_text

from .utils import list_required_parameters, read_named_function


def list_called_tools(label: Sequence[Any] | None) -> tuple[str, ...]:
    """The tool names one label calls, in the order it calls them.

    An entry that names no tool is left out: it is not a call, and `validate_label_calls` is what
    says the row is broken.
    """
    called = (read_named_function(entry) for entry in label or ())
    return tuple(function["name"] for function in called if function is not None)


def read_call_arguments(function: Mapping[str, Any]) -> Mapping[str, Any]:
    """What one call supplies, whether it wrote its arguments as an object or as JSON text."""
    arguments = function.get("arguments")
    if isinstance(arguments, str):
        arguments = extract_json_from_text(arguments)
    return arguments if isinstance(arguments, Mapping) else {}


def validate_label_calls(label: Sequence[Any] | None, catalog: Sequence[Any]) -> bool:
    """Whether every call names a tool this row was offered and supplies its required params.

    BFCL's AST check turned on the corpus rather than on a model: a label calling a tool the
    sample never offered is a broken row, not a hard example. An empty label is valid.
    """
    required_by_tool: dict[str, set[str]] = {}
    for offered in catalog:
        function = read_named_function(offered)
        if function is None:
            continue
        parameters = function.get("parameters") or {}
        # A tool whose parameters will not read is a tool no call can be cleared against, so it
        # is left out of the catalog here and a call naming it is invalid.
        if isinstance(parameters, Mapping):
            required_by_tool[function["name"]] = list_required_parameters(parameters)
    for entry in label or ():
        called = read_named_function(entry)
        if called is None or called["name"] not in required_by_tool:
            return False
        if not required_by_tool[called["name"]] <= set(read_call_arguments(called)):
            return False
    return True


def count_tool_calls(
    labels: Sequence[Sequence[Any] | None], catalogs: Sequence[Sequence[Any]]
) -> Mapping[str, int]:
    """Every tool the corpus offers, and how many calls each of them carries.

    **The zeros are the finding**, the same way an empty cell of the joint distribution matrix is: a tool
    offered a thousand times and never called is a tool the corpus cannot teach. The tail is the
    other half -- two tools carrying most of the calls trains a model that knows two tools.

    A tool called without ever being offered is in here too, with its count. Nothing drops it;
    `schema_valid` is what marks the row that made that call.
    """
    counted: Counter[str] = Counter()
    for label, catalog in zip(labels, catalogs, strict=True):
        offered = (read_named_function(entry) for entry in catalog)
        counted.update(
            {function["name"]: 0 for function in offered if function is not None}
        )
        counted.update(list_called_tools(label))
    return dict(sorted(counted.items()))


def list_offered_tools(catalogs: Sequence[Sequence[Any]]) -> tuple[str, ...]:
    """Every distinct tool the catalogs put in front of the model, sorted.

    Counted apart from `count_tool_calls`'s keys, which also hold a tool a label named without ever
    being offered. That is a broken row's invention, not an offer, and letting it into this figure
    would inflate the number the zeros are read against.

    `read_named_function` rather than a second reading of what an offered tool is, so the check, the
    rendered catalog and this figure cannot disagree about what the model was shown.
    """
    offered = (read_named_function(entry) for catalog in catalogs for entry in catalog)
    return tuple(
        sorted({function["name"] for function in offered if function is not None})
    )
