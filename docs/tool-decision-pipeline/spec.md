# tool_decision: eight independent steps, and one record at the end

## What

A `tool_decision` sample goes through eight steps, and **every step is reachable on its own**: one
part, one call, the arguments its own signature declares and the value its own method returns. No
step is handed another step's result to carry. A human step returns the whole shape it was given —
untouched where the human says it is right, edited where the human edited it — never a verdict about
it. The page is what remembers the answers, and it assembles them into one record at the last step,
which is the only place a record exists and exists only to be stored.

This specs the two parts that have a shape to act on — `ai_review` and the personal-data check — the
endpoint per part, the page, and the store the last step posts to. The other two data-quality checks
declare nothing, so they answer `None` and this specs no more about them.

## Context

Three axes and an edge hold the code, and each one imports only downward.

- `modalities/text2text/<part>/` declares the shapes and the sockets: an `@abstractmethod` per
  class, and a body only where the rule is shared by every task the modality serves.
- `profile/tool_decision/<part>.py` answers those sockets — one file per part, and the task's own
  logic.
- `services/tool_decision/<part>.py` — `ai_review.py`, `data_quality.py`, `human_review.py`,
  mirroring the profile file for file — is the full logic behind one endpoint. One function per
  endpoint, each callable without the others, and each takes the config for the model it asks and
  builds its own reviewer.
- `edge/routers/text2text/tool_decision.py` is the HTTP shell, `edge/store/` the table, and
  `edge/static/index.html` the page.

A service never imports `edge/`: the store is an adapter and a service is logic, so `stored_record`
takes the write as an argument and the router is what connects the two.

What each part declares, and who answers it:

| class | socket | the profile's subclass |
|---|---|---|
| `LLMPrediction` | `predict(turns, label)`, config one model or several | `ToolDecisionLLMPrediction` |
| `SFTPrediction` | `predict(turns, label)` | `ToolDecisionSFTPrediction` |
| `PersonalDataChecking` | `scan(sample)` | `ToolDecisionPersonalChecking` |
| `DuplicateDataChecking` | `embedding(texts)` | `ToolDecisionDuplicateChecking` — answers nothing, so the class stays abstract |
| `CommonAbnormalChecking` | none — `check_verdict` returns `None` | `ToolDecisionAbnormalChecking` |

`human_review/` declares `Annotation` and `ReturnedAnnotation`, which `edge/label_studio.py` builds
from what the annotation tool returns. Nothing on this flow's path builds either.

Three prompts are written, and a prompt sits with the code that fills it. Two are the task's,
under `config/prompts/profiles/tool_decision/`: `tool_prediction.txt` is a tool router — handed the
catalog and the conversation, it returns one JSON object, `{reason, label}`, and nothing else — and
`pii_llm_detect.txt` is the scan's second detector, handed the review text and answering
`{detected}`, a `{reason, text, label}` per value it found. It is asked to copy each value and
never to count characters: the offsets are found by searching for what it wrote.

The third is the modality's, at
`config/prompts/modalities/text2text/data_quality/pii_llm_confirm.txt`, mirroring the module that
sends it. It is handed the review text and every span both detectors
earned, numbered, and answers `{confirmed}` — one `{id, reason, confirmed}` per span it was shown. That one is shared because *whether a detected
value is personal data* is a question about personal data and about nothing else, where what a
sample is scanned as, and how, is the task's. Each file is named for the method that fills it.

`agent_toolkit.string_utils` holds the four rule scans — `email_detection_by_rules`,
`phone_number_detection_by_rules`, `otp_detection_by_rules`, `name_detection_by_rules`.
`agent_toolkit.llm.complete` is the model call and `resolve_config` reads a model's config by name;
every class here that asks a model calls both itself — it resolves the name when it is built, then
makes the call and reads one declared shape back. `profile/tool_decision/utils.py` renders an
OpenAI `tools` array as the catalog text a reviewer and a juror both read.

## Requirements

**The flow.**

1. A step reads its own arguments and returns its own value. Nothing threads a growing payload
   through the eight, and no step's signature mentions another step's shape.
2. A human step returns the shape it was handed: a `PersonalDataDetected` for a
   `PersonalDataDetected`, a label for a label. Where the human changed nothing, what it returns
   equals what it was given.
