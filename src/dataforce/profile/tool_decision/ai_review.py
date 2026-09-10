"""logic · which tool the two reviewers say this sample should call.

The prompt is built here, not in the modality: `tool_prediction.txt` asks for a tool call, and what
a juror is asked is the task's question. Each juror is handed the catalog, the conversation and
nothing else -- not the sample's label, because a model shown a label answers about the label.

What an answer here *is* also belongs to the task, and it is a tool call -- so every rule about
reading one lives in this package and not in `modalities/`, which serves any text2text task and
can know nothing about tools. `normalize_prediction` answers the modality's socket: it matches the
calls `text_to_openai_tool_format` read out of what a juror wrote, rather than comparing two
strings and hoping they were spelled alike. That is also why this task asks no judge -- two calls are the same call or they are
not, and no model is needed to say which. `llm_judge_consensus` is for a task whose answers can
only be compared as meaning.
"""

import json
from asyncio import gather
from collections.abc import Sequence
from pathlib import Path

from agent_toolkit.file_utils import read_txt
from agent_toolkit.llm import complete, resolve_config
from agent_toolkit.llm.exceptions import LLMError
from agent_toolkit.logging import get_logger
from agent_toolkit.string_utils import (
    extract_json_from_text,
    normalize_text,
    slot_filling,
)

from dataforce.errors import ConfigError
from dataforce.modalities.text2text.ai_review import (
    LLMPrediction,
    LLMReviewerAnswer,
    LLMReviewerVote,
    SFTPrediction,
    SFTReviewerVerdict,
)
from dataforce.modalities.text2text.ai_review.schema import LLMModelConfig

from .utils import openai_tool_format_to_text, text_to_openai_tool_format

# The deployment's, on the same terms as `config/model/`: read from the working directory and named
# for the step that sends it.
TOOL_PREDICTION_PROMPT = Path(
    "config/prompts/profiles/tool_decision/tool_prediction.txt"
)

logger = get_logger(__name__)


class ToolPredictor:
    """One juror: the model a request ticked, asked which tool this sample should call."""

    def __init__(self, config: LLMModelConfig) -> None:
        """The model resolved from what the request declared, or `ConfigError` before any record."""
        try:
            self.model = resolve_config(
                model=config.model_name,
                api_key=config.api_key,
                base_url=config.base_url,
            )
        except LLMError as error:
            raise ConfigError(f"{config.model_name}: {error}") from error
        if not self.model.base_url:
            raise ConfigError(
                f"{config.model_name}: no base_url in its config file and none passed,"
                " so there is no endpoint to ask"
            )
        self.settings = config.settings

    async def predict(self, prompt: str) -> LLMReviewerVote | None:
        """Its vote, or `None` where it did not answer. Never raises (Requirement 19).

        A failed call and an answer of the wrong shape come to the same thing -- a juror absent
        from the panel, rather than a vote with an empty label that then agrees with nothing --
        and both are one event naming this juror (`H-6`), so a panel that quietly shrank is
        readable from the output and not only from `label_agreement`.
        """
        try:
            resp_text = await complete(
                prompt,
                model=self.model.model,
                api_key=self.model.api_key,
                base_url=self.model.base_url,
                **self.settings,
            )
            validated_resp_text = LLMReviewerAnswer.model_validate(
                extract_json_from_text(resp_text)
            )

        except Exception as error:
            logger.warning(
                "tool_prediction_failed",
                extra={
                    "model": self.model.model,
                    "error": f"{type(error).__name__}: {error}",
                },
            )
            return None

        return LLMReviewerVote(
            model_name=self.model.model,
            reason=validated_resp_text.reason,
            label=validated_resp_text.label
            if isinstance(validated_resp_text.label, str)
            else json.dumps(validated_resp_text.label, ensure_ascii=False),
        )


