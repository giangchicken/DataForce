# tool_decision: the two parts that get bodies, and a page to watch them run

## What

Give bodies to the methods that today say `pass`, for two parts only -- `ai_review` and the personal-data
check -- for the `tool_decision` profile, and put one static page in front of them that draws the whole
labelling flow as a row of rectangles, each rectangle holding the input that step was handed. The other two
data-quality checks have no shape yet, so their rectangles read `None` and the page says why. Nothing here
decides a shape `schema.py` does not already declare.

## Context

The tree is mid-restructure. What exists:

- `modalities/text2text/` -- ABCs and pydantic schemas, declaration only. Every method body is `pass`; the one
  `@abstractmethod` per class is the outside call.
- `profile/tool_decision/` -- one file per part (`ai_review.py`, `data_quality.py`, `human_review.py`), each
  holding the subclasses this profile ships, all empty. `utils.py` renders an OpenAI `tools` array as the
  catalog text a reviewer reads.
- `edge/routers/text2text/tool_decision.py` -- created, empty, 0 bytes.
- `config/prompts/` -- three prompts already written: `modalities/text2text/pii_checking.txt`,
  `modalities/text2text/vote.txt`, `profiles/tool_decision/prediction.txt`.
- `agent_toolkit` -- `string_utils` has the four rule scans (`email_detection_by_rules`,
  `name_detection_by_rules`, `otp_detection_by_rules`, `phone_number_detection_by_rules`), `llm.complete` is
  the model call, `embed` owns the embedding socket.

What does not exist: `services/`, `edge/routers/ai_review.py`, `edge/routers/data_quality.py`, any frontend.

`schema.py` docstrings still name `services/text2text/data_quality/` as where a socket gets a body. That
directory is gone from the tree and the profile subclasses took its place; the docstrings are stale and this
spec corrects them.

## Requirements

**Personal data.**

1. `review_text(turns, label)` returns one string holding the sample's input and output together. Every offset
   any span carries is into this string, and nothing downstream reorders or reflows it.
2. `flagged_candidates(text, language)` returns `{value: class}` from the four rule scans, called in a fixed
   declared order. A value matched by more than one scan keeps the class of the first scan that claimed it.
3. `confirmed(window, candidates)` -- the abstract method -- returns the subset of `candidates` the model
   confirms, keyed by value, with the class the model assigned. It never raises: a failed call confirms none.
4. `typed_placeholders(confirmed)` returns `{value: placeholder}`, one placeholder per distinct value,
   `<CLASS_N>` numbered per class in first-appearance order within the sample. One value said twice keeps one
   placeholder.
5. `confirmed_spans(text, confirmed, placeholders)` returns every occurrence of every confirmed value, in text
   order, matching across any run of whitespace. A span falling inside another span is dropped.
6. `replaced_text(text, placeholders)` returns the text with every confirmed value replaced by its placeholder,
   longest value first so a shorter value inside a longer one cannot cut it.
7. `scan(...)` returns a `PersonalDataScan` whose `decision` is `reported` when `redact` is false, `redacted`
   when `redact` is true and every candidate resolved, and `withheld` when `redact` is true and layer two left
   something unconfirmed.
8. `ToolDecisionPersonalChecking` overrides `review_text` so the tool catalog is part of what is scanned --
   an argument value in a tool call is where personal data actually sits in this profile.

**AI review.**

9. `LLMPrediction.predict(turns, label)` asks each juror once, independently, and returns one
   `LLMReviewerVote` per juror that answered. A juror that failed is absent from the sequence -- never a vote,
   never an empty label.
10. `LLMPrediction.verdict(turns, label)` returns an `LLMReviewerVerdict` whose `label_agreement` is the share
    of returned votes whose label equals the sample's label, and whose `consensus` is the panel's one answer or
    `None`.
11. `exact_match_consensus(answers)` returns the answer strictly more than half of them gave, else `None`.
    A strict majority, never a mode.