3. The record is assembled by the page, once, as the body it posts to be stored. No step above
   produces it. It keeps what arrived and adds what the review made of it:
   `{id, messages, tools, label, new_messages, new_tools, new_label, personal_data, duplicate,
   abnormal, llm, sft}`.
4. `duplicate` and `abnormal` are `None`. Neither check declares a shape.

**Personal data.**

5. **Detecting and replacing are two calls, because a human sits between them.**
   `detect(checking_input)` takes a `PersonalDataCheckingInput` — the record whole and the
   language it is in — and returns a `PersonalDataDetected`: the review text, what the detectors
   claimed, and the spans that survived. The two detectors, the confirmation, the placeholders and the offsets are that one
   answer, and the profile writes all of it bar the confirmation. `replace` then takes a
   `PersonalDataDetected` back — the spans as the reviewer ticked, edited or added them — and
   returns a `PersonalDataReplaced`: the copy, and how far it got. Nothing is replaced before a
   human has seen it, and what is replaced is what they handed back. What a checker is built with
   is `PersonalDataCheckingConfig`: the model that confirms, and the rule scans that detect. Both
   detectors are built from it, so both exist before any record does, and a deployment's own scan
   function is a scan like any other.
6. `review_text` is the string every span's offsets index — for this task the turns, the tool
   catalog and the label together, because an argument value in a tool call is where personal data
   sits. Nothing afterwards may reorder or reflow it.
7. Detection is two detectors over the same review text, unioned. One is the rule scans the input
   carries — `agent_toolkit`'s four, in the order email, phone, OTP, name, unless a caller passed
   its own — each handed the declared language; that order settles an overlap, where two scans
   claim one value the first to claim it keeps it. The other is
   one model, which answers with the values it found and what each one is — never with offsets,
   because a model counting characters is a model nothing here can check. A value it did not copy
   character-for-character out of the review text is dropped, since no offset can be found for it.
   Where both claim one value the rule scan's class wins; a class only the model named is kept, and
   is numbered after the four the scans declare.
8. The confirmation is a second model pass, span by span, and it is what sets the precision: only
   a span it confirms carries into the answer, and only those are replaced. It answers per span
   because the same characters are a customer's number in one line and an order number in the
   next. It may not raise — a failed call confirms none — and it only ever narrows: an answer
   naming an id no span carries is discarded, a span answered twice keeps the first answer, and a
   span nothing came back about is not confirmed. Nothing detected is nobody asked. Every model
   answer on this flow writes its `reason` key before the value or the verdict it justifies, so
   what a model concludes is read off the reason it has already written.
9. A span records `id`, `start`, `end`, `personal_data_class`, `placeholder` and `reason`, and
   `review_text[start:end]` is the value the span was made from. `id` is 1-based in the order the
   spans were found and is what the confirmation is asked about and answers with; `reason` is the
   confirmation's own words for that span, and the one thing on a span no rule here computes.
10. One placeholder per distinct value, `<CLASS_N>` numbered per class in first-appearance order. A
    value said twice keeps one placeholder and stays co-referent.
11. A span falling inside a longer span is dropped; the outermost wins.
12. `redacted_text` is `review_text` copied with every handed-over span's value replaced by its
    placeholder, longest value first so a shorter value inside a longer one cannot cut it. By
    value and not by offset, so a value confirmed at one occurrence is replaced at every
    occurrence — which is what keeps the same rule runnable over the record's other fields, where
    there are no offsets to run it by. It is `None` where nothing was rewritten. A span whose
    offsets read nothing is skipped, because replacing the empty string would place a placeholder
    between every character. The original is never overwritten: `review_text` stays on the detect
    answer and the copy is on the replace answer.
13. `outcome` is `reported` where no detector claimed anything — there was nothing to rewrite —
    `redacted` where the copy was made and every claimed value resolved, and `withheld` everywhere
    between: the copy holding what resolved, and equally the answer where the confirmation
    confirmed none or a reviewer handed back no span. A rewrite asked for and not finished is
    `withheld`, never `reported`. It is measured against `claims` and not against the spans, which
    is why the detect answer carries them: spans alone cannot tell a clean record from one whose
    every candidate was dropped.
14. Nothing on either shape records that a human looked. `outcome` says what was done to the text,
    and the flow's own answer is that the human returned the spans.
15. The human may edit `messages`, `tools` and `label`. What they edited to, redacted, is
    `new_messages`, `new_tools` and `new_label`; what arrived stays under the original three.
    `new_tools` is `null` where the catalog was left alone — an unmodified catalog has no new
    version to carry, and a copy of it under a second key is one more thing to keep in step.