class ToolDecisionLLMPrediction(LLMPrediction):
    """N jurors answering the sample's own question: which tool, with which arguments."""

    def __init__(self, config: LLMModelConfig | Sequence[LLMModelConfig]) -> None:
        super().__init__(config)
        self.tool_predictors = self.build_tool_predictors()

    def build_tool_predictors(self) -> tuple[ToolPredictor, ...]:
        """One asking class per juror, each resolving its model as the panel is built.

        Built with the panel and not per record, so a name with no config file and no endpoint is
        refused before the first sample rather than during it (Requirement 26).
        """
        return tuple(ToolPredictor(juror) for juror in self.jurors)

    async def predict(
        self, turns: Sequence[str], tools: Sequence[object], language: str
    ) -> Sequence[LLMReviewerVote]:
        """One vote per juror that answered, each asked once and shown no other juror's answer.

        One rendering for the whole panel, because no slot depends on which juror is asked, and
        the calls are made together because N jurors asked one after another is N times the wait
        for nothing. A juror that failed is dropped here and named on stdout by the class that
        asked it.
        """
        prompt = self.build_tool_prediction_prompt(turns, tools, language)
        predicted_results: tuple[LLMReviewerVote | None, ...] = tuple(
            await gather(*(juror.predict(prompt) for juror in self.tool_predictors))
        )
        return tuple(
            predicted_result
            for predicted_result in predicted_results
            if predicted_result is not None
        )

    def normalize_prediction(self, pred_text: str) -> str:
        """The calls in one answer, as the text two answers are matched by.

        An answer to this task is an array of tool calls, so sameness is structural rather than a
        judgement, and this is why the panel needs no judge: `text_to_openai_tool_format` reads the
        calls out of whatever the model wrote, and two answers are one where those are the same
        calls. They are written back sorted, so two jurors that called the same tools with the same
        arguments in a different order gave one answer. A corpus whose calls must run in the order
        they were written is where that stops being true, and this is the line that would change.

        An answer with no call readable in it -- prose, or `[]`, which is the answer that no tool
        is needed -- is matched as what it says instead: the JSON it did write under one key
        ordering, and anything else by the library's own whitespace rule (`I6`). Never as the empty
        list of calls, which every other prose would also match.
        """
        norm_tools = sorted(
            json.dumps(call, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for call in text_to_openai_tool_format(pred_text)
        )
        if norm_tools:
            return f"[{','.join(norm_tools)}]"
        parsed_json = extract_json_from_text(pred_text)
        if parsed_json is not None:
            return json.dumps(
                parsed_json, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        return normalize_text(pred_text)

    async def judge_prediction(self, pred_texts: Sequence[str]) -> str | None:
        """`None`: this task asks no judge, and pays for no call to find that out.

        An answer here is a tool call, so `normalize_prediction` has already said whether two
        jurors said the same thing. A tie that survives it is two different calls -- not two
        spellings of one -- and a model picking between them would be the deciding vote, cast by a
        juror that never read the conversation (Decision 9). So the tie stands as no answer, which
        is what a panel that could not agree said. The socket is for a task whose answers can only
        be compared as meaning, where a summary said twice in different words is one answer.
        """
        return None

    def build_tool_prediction_prompt(
        self, turns: Sequence[str], tools: Sequence[object], language: str
    ) -> str:
        """`tool_prediction.txt` with its four slots filled, ready to send.

        The catalog, the turns before the last, the last turn, and the language the request
        declared. The sample's label is in none of them (Decision 12). `ConfigError` where the
        file is missing, so a deployment with no prompt is not a model having a bad day.
        """
        template = read_txt(TOOL_PREDICTION_PROMPT)
        if not template.strip():
            raise ConfigError(
                f"no prompt at {TOOL_PREDICTION_PROMPT}: it is the deployment's file, on"
                " the same terms as config/model/"
            )
        return slot_filling(
            template,
            {
                "tool_descriptions": self.build_tool_catalog(tools),
                "conversation_history": "\n".join(turns[:-1]),
                "user_message": turns[-1] if turns else "",
                "language": language,
            },
        )

    def build_tool_catalog(self, tools: Sequence[object]) -> str:
        """The tools this sample was offered, as the text the prompt's catalog slot takes."""
        return openai_tool_format_to_text(tools)


class ToolDecisionSFTPrediction(SFTPrediction):
    """The finetuned reviewer's own answer to the same question."""

    async def predict(
        self, turns: Sequence[str], tools: Sequence[object], language: str
    ) -> SFTReviewerVerdict | None:
        """Undecided, and so still unwritten: nothing says where its confidence comes from.

        `SFTReviewerVerdict` carries one, `tool_prediction.txt` asks for none, and `complete`
        answers with text and no logprobs -- so a number here would be invented rather than
        measured. Which prompt asks for it is the decision this waits on.
        """
        raise NotImplementedError