12. `llm_judge_consensus(answers)` runs only where `exact_match_consensus` returned `None`, and returns one of
    the answers given or `None`. It never returns a string no juror wrote.
13. `SFTPrediction.predict(turns, label)` returns one `SFTReviewerVerdict`; `verdict(answered, label)` returns
    whether that reviewer's label agrees with the sample's.
14. `ToolDecisionLLMPrediction` and `ToolDecisionSFTPrediction` render the prompt from
    `config/prompts/profiles/tool_decision/prediction.txt`, filling `{{conversation}}`, `{{catalog}}` and
    `{{label}}`, where `{{catalog}}` is `openai_tool_format_to_text(sample["tools"])`.

**Endpoints.** One per part, never one for all of them.

15. `POST /text2text/tool-decision/data-quality/personal-data` takes a sample, returns a `PersonalDataScan`.
16. `POST /text2text/tool-decision/data-quality/duplicate` and `.../abnormal` return `null` and an HTTP 200 with
    a `reason` naming the undecided shape. They are not 501: nothing failed, there is nothing to report yet.
17. `POST /text2text/tool-decision/ai-review` takes a sample, returns an `LLMReviewerVerdict` and an
    `SFTReviewerVerdict`.
18. `GET /text2text/tool-decision/` serves the page.

**The page.**

19. Seven rectangles, left to right, wrapping: `input`, `personal`, `duplicate`, `abnormal`,
    `human check: data quality`, `ai review label`, `human check`, `final result`.
20. Each rectangle shows the input that step was handed, not only its output. `input` shows the pasted sample;
    `personal` shows the review text it scanned; `ai review label` shows the conversation, catalog and label it
    was asked about; each `human check` shows what it is being asked to confirm.
21. `duplicate` and `abnormal` render `None` and the reason from the endpoint.
22. The two human-check rectangles are editable and pass their content to the next rectangle. They call no
    endpoint -- there is no human-review logic in this spec.

## Design

**Where a body lands.** A non-abstract method in `modalities/` is this modality's own rule and gets its body
there. The one `@abstractmethod` per class is the outside call and gets its body in
`profile/tool_decision/<part>.py`. So `verdict`, `exact_match_consensus`, `llm_judge_consensus`, `scan`,
`review_text`, `flagged_candidates`, `typed_placeholders`, `confirmed_spans` and `replaced_text` are filled in
the modality; `predict` and `confirmed` are filled in the profile. `review_text` is the one exception: the
modality writes the general version and the profile overrides it, because the catalog is this profile's alone.

**Data flow, personal data.**

    turns + label ──review_text──▶ text ──flagged_candidates──▶ {value: class}
                                    │                                │
                                    └──────────────┬─────────────────┘
                                                   ▼
                                          confirmed  (the model)
                                                   │
                                    ┌──────────────┴──────────────┐
                                    ▼                             ▼
                          typed_placeholders               confirmed_spans
                                    │                             │
                                    ▼                             │
                            replaced_text ◀────────────────────────┘
                                    │
                                    ▼
                             PersonalDataScan

`scan` is the only method that composes these; each of the others is callable and testable on its own.

**Data flow, ai review.** `verdict` calls `predict` once, counts agreement over the returned votes, then asks
`exact_match_consensus`; only where that is `None` does it ask `llm_judge_consensus`. The judge reads the
answers, not the conversation -- it is picking among answers already given, and giving it the conversation
would make it an N+1th juror whose vote outweighs the rest.

**Files.**

| file | change |
|---|---|
| `modalities/text2text/ai_review/llm_prediction.py` | bodies for `verdict`, `exact_match_consensus`, `llm_judge_consensus` |
| `modalities/text2text/ai_review/SFTmodel_prediction.py` | body for `verdict` |
| `modalities/text2text/data_quality/personal_data_checking.py` | bodies for the six non-abstract methods; docstring stops naming `services/` |
| `profile/tool_decision/ai_review.py` | `predict` on both classes |
| `profile/tool_decision/data_quality.py` | `confirmed` and the `review_text` override on `ToolDecisionPersonalChecking` |
| `profile/tool_decision/__init__.py` | rewrite: it exports six names that no longer exist |
| `edge/routers/text2text/__init__.py` | new, `facade` |
| `edge/routers/text2text/tool_decision.py` | the four endpoints and the page route |
| `edge/routers/__init__.py` | rewrite: it imports two deleted modules and aliases this router as `human_review_router` |
| `edge/main.py` | include one router, not three |
| `edge/static/index.html` | new, the whole page |

