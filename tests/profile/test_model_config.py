"""The two ways a model's config is not one this deployment can act on, proved in both classes.

Requirement 26 and Decision 10 are one rule, and every class that asks a model now states it
itself: the confirmation in the modality, the model detector in the profile. So the tests are
parametrised over both -- there is no one function left to prove it against, and a rule written
twice is a rule that can rot in one place while the other still passes.

What the *merge* does is the library's own and is not restated. What these say is that the
declaration a request carried is handed over, and that a config with no endpoint is refused when
the class is built rather than sent to a provider's default.

Asking itself is proved in `test_personal_data.py`: what a failed call or an answer of the wrong
shape comes to is a rule about the step that asked.
"""

from types import ModuleType
from typing import Any

import pytest
from agent_toolkit.llm import LLMConfig
from agent_toolkit.llm.exceptions import LLMConfigError

from dataforce.errors import ConfigError
from dataforce.modalities.text2text.data_quality import (
    PiiLlmConfirmer,
    personal_data_checking,
)
from dataforce.modalities.text2text.data_quality.schema import VerifierModelConfig
from dataforce.profile.tool_decision import data_quality
from dataforce.profile.tool_decision.data_quality import PiiLlmDetector

MODEL = "a-verifier"

# Each class resolves its own model, so each is patched where it calls the library.
ASKING = [
    pytest.param(PiiLlmConfirmer, personal_data_checking, id="confirmer"),
    pytest.param(PiiLlmDetector, data_quality, id="detector"),
]


@pytest.mark.parametrize(("asking", "module"), ASKING)
def test_the_declaration_a_request_carried_is_what_the_library_is_handed(
    monkeypatch: pytest.MonkeyPatch, asking: Any, module: ModuleType
) -> None:
    """Decision 10, explicit first. The precedence is the library's; the handing over is ours.

    Whatever the part's own `<X>ModelConfig` carries goes over the file's value, and the file
    answers for the rest -- so a `None` has to reach `resolve_config` as `None`. Dropped instead,
    it would be the file's value winning over an endpoint the request named.
    """
    asked: dict[str, Any] = {}

    def resolving(**kwargs: Any) -> LLMConfig:
        asked.update(kwargs)
        return LLMConfig(model=MODEL, base_url="http://from-the-file.invalid/v1")

    monkeypatch.setattr(module, "resolve_config", resolving)

    step = asking(VerifierModelConfig(model=MODEL, api_key="the-key"))

    assert asked == {"model": MODEL, "api_key": "the-key", "base_url": None}
    assert step.model.base_url == "http://from-the-file.invalid/v1"


@pytest.mark.parametrize(("asking", "module"), ASKING)
def test_the_settings_a_part_declared_are_the_step_s_own(
    monkeypatch: pytest.MonkeyPatch, asking: Any, module: ModuleType
) -> None:
    """They are the provider's to read, so they are held beside the config and not merged into it.

    A part that declares none is a model asked with none, never a `None` unpacked into the call.
    """
    monkeypatch.setattr(
        module,
        "resolve_config",
        lambda **kwargs: LLMConfig(model=MODEL, base_url="http://a-model.invalid/v1"),
    )

    declared = VerifierModelConfig(model=MODEL, settings={"temperature": 0.0})

    assert asking(declared).settings == {"temperature": 0.0}
    assert asking(VerifierModelConfig(model=MODEL)).settings == {}


@pytest.mark.parametrize(("asking", "module"), ASKING)
@pytest.mark.parametrize("declared", [None, ""], ids=["none", "empty"])
def test_a_model_with_no_endpoint_is_refused_before_the_call(
    monkeypatch: pytest.MonkeyPatch,
    asking: Any,
    module: ModuleType,
    declared: str | None,
) -> None:
    """Requirement 26: a name with no file and no explicit URL is a configuration error.

    Never a default. A provider's own default endpoint is a call to somewhere nobody declared, and
    the deployment that keeps its endpoint in the environment reads as exactly this case.
    """
    monkeypatch.setattr(
        module,
        "resolve_config",
        lambda **kwargs: LLMConfig(model=MODEL, base_url=declared),
    )

    with pytest.raises(ConfigError, match="base_url"):
        asking(VerifierModelConfig(model=MODEL))


@pytest.mark.parametrize(("asking", "module"), ASKING)
def test_a_name_the_resolver_cannot_read_is_refused_as_a_configuration_error(
    monkeypatch: pytest.MonkeyPatch, asking: Any, module: ModuleType
) -> None:
    """The library's own error, as this codebase's one exception, so a handler answers 422.

    `LLMError` and not `ToolkitError`: the library's LLM errors are their own hierarchy, so
    catching the wrong root lets a missing config file out as a 500.
    """

    def unreadable(**kwargs: Any) -> LLMConfig:
        raise LLMConfigError(f"no usable LLM config at config/model/{MODEL}.json")

    monkeypatch.setattr(module, "resolve_config", unreadable)

    with pytest.raises(ConfigError, match=MODEL):
        asking(VerifierModelConfig(model=MODEL))