16. Redaction runs after the edit, so a value the human typed is redacted too.
17. The record holds the raw content as well as the redacted content. That is what makes a review
    auditable — what changed is readable against what arrived — and it means the redaction protects
    a reader of the three `new_` keys and not the store: anything holding the row holds the values.

**AI review.**

18. `LLMPrediction` takes one `LLMModelConfig` or a sequence of them: one config is a panel of one
    and several are a panel of several. `jurors` is the one place that reads either, so nothing
    downstream counts models.
19. `LLMPrediction.predict(turns, label)` asks each juror once, independently, and returns one
    `LLMReviewerVote` per juror that answered. A juror is asked the sample's own question and is not
    shown the label. A juror that failed is absent — never a vote, never an empty label.
20. `verdict(turns, label)` returns an `LLMReviewerVerdict` whose `label_agreement` is the share of
    returned votes whose label equals the sample's — compared here, never asked of a model — and
    whose `consensus` is the panel's one answer or `None`.
21. `exact_match_consensus(answers)` returns the answer strictly more than half of them gave, else
    `None`. A strict majority, never a mode. Answers are compared as canonical text — one whitespace
    and one key ordering — so two that mean the same count as one.
22. `llm_judge_consensus(answers)` runs only where `exact_match_consensus` returned `None`, and
    returns one of the answers given or `None`. It never returns a string no juror wrote.
23. `SFTPrediction.predict(turns, label)` returns one `SFTReviewerVerdict`; `verdict(answered, label)`
    returns whether that reviewer's label agrees with the sample's.
24. The prompt is built inside `predict`, in the profile. It renders `tool_prediction.txt`, filling
    `{{tool_descriptions}}` with `openai_tool_format_to_text(sample["tools"])`,
    `{{conversation_history}}` with the turns before the last, `{{user_message}}` with the last one,
    and `{{language}}` with `sample["language"]`. The sample's label is not among them, and a sample
    that declares no language is a configuration error before the call, never a language guessed
    from the turns.
25. A juror's answer is the object the prompt asks for. `reason` and `label` are the model's;
    `model_name` is set by the caller, the only one that knows which juror it asked. `label` is a
    string — the tool-call array as text — and `LLMReviewerVote.label` holds it as one; nothing turns
    it into a structure. An answer that does not parse, or is missing either key, is a juror that did
    not answer.
26. A model's config is read from `config/model/<model name>.json` by name. `base_url` and `api_key`
    are used where the part's `<X>ModelConfig` carries them and read from that file where it does
    not. A name with no file and no explicit URL is a configuration error before the first call,
    never a default.

**Which models answer.**

27. `GET /text2text/tool-decision/models` returns every model this deployment serves, which is
    every `config/model/<name>.json` on disk. That directory is the list; nothing declares the
    names a second time in a file that could disagree with it.
28. A request names the models it wants: `verifier_model` on the scan, `jury_models` and
    `sft_model` on the review. They are the caller's tick, not a deployment's declaration.
29. A name the deployment does not serve is refused with 422 naming it, and the served list, before
    any model is called.
30. A request's model keys are named apart from a record's answer keys — `sft_model` against `sft`,
    `jury_models` against `llm` — because one says which reviewer to ask and the other what a
    reviewer said, and one word for both makes a record unpostable to a review endpoint.
31. Which models answered is on the record: `LLMReviewerVote.model_name` per vote and
    `SFTReviewerVerdict.model_name`. A panel that changes between records is therefore readable
    from the records, which is what makes a comparison across them checkable.

**Endpoints.** One per part, never one for all of them, and none of them returns a record.

32. `POST /text2text/tool-decision/data-quality/personal-data` takes the sample, the language and
    the verifier model, and returns a `PersonalDataDetected`. The language and the model are
    declarations about the request rather than keys of the record, so the sample handed on is what
    the corpus carries. `POST /text2text/tool-decision/data-quality/personal-data/replace` takes a
    `PersonalDataDetected` back and returns a `PersonalDataReplaced`. Two calls for one part
    because a human sits between them; the second asks no model, so nothing about it can be
    refused for a name this deployment does not serve.
33. `POST /text2text/tool-decision/data-quality/duplicate` and `.../abnormal` return `null` at
    HTTP 200. Nothing failed; there is nothing to report.