**The page.**

    ┌──────────┐   ┌───────────┐  ┌───────────┐  ┌───────────┐
    │  input   │──▶│ personal  │  │ duplicate │  │ abnormal  │
    │          │   │           │  │           │  │           │
    │ messages │   │ in: review│  │ in: sample│  │ in: sample│
    │ tools    │   │     text  │  │ out: None │  │ out: None │
    │ label    │   │ out: scan │  │ (no shape)│  │ (no shape)│
    └──────────┘   └───────────┘  └───────────┘  └───────────┘
                         └──────────────┴──────────────┘
                                        ▼
    ┌────────────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────────┐
    │ human check    │─▶│ ai review    │─▶│ human      │─▶│ final result │
    │ data quality   │  │ label        │  │ check      │  │              │
    │                │  │              │  │            │  │              │
    │ in: spans,     │  │ in: convo,   │  │ in: panel  │  │ in: everything│
    │     decision   │  │     catalog, │  │     verdict│  │ out: the label│
    │ out: approved  │  │     label    │  │     + sft  │  │      that ships│
    └────────────────┘  │ out: verdicts│  │ out: label │  └──────────────┘
                        └──────────────┘  └────────────┘

One file, `edge/static/index.html`: markup, style and script inline, no build step and no npm. Vanilla `fetch`
against the four endpoints. It is a bone -- it shows the flow and the shape of what moves along it, and it is
meant to be deleted when a real UI arrives (T-5).

## Decisions

1. **Abstract bodies land in `profile/tool_decision/`, not in `services/`.** Alternative: recreate
   `services/text2text/`. `services/` is gone from the tree and the profile subclasses already occupy that
   position, so recreating it adds a layer that hides nothing (H-2). Reversible; the docstrings that still name
   `services/` get corrected as part of this.
2. **The page is one static HTML file served by the edge.** Alternative: a Vite app under `ui/`, which is what
   the sibling `agent-evaluation` repo does. A build step, a lockfile and a CI step are a mouth to feed (T-3),
   and this page is a skeleton. Reversible -- `ui/` can be added later and this file deleted.
3. **The catalog in the ai-review prompt is rendered by `openai_tool_format_to_text`, the same function the
   personal-data `review_text` uses.** Alternative: a second renderer tuned for the model. Two renderers is two
   definitions of what a tool looks like, and a reviewer and a juror disagreeing about the catalog they read
   would be invisible (C-3).
4. **The judge fallback reads only the answers.** Alternative: give it the conversation too. That makes it an
   N+1th juror whose single vote breaks every tie, which is not what "consensus" was asked for.
5. **`ToolDecisionPersonalChecking.review_text` widens the base's signature to take the whole sample.** The base
   is handed turns and a label; the catalog lives on the sample's `tools`. Alternative: pass the rendered
   catalog in as another turn. That hides the widening rather than removing it, and a turn that is not a turn
   is worse than a wider signature.
6. **`duplicate` and `abnormal` return `null` with a reason, at HTTP 200.** Alternative: 501. Nothing failed and
   nothing is unimplemented in the sense 501 means -- the shape is undecided, which is a different fact and one
   the page should show as `None` rather than as an error.
7. `Assumption:` a sample posted to these endpoints is the JSON record shape already in use for this profile --
   `messages`, `tools`, and the label. No `Record` type is introduced.
8. `Assumption:` the four rule scans are called in the declared order email, phone, OTP, name. The order decides
   which class wins an overlap, so it is a constant with a name, not a literal in a loop (C-3).