34. `POST /text2text/tool-decision/ai-review` takes the turns, the label and the tools, and returns
    an `LLMReviewerVerdict` and an `SFTReviewerVerdict` side by side.
35. `POST /text2text/tool-decision/records` takes the record **raw**, redacts it, stores the
    redacted row and returns `{record_id, stored_at}`. Redaction is the service's, never the
    client's: a rule the caller can skip is not a rule. A record with no redacted form is refused
    with 422, and so is a row that still holds a value its own scan says it replaced.
36. `GET /text2text/tool-decision/` serves the page.

**The page.**

37. Eight rectangles: `input`, `personal data`, `duplicate`, `abnormal`,
    `human check · data quality`, `ai review label`, `human check · label`, `final result`.
38. Each rectangle shows the input it was handed and the output it produces.
39. Step 2 lists every span as an editable row — `start`, `end`, `personal_data_class`,
    `placeholder` — beside the value `review_text[start:end]` currently reads. A **check** button
    re-reads every row and re-slices. An unreadable edit says why: not an integer, end not past
    start, or outside the text.
40. Step 5 carries an `auto` toggle. On, it keeps the outermost span and drops any span inside a
    longer one. Off, every span stands. Its output is the `PersonalDataDetected` it was handed with
    the spans that survived, badged `unchanged` where the spans leaving equal the spans step 2
    produced and `modified` otherwise, and the `PersonalDataReplaced` the replace endpoint answers
    with over those spans.
41. Step 6 reads the sample, not step 5. It is a check on the label, and no data-quality answer is an
    argument to it.
42. Step 7 offers `correct` and `modify`. `correct` returns the label as it arrived. `modify` opens
    the label editor; a **check** button re-parses it, and a label that is not JSON is returned as
    `{unparsed: <text>}` rather than dropped.
43. Step 8 shows the assembled record as the request body, raw and as computed, and beside it the
    row the service would store. It says on its face that the page built the body, that no step
    above did, and that the redaction is the service's.

## Design

**Where a body lands.** The modality declares; the profile answers; the service composes. Every
socket gets its body in `profile/tool_decision/<part>.py`, and a method with a body in `modalities/`
is a rule shared across every task that modality serves. `verdict`, `exact_match_consensus` and
`llm_judge_consensus` are three of them, because a strict majority is arithmetic and does not change
with the question being asked. `PersonalDataChecking` holds two more. `PiiRuleDetector` is the
rule scans as one thing that detects — where two of them claim one value the first keeps it, so the
order and the rule are one object — and which scans, in what order, is the input's; the four are
its default. And `pii_llm_confirm`, with
`PiiLlmConfirmer` and the prompt it sends, is **the confirmation**: whether a detected value really
is personal data is a question about personal data and about nothing else, so every task asks it
the same way and gets the same narrowing — a value that was not detected is discarded, and an
answer that did not come back, or came back the wrong shape, confirms none. Neither varies by
task. Which model confirms does, so a checker is *constructed* with the declaration its
request carried, and the confirmation resolves it in `__init__`.

`services/tool_decision/` is what an endpoint calls: `personal_data_scan` in `data_quality.py`,
`tool_decision_llm_predict` and `tool_decision_sft_predict` in `ai_review.py`, `reviewed_record` and `stored_record` in
`human_review.py`. Each takes a config and one sample and constructs the profile class it needs —
a config, not a built object, because the config is the only thing that varies and a bag of
pre-built reviewers passed between layers is one more thing to keep in step. A `None` config is a
reviewer the deployment did not declare and answers `None`. `duplicate_report` and
`abnormal_report` take a sample and nothing else: neither declares a shape to return, so neither
has a model to ask. A handler is then three lines: read the body, call one function, map
`ConfigError` to 422.

**Personal data is one socket and one function beside it.** `detect` is abstract and the profile
writes the whole of it; replacing is not a socket, because a copy with placeholders in it is the
same rule for every task and needs nothing a task knows. What a
sample is scanned *as* is the task's answer, not the modality's: a tool-calling sample is its turns
plus the catalog it was offered, and a base that composed the text from turns alone would be wrong
for the only task there is. So the input carries the sample whole, and the
methods it is written out of are the profile's own, each declared because it is a rule worth naming
and none of them a socket. `build_review_text` builds the frame of reference.

**A detector is an object that detects, built when the checker is, and a method that asks it.**
`PiiRuleDetector` holds the scans and their order — where two claim one value the first keeps it,
so the order and the rule are one thing. `PiiLlmDetector` and `PiiLlmConfirmer` are each one
class over the same resolved model — one prompt in, its own answer out, like the rule detector beside them —
differing in the prompt they send and the shape they ask their model for: `PiiLlmDetected` is a
`{text, label}` per value, `PiiLlmConfirmed` a list of values. **A model's
answer is a declared shape**, in `data_quality/schema.py` beside every other shape here, so reading
one is a validation with a message rather than a walk through `isinstance` that ends in an empty
answer nobody can explain. Each is built once per checker and not once per record — the scan set is
the task's and the config file is the same file every time, so one checker over a corpus reads
`config/model/<name>.json` once, and a name with no config and no endpoint is refused before the
first record rather than during it.

`pii_llm_detect` asks the model detector and `pii_rule_detector` is asked directly, both built
with the checker; `pii_detect` takes the text and the language and unions the two into what a
reviewer is shown as detected, `find_and_number_spans` turns
that into numbered spans, and `pii_llm_confirm` — the modality's — narrows those to the ones that
ship, each carrying the reason it was confirmed for. Each prompt is built by a `build_..._prompt` method named for the step that sends it, and
outside the `try` that swallows a failed call, so a missing prompt file is a `ConfigError` rather
than a record quietly answering nothing. Which endpoint a step reaches, and the call
itself, are that step's own class: it takes the `<X>ModelConfig` a request carried, resolves it in
`__init__` — so a name with no endpoint is refused before the first record — and its one method
makes the call, reads its shape back, and answers nothing where a model said nothing. The rule is
therefore written once per asking class rather than once for the codebase, which is the price of
each class holding the whole of its own asking.

**AI review.** `verdict` calls `predict` once, counts agreement over the returned votes, then asks
`exact_match_consensus`; only where that is `None` does it ask `llm_judge_consensus`. The judge reads
the answers, not the conversation. `predict` builds the prompt and makes the call, both in the
profile, so the prompt and the shape it must return are read in one file.

**One record, and only at the end.** The page holds the eight answers and composes them into the
record the store is posted. Nothing else composes one: a handler answers for its own part and knows
nothing about the others, which is what makes each endpoint drivable by itself. `llm` and `sft` are
the names the votes carry; `personal_data`, `duplicate` and `abnormal` are the three checks' own. No
pydantic model declares the envelope.

**Which models a deployment serves, and which a request asks.** A model is served when
`config/model/<model name>.json` exists — `edge/served_models.py` reads that directory and nothing
declares the names a second time, so the list cannot disagree with what is actually configured.
`GET /models` is that list, the page ticks from it, and a request carries the names it ticked. A
name off the list is refused before any model is called, with the served list in the message.

The choice being per request rather than per deployment costs nothing in traceability: every vote
carries `model_name`, so which models answered is readable off the record, and a panel that changed
between two records is visible in the two records rather than in a config file's history.