## Versions

No new dependency. FastAPI (`>=0.141.1`) already serves; `StaticFiles` is part of Starlette, which FastAPI
already pulls in. The page loads nothing from a CDN.

## Invariants

- Every `PersonalDataSpan` offset indexes the exact string `review_text` returned. Check: slicing the text by a
  span's `start`/`end` yields the value that span was made from.
- One value gets one placeholder throughout a sample. Check: the placeholder map is keyed by value.
- No juror sees another juror's answer. Check: `predict` builds each juror's prompt from the sample alone.
- `llm_judge_consensus` returns only a string some juror wrote, or `None`. Check: its return is asserted to be
  in the answers it was given.
- Property order is preserved through `openai_tool_format_to_text`, so text re-rendered from the same tools is
  byte-identical. Already true; a test pins it.

## Error Behavior

- A juror call that fails is dropped from the vote list. The panel is smaller and `LLMReviewerVerdict.votes`
  says so; it is never an empty-label vote.
- Every juror failing gives a verdict with no votes, `label_agreement` 0.0 and `consensus` `None`. That is a
  valid answer, not an exception.
- `confirmed` returning nothing -- whether by failure or by rejecting every candidate -- leaves the text
  unrewritten. The two are not distinguished by the return, so the failure is logged as a structured event to
  stdout (H-6) and the decision is `withheld` when redaction was on.
- A value the model returns that is not character-for-character one of the candidates is discarded, as the
  prompt already states.
- An endpoint maps a domain error through `errors.py`; a handler stays thin and names no stage sequence.

## Testing Strategy

- Each personal-data method tested alone, against a hand-written text: overlap resolution picks the declared
  first scan; a value said twice gets one placeholder; a span inside a span is dropped; longest-first
  replacement does not cut a shorter value out of a longer one.
- `exact_match_consensus`: three answers two of which match gives that answer; two-two gives `None`; a mode that
  is not a strict majority gives `None`.
- `verdict` with a stub `predict`: agreement counted over returned votes only, and a failing juror not counted
  as agreement.
- `openai_tool_format_to_text` pinned against the known-good rendering already verified in this repo.
- The endpoints tested through FastAPI's `TestClient` with the model calls stubbed. `duplicate` and `abnormal`
  asserted to return `null` at 200.
- No test drives the page. It is a bone; a browser check is the check.

## Out of Scope

- `DuplicateDataChecking` and `CommonAbnormalChecking` bodies. Neither has a decided shape and this spec
  invents none.
- `DecisionLogic.decide` and the whole human-review rule. The page's two human-check rectangles are inputs a
  person types into, not a call.
- Persistence. Nothing here writes to the question store; a scan is computed and returned.
- Auth, rate limiting, batching, and running any of this over a corpus rather than one sample.
- `params.yaml` wiring -- which models the panel asks is still empty there, and filling it is a separate
  decision.

## Open, and reported rather than decided

These are contradictions already on disk. Each one blocks part of the above and none of them is mine to settle.

1. **`PersonalDataScan.approved: int` is required and has no default**, and its description is *"Human check and
   appprove the personal data span is correct"*. `scan()` runs before any human looks, so it cannot supply an
   honest value -- and the type is `int` where the description reads boolean. Requirement 7 cannot be met until
   this is either given a default, made optional, or moved off the scan.
2. **Nothing carries the rewritten text.** `Redaction` was deleted from `schema.py`, so `replaced_text` produces
   the redacted string and `PersonalDataScan` has no field to hold it -- while `decision` still distinguishes
   `redacted` from `reported`. Requirement 6 produces a value with nowhere to go.
3. `data_quality/schema.py` fails `ruff check`: `Callable`, `Sequence` and `NamedTuple` are imported and unused,
   left over from the deleted types.
4. `modalities/text2text/__init__.py` and `edge/routers/__init__.py` both write `façade` with the cedilla. H-8
   says the tag is read by a machine and is spelled `facade`.