**Where a model's config comes from.** Two sources and one order. `resolve_config` reads
`config/model/<model name>.json` through `agent_toolkit`'s `JsonDirConfigResolver(directory)`,
registered once at the composition root with `set_config_resolver`; anything handed to it explicitly
then replaces what the file said. That precedence is the library's own — `api_key if api_key is not
None else config.api_key`, `base_url or config.base_url` — so a part passes whatever its
`<X>ModelConfig` carries and takes the file's value for the rest, and no merge is written here. No
module here writes its own reader either: `tests/guards/test_toolkit_not_reimplemented.py` fails a
`def` that names a library function.

The file is the deployment's — written after cloning, kept out of the repository by `.gitignore` —
and it says how the model behaves: temperature, concurrency, the token ceiling. A deployment that
keeps the endpoint in the environment leaves `base_url` and `api_key` out of both and lets
`LLM_BASE_URL` and `LLM_API_KEY` answer.

**The page.** One file, `edge/static/index.html` — markup, style and script inline, no build step and
no npm, nothing loaded from a CDN. Every shape in it is read off the tree, and the span offsets are
found with `indexOf` rather than written down, so the check button can always reproduce them.

**The store.** One table, `record`, keyed by `record_id`, holding the row as JSON and the time it
landed. A repeated id replaces the row through `session.merge()` -- a record posted twice is one
record reviewed twice, not two, and merge is a primary-key read then an insert or update, so no
dialect-specific `insert` is reached for. The cost, stated: the review the row used to hold is gone,
with no trace it existed.

**What the row holds, and what the store checks.** The whole record: what arrived under
`messages`, `tools` and `label`, and what ships under the three `new_` keys.
`services/tool_decision/human_review.py` composes it -- the human's edits applied, then every value
the scan carries replaced wherever it occurs, so a value the human typed is redacted too.

Keeping both halves is the decision, and its consequence is stated once: the row holds the personal
data verbatim, so the redaction protects a reader of the `new_` keys and not the database. Anything
holding a row holds the values.

What the store therefore checks is narrow, and it is the only check available server-side: a
posted record carries the spans the reviewer kept and no trace of the ones they dropped, so nothing
there can report what a reviewer let through. `unreplaced_values` proves the one provable thing --
the three `new_` keys hold none of the values the scan says it replaced -- reading only that half,
because the originals hold raw content on purpose and checking the whole record would fail by
design. A record that fails it is refused with 422 rather than written.

The service's one check is a self-check, and it is the only one available there: a posted record
carries the spans the reviewer kept and no trace of the ones they dropped, so nothing server-side
can report what a reviewer let through. `unreplaced_values` proves the narrower thing worth
proving — a row holds none of the values it claims to have replaced — and a row that fails it is
refused rather than written.

What a reviewer let through is the page's to show, beside the reviewer who did it. Two cases it
draws and neither side resolves: unticking a span leaves its value in the row, so the row is
redacted as far as the reviewer allowed and no further; and unticking a value another kept value
sits inside cuts it in half, because replacement is by value across every field, so a phone inside
a kept email becomes `minh<PHONE_1>@vd.vn`. Which of the two wins is not decided.

**Files.**

| file | change |
|---|---|
| `modalities/text2text/ai_review/llm_prediction.py` | bodies for `verdict`, `exact_match_consensus`, `llm_judge_consensus` |
| `modalities/text2text/data_quality/personal_data_checking.py` | `PiiRuleDetector`, and `PiiLlmConfirmer` — which resolves its own model and makes its own call |
| `modalities/text2text/data_quality/schema.py` | `PersonalDataCheckingConfig`, `PersonalDataCheckingInput`, `Language`, `RuleScan`, `SCAN_FUNCTIONS` and the `SCANS` a config defaults to |
| `services/tool_decision/data_quality.py` | builds the scan's input, and turns a record it cannot read into a `ConfigError` |
| `modalities/text2text/ai_review/SFTmodel_prediction.py` | body for `verdict` |
| `profile/tool_decision/ai_review.py` | `predict` and `rendered_prompt` on both classes |
| `profile/tool_decision/data_quality.py` | `detect`, `build_review_text`, the two detectors, and `order_claims_by_class`, `find_and_number_spans`, `replace_spans_with_placeholders`, `decide_replacement_outcome` |
| `profile/tool_decision/utils.py` | `conversation_turns`, which both parts read |
| `config/prompts/profiles/tool_decision/pii_llm_detect.txt` | what the second detector is asked |
| `config/prompts/modalities/text2text/data_quality/pii_llm_confirm.txt` | the spans the confirmation is shown, and the `{id, reason, confirmed}` it answers |

## Decisions

1. **Three axes: declare, answer, compose.** `modalities/` declares, `profile/` answers a task's
   sockets, `services/<task>/` composes one endpoint's full logic, and the router is thin.
   Alternative: let the handler compose the parts. Then the composition is only reachable over
   HTTP, cannot be tested without a client, and `edge/` grows the task's logic — while every
   endpoint's handler grows a second reason to change. The cost, stated: one more layer to open when
   following a call.
2. **Every step is independent, and the record exists only for the store.** Alternative: thread one
   envelope through the endpoints, each filling its key. That gives every handler a reason to know
   the whole shape, makes a part undrivable without the parts before it, and puts one pydantic model
   in the path of every change to any part. Reversible.
3. **A human step returns the whole shape, not a delta.** Alternative: return only what the human
   decided — a count, or a per-person row. Then a human saying *this is right* and a human saying *I
   have nothing to add* return the same thing, and the caller has to re-derive the rest.
4. **`detect` is the socket and the profile writes all of it.** Alternative: keep the layers apart, the
   model pass abstract and the composition in the modality. But the composition begins by deciding
   what text to scan, and that is the task's answer — the catalog belongs in it for this task and
   would not for another. One socket keeps the two halves of that decision in one file. The cost,
   stated: a second task re-writes the scan order and the placeholder numbering.
5. **Nothing records that a human approved a scan.** Alternative: a count or a flag on the shape.
   The service does not read it — the human's answer *is* the returned scan — and a field nothing
   reads is a field that goes stale.
6. **The redacted text is a second string, not a rewrite.** `review_text` is what every offset
   indexes, so replacing values in place would invalidate every span on the same object.
7. **`duplicate` and `abnormal` answer `null` at HTTP 200.** Alternative: 501. Nothing failed — the
   shape is undecided, which is a different fact, and the page should draw it as `None` rather than
   as an error.
8. **The catalog is rendered by `openai_tool_format_to_text` for both parts.** Two renderers would be
   two definitions of what a tool looks like, and a reviewer and a juror disagreeing about the
   catalog they read would be invisible (C-3).
9. **The judge fallback reads only the answers.** Giving it the conversation makes it an N+1th juror
   whose single vote breaks every tie.
10. **Both config sources, explicit first.** Alternative: one of them. The config class alone makes
   every deployment restate a URL and a key that `config/model/` already holds; the file alone makes
   a one-off run impossible without writing a file. The library merges them in this order already,
   so using both costs no code here — only `base_url` and `api_key` becoming optional on the four
   config classes, since a required field can never be left to the file.
11. **`label` stays a string.** Alternative: hold the parsed tool calls on the vote. A juror answers
    in text and the field declares text, so the answer is kept as written and canonicalised only
    where two of them are compared.
12. **A juror is not shown the label.** Alternative: ask it both questions, its own answer and a
    verdict on the label. A model shown the label answers about the label, and the signal this
    service runs on is a model answering the sample's own question. Agreement is arithmetic over the
    answers and belongs in code.
13. **Served models are a directory listing, not a declaration.** Alternative: a file naming the
    models this deployment uses. That file and `config/model/` could disagree, and the one that is
    wrong would be the one nothing checks. A name with a config file is served; a name without one
    is not.
14. **A panel config is one model or a list of them.** Alternative: always a list. A deployment
    asking one model would declare a one-element list and every reader would carry the same
    unwrapping, so `jurors` carries it once instead, in the class the panel belongs to.
15. **The page is one static HTML file the edge serves.** Alternative: a Vite app under `ui/`. A
    build step and a lockfile are a mouth to feed (T-3) for a skeleton meant to be deleted (T-5).
16. **`auto` on step 5 is the outermost rule, not a confidence threshold.** It is the same rule spans
    are resolved by inside `detect`, applied again where a human did not override it.
17. **The language is declared, not guessed, and it is one of the two the scans know.** Alternative:
    detect it from the turns. A detector is a rule to write, test and keep, and it answers a
    mixed-language chat by guessing. `agent_toolkit`'s scans key their tables by `vi` or `en`, so
    `PersonalDataCheckingInput.language` is that choice and nothing else — `Tiếng việt` spelled out
    is a `KeyError` from inside the library, so the shape refuses it and `personal_data_scan` turns
    that into a `ConfigError` and a 422 rather than a 500. It defaults to `vi`, the language this
    corpus is in, so a record that says nothing is scanned in Vietnamese rather than refused. Every
    rule scan and both model steps take that one value.
18. **The scan is given a declared input, not a bare sample, and the checker a declared config.**
    `PersonalDataCheckingInput` holds the record and the language — what changes per record.
    `PersonalDataCheckingConfig` holds `verifier_model` and `list_scan_functions` — the scans to
    run, picked from `SCAN_FUNCTIONS` or brought by the deployment — which is what a checker is
    built with and does not change while it lives. That split is why `pii_rule_detector` and
    `pii_llm_detector` are both built in `__init__` and sit side by side: a detector whose scans
    arrived with the record could not. Alternative: read the language off the record and fix the
    scans in the checker, which left two things a caller could not see from any signature. A
    sample itself is still `{id, messages, tools, label}` as the page holds it, and is carried
    whole; the language is declared beside it.
19. **Detecting answers, replacing is asked for separately.** Alternative: one call that detects,
    confirms and replaces, which is what it did until the page needed the spans before the copy.
    A human ticks, edits and adds spans, so a copy made before they looked is a copy of what
    nobody agreed to, and rebuilding it in the page would be a second implementation of the one
    rule a client must not be able to skip. So `detect` answers `{review_text, spans}`, the page
    hands those back with its edits, and `replace` answers `{redacted_text, outcome}`. The cost,
    stated: the detect answer carries `claims` as well as `spans`, and the page round-trips both.
    Without them the outcome could only say *nothing was handed over*, and a scan whose every
    candidate was dropped — both model steps failing, or a reviewer unticking the lot — would
    read `reported`, which is the word for a clean record.

## Versions

No new dependency. FastAPI `>=0.141.1` serves the page through Starlette's `StaticFiles`.
`sqlalchemy >=2.0.52,<2.1` and `alembic >=1.19.1` are already declared in `pyproject.toml` and are
what the store is built on.

## Invariants

- Every span offset indexes the exact string in `PersonalDataDetected.review_text`. Check: slicing by a
  span's `start`/`end` yields the value it was made from.
- No span offset indexes `redacted_text`. A placeholder is not the length of the value it replaced,
  so the two strings do not share offsets, and only `review_text` is a span's frame of reference.
- One value gets one placeholder throughout a scan. Check: the placeholder map is keyed by value.
- No span survives inside a longer span. Check: no pair where one range contains the other.
- No juror sees another juror's answer. Check: `predict` builds each juror's prompt from the sample
  alone.
- `llm_judge_consensus` returns only a string some juror wrote, or `None`.
- What a human step returns differs from what it was given only where the human changed something.
- No endpoint's response mentions a part it does not own. Check: each response model is one part's
  own shape.
- Property order is preserved through `openai_tool_format_to_text`, so text re-rendered from the same
  tools is byte-identical.

## Error Behavior

- A juror call that fails is dropped from the vote list. The panel is smaller and `votes` says so; it
  is never an empty-label vote.
- Every juror failing gives a verdict with no votes, `label_agreement` 0.0 and `consensus` `None`. A
  valid answer, not an exception.
- A model call that fails answers nothing, and so does an answer that is not the shape the step
  asked for. Neither step raises: a failed detection leaves the rule scans' values, and a failed
  confirmation confirms none, which leaves `redacted_text` `None`. Either way it is a structured
  event on stdout naming the step that was asking and what went wrong (H-6); `outcome` is
  `withheld` where a rewrite was asked for.
- A value a detector returns that is not character-for-character in the review text is dropped, and
  an answer the confirmation returns about a span nobody showed it is discarded.
- A label the human typed that is not JSON is carried as `{unparsed: <text>}`. It is never dropped
  and never guessed at.
- One part failing fails that one call. The page keeps every answer it already has, and the step is
  re-runnable on its own.
- `POST .../records` with an `id` already stored replaces that row.
- A handler stays thin: it calls the part and maps the error through `errors.py`.

## Testing Strategy

- `detect` over a hand-written sample: overlap resolution picks the declared first scan; a value said
  twice gets one placeholder; a span inside a longer span is dropped; every returned offset slices
  back to its value; `redacted_text` replaces the longest value first.
- `exact_match_consensus`: two of three matching gives that answer; two-two gives `None`; a mode that
  is not a strict majority gives `None`.
- `verdict` with a stubbed `predict`: agreement counted over returned votes only, a failing juror not
  counted as agreement.
- `openai_tool_format_to_text` pinned against its known rendering.
- Each endpoint through `TestClient` with the model calls stubbed, called with nothing but its own
  arguments — no fixture threads one payload through several of them.
- Round trip: `POST .../records` then read it back, equal.
- No test drives the page. A browser is the check.

## Out of Scope

- `DuplicateDataChecking.duplicate_groups` and `CommonAbnormalChecking.check_verdict` bodies. Neither
  declares a shape and this spec invents none.
- Auth, rate limiting, batching, and running any of this over a corpus rather than one sample.
- Which models the panel asks, and how many. A composition is a deployment's declaration, and
  nothing in this spec picks one.
- The store's schema management. `edge/store/records.py` declares the table and `create_all` is
  what has been run against it; Alembic, migrations, and how a schema changes are deferred by
  decision, to be settled when the database is.

## Open

Nothing. Every question this spec opened has an answer above; the one thing deliberately deferred
is the store's schema management, under Out of Scope.
