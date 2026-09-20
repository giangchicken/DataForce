# tool_decision: eight independent steps, and one record at the end

## What

A `tool_decision` sample goes through eight steps, and **every step is reachable on its own**: one
part, one call, the arguments its own signature declares and the value its own method returns. No
step is handed another step's result to carry. A human step returns the whole shape it was given —
untouched where the human says it is right, edited where the human edited it — never a verdict about
it. The page is what remembers the answers, and it assembles them into one record at the last step,
which is the only place a record exists.

This specs the two parts that have a shape to act on — `ai_review` and the personal-data check — the
endpoint per part, and the two pages: `edge/static/index.html`, which *draws* the flow for whoever
is building it, and `ui/`, which *drives* it for whoever is labelling. Where that record is then kept is not specified here: the store,
the route that would take it and the records it may refuse are another spec's
(§ *Out of Scope*). The other two data-quality checks declare nothing, so they answer `None` and
this specs no more about them.

## Context

Three axes and an edge hold the code, and each one imports only downward.

- `modalities/text2text/<part>/` declares the shapes and the sockets: an `@abstractmethod` per
  class, and a body only where the rule is shared by every task the modality serves.
- `profile/tool_decision/<part>.py` answers those sockets — one file per part, and the task's own
  logic.
- `services/tool_decision/<part>.py` — `ai_review.py` and `data_quality.py`, mirroring the profile
  file for file — is the full logic behind one endpoint. One function per endpoint, each callable
  without the others, and each takes the config for the model it asks and builds its own reviewer.
- `edge/routers/text2text/tool_decision.py` is the HTTP shell, `edge/static/index.html` the
  drawing of the flow, and `ui/` the labelling UI that calls the routes. There is no table:
  nothing here writes the record down.

A service never imports `edge/`. That direction is what a store would be built against when there
is one — an adapter handed to logic as an argument, never imported by it — and it is `H-8`'s fourth
column, not a rule this feature invented.

What each part declares, and who answers it:

| class | socket | the profile's subclass |
|---|---|---|
| `LLMPrediction` | `predict(turns, label)`, config one model or several | `ToolDecisionLLMPrediction` |
| `SFTPrediction` | `predict(turns, label)` | `ToolDecisionSFTPrediction` |
| `PersonalDataChecking` | `scan(sample)` | `ToolDecisionPersonalChecking` |
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
OpenAI `tools` array as the catalog text a reviewer and a juror both read, and reads the other
way too: `parse_text_to_tools` turns what a juror wrote back into OpenAI tool calls, the
format's own shape, arguments as JSON text under one key ordering.

## Requirements

**The flow.**

1. A step reads its own arguments and returns its own value. Nothing threads a growing payload
   through the eight, and no step's signature mentions another step's shape.
2. A human step returns the shape it was handed: a `PersonalDataDetected` for a
   `PersonalDataDetected`, a label for a label. Where the human changed nothing, what it returns
   equals what it was given.
3. The record is assembled by the page, once, as the flow's last answer. No step above produces
   it, and no route takes it: where it is kept is deferred (§ *Out of Scope*). It keeps what
   arrived and adds what the review made of it:
   `{id, messages, tools, label, new_messages, new_tools, new_label, personal_data, duplicate,
   abnormal, llm, sft}`. A key the corpus carries that nothing here reads stays under its own
   name: what arrived is kept whole, and dropping one at the last step would make the record a
   lossy copy of the sample it is about.
4. `duplicate` and `abnormal` are `None`. Neither check declares a shape.

**Personal data.**

5. **Detecting and replacing are two calls, because a human sits between them.**
   `detect(checking_input)` takes a `PersonalDataCheckingInput` — the record whole and the
   language it is in — and returns a `PersonalDataDetected`: the review text, what the detectors
   claimed, and the spans that survived. The two detectors, the confirmation, the placeholders and the offsets are that one
   answer, and the profile writes all of it bar the confirmation. `redact` then takes a
   `PersonalDataDetected` back — the spans as the reviewer ticked, edited or added them — beside
   the record as they left it, and returns a `PersonalDataRedacted`: the record with every
   confirmed value replaced in every field, that record rendered back as one text, and how far it
   got. Nothing is replaced before a human has seen it, and what is replaced is what they handed
   back. **Two and not three.** There was a call between them that rewrote `review_text` alone: a
   copy nothing read, and an outcome measured against a second rewrite of the scan's own text
   rather than against what ships. What a checker is built with
   is `PersonalDataCheckingConfig`: the model that confirms, and the rule scans that detect. Both
   detectors are built from it, so both exist before any record does, and a deployment's own scan
   function is a scan like any other.
6. `review_text` is the string every span's offsets index — for this task the turns, the tool
   catalog and the label together, because an argument value in a tool call is where personal data
   sits. Nothing afterwards may reorder or reflow it. **It is built one way and there is no way
   back.** `build_review_text` is module-level rather than a method on a checker, because it is
   built twice from two sides — over the sample a scan is handed, and over the record a reviewer
   left, to say what that record now reads as — and two spellings of it would be two frames of
   reference. Nothing needs the other direction: everything that happens to a record after its
   text has been read happens *to the record*, by value, so the record stays JSON the whole way
   through and the text is rendered again whenever somebody has to read one. A parser going the
   other way would be a second definition of what a turn and a call are.
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
   `review_text[start:end]` is the value the span was made from. Both offsets are non-negative:
   a negative one is a slice counted from the end of the text, which reads a value nothing
   detected, so the shape refuses it rather than answering about it. `id` is 1-based in the order the
   spans were found and is what the confirmation is asked about and answers with; `reason` is the
   confirmation's own words for that span, and the one thing on a span no rule here computes.
10. One placeholder per distinct value, `<CLASS_N>` numbered per class in first-appearance order. A
    value said twice keeps one placeholder and stays co-referent.
11. A span falling inside a longer span is dropped; the outermost wins.
12. Replacing is every handed-over span's value swapped for its placeholder, longest value first
    so a shorter value inside a longer one cannot cut it. By
    value and not by offset, so a value confirmed at one occurrence is replaced at every
    occurrence — which is what makes the rule runnable over the record's other fields at all,
    where there are no offsets to run it by. A span whose
    offsets read nothing is skipped, because replacing the empty string would place a placeholder
    between every character; a span with no placeholder is skipped for the same reason read the
    other way round — there is nothing to put in the text, and replacing a value with nothing
    deletes it rather than marking it, and says `redacted` about a copy that lost a stretch of
    itself. The claim such a span named is then unresolved, which is `withheld`.
    The copy a reviewer reads is the redacted record rendered forward by `build_review_text`, not
    a second rewrite of the scan's own string: one place where a replacement happens, and one
    place where a text is built from a record.
    The values are read into a map keyed by *value*: one value has one placeholder
    (Requirement 10), and keyed the other way two spans a reviewer typed the same placeholder on
    would be one entry, leaving the value that lost in a copy reporting itself redacted. The original is never overwritten: `review_text` stays on the detect
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
15. **The human edits the label, and only the label.** What they edited it to, redacted, is
    `new_label`; the turns and the catalog ship under `new_messages` and `new_tools` because
    redaction rewrites them, and what arrived stays under the original three. The record shape
    holds all three either way — a value coming out of a turn is not a reviewer rewriting one —
    but nothing offers the turns or the catalog for retyping: they are what a customer said and
    what the assistant was offered, and a page that let either be changed is a page that can make
    the sample agree with the label instead of the other way round. What is being decided is
    which calls that conversation should have produced.
    `new_tools` is `null` where nothing made a new version of the catalog — a copy of it under a
    second key is one more thing to keep in step — and redaction is now the only thing that ever
    makes one: `review_text` holds the catalog (Requirement 6), so a confirmed value can sit in a
    tool's description and the redaction rewrites it there, and a redacted catalog *is* a new
    version.
16. Redaction runs after the edit, so a value the human typed is redacted too.
17. The record holds the raw content as well as the redacted content. That is what makes a review
    auditable — what changed is readable against what arrived — and it means the redaction protects
    a reader of the three `new_` keys and nothing else: anything holding the record holds the
    values, whatever ends up holding it.

**AI review.**

18. `LLMPrediction` takes one `LLMModelConfig` or a sequence of them: one config is a panel of one
    and several are a panel of several. `jurors` is the one place that reads either, so nothing
    downstream counts models.
19. `LLMPrediction.predict(turns, tools, language)` asks each juror once, independently, and returns
    one `LLMReviewerVote` per juror that answered. A juror is asked the sample's own question, and
    the label is not among the arguments: a step that is never to show a label is not handed one.
    A juror that failed is absent — never a vote, never an empty label.
20. `verdict(turns, label, tools, language)` returns an `LLMReviewerVerdict` whose
    `label_agreement` is the share of returned votes whose label equals the sample's — compared
    here as canonical text, never asked of a model — and whose `consensus` is the panel's one
    answer or `None`.
21. `find_exact_match_consensus(pred_texts)` returns the answer strictly more than half of them gave,
    else `None`. A strict majority, never a mode. Answers are compared by `normalize_prediction`, which
    is a **socket**: the arithmetic counts over it and the modality never says what it is, because
    nothing at that layer knows what an answer is made of. `ToolDecisionLLMPrediction` answers it
    over `parse_text_to_tools`, which reads the calls out of what a juror wrote — so the
    order the calls were written in, prose around them, arguments written as JSON text rather than
    as an object, the wrapper the wire format puts a call in and the `id` it hangs on one are all
    one answer, while a different tool, a different argument value, or one call where another
    answer made two are not.
    Where it can read no call it canonicalises whatever JSON it did read — so `[]` with prose
    around it is the same answer as `[]`, on the same terms as a call with prose around it —
    and compares text that reads as no JSON as text.
22. `find_llm_judge_consensus(pred_texts)` runs only where `find_exact_match_consensus` returned `None`, and
    returns one of the answers given or `None`. It never returns a string no juror wrote: it asks
    `judge_prediction(pred_texts)` — the socket — and narrows what comes back to an answer given,
    matched the same way the answers were matched to each other. Nothing answered is nobody asked.
    `ToolDecisionLLMPrediction.judge_prediction` answers `None` and asks no model: where sameness
    is structural, a tie that survives the matching is two different calls, and a model picking
    between them would be the deciding vote cast by a juror that never read the conversation
    (Decision 9, Decision 20). The socket is for a task whose answers can only be compared as
    meaning — a summary said twice in different words is one answer, and nothing but a model can
    say so.
23. `SFTPrediction.predict(turns, tools, language)` returns one `SFTReviewerVerdict`, or `None`
    where it did not answer — on the same terms as an absent juror, never an empty-label verdict.
    That is the whole of the socket. Whether its answer agrees with the label is not asked in the
    modality: comparing two answers means knowing what an answer is made of, and that is the
    task's, so it lands in the profile with the rest of this reviewer's half. Where its
    `confidence` comes from is open (§ *Open*), so nothing of it has a body yet.
24. The prompt is built inside `predict`, in the profile. It renders `tool_prediction.txt`, filling
    `{{tool_descriptions}}` with `convert_tools_to_text(sample["tools"])`,
    `{{conversation_history}}` with the turns before the last, `{{user_message}}` with the last one,
    and `{{language}}` with the language declared for the request. The sample's label is not among
    them, and the language is never guessed from the turns. `ReviewRequest` declares it, defaulting
    to `vi`, on the same terms as the scan (Decision 17); the methods that carry it to the slot
    type it as text, because a prompt slot is not a table anything can `KeyError` on. One rendering
    serves the whole panel, since no slot depends on which juror is asked.

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
    the corpus carries. `.../personal-data/redact` is the second, and the last. Two calls for one
    part because a human sits between them; the second asks no model, so nothing about it can be
    refused for a name this deployment does not serve.
    It takes the sample as the human left it with that
    same `PersonalDataDetected` beside it under `detected`, and answers a `PersonalDataRedacted`:
    the sample copied with every handed-back span's value replaced wherever it occurs, under
    `sample`; that copy rendered again as a review text, under `review_text`; and how far the
    rewrite got, under `outcome`. The record half
    is where the three `new_` keys come from, because a span's offsets index `review_text` and
    `messages` and `label` are other strings (Requirement 12); `sample` holds the record's own keys
    and nothing about how it was redacted, on the same terms as the other declarations. The text
    half is the only thing a person can read the redaction *off* — the label is rendered into it
    (Requirement 6), so the placeholder standing in a turn and the placeholder standing in a call's
    argument are one screen apart and visibly the same string. It is built forward from the
    redacted record, never read back out of a text. It asks no model either, and it keeps nothing:
    the sample is read, copied and answered. A reviewer who handed back no span asked for nothing
    to be rewritten, and gets the sample as it arrived rather than a refusal.
33. `POST /text2text/tool-decision/data-quality/label` takes a sample and answers a `LabelChecked`:
    whether every call the label makes names a tool the sample's own catalog offers and supplies
    the arguments that tool requires, under `schema_valid`; and one sentence per call that does
    not, naming it by its position in the label, under `faults`. It is the store's `schema_valid`
    rule (`docs/tool-decision-store/spec.md` § *The facets*) asked **before** a row is written
    rather than read off one afterwards, and it is that same function and not a second reading of
    it — two readings would let a page wave a label through and the corpus mark that same label
    broken. A check and never a refusal: 200 with a verdict, because what the label ought to be is
    the reviewer's to say and a route that refused would decide it for them. It asks no model,
    holds no session and keeps nothing, so it may be asked as often as a label changes. A label
    that is empty or absent is a sample needing no call, which is an answer and not a fault.
34. `POST /text2text/tool-decision/data-quality/duplicate` and `.../abnormal` return `null` at
    HTTP 200. Nothing failed; there is nothing to report.
35. `POST /text2text/tool-decision/ai-review` takes the sample, the language it is in and the models
    ticked, and returns an `LLMReviewerVerdict` and an `SFTReviewerVerdict` side by side. The
    language and the two model keys are declarations about the request rather than keys of the
    record, so the sample handed on is what the corpus carries.
36. One route stores a record, and it is not this spec's. The redaction route reads one and keeps
    neither it nor the copy it answers (Requirement 32); the store, the route that takes it and
    which records it refuses are one decision taken in `docs/tool-decision-store/spec.md`
    (§ *Out of Scope*). Nothing else here depends on it — every step above answers its own call —
    so the record is still the flow's last answer, and a refusal from that route sends the labeller
    back to the step it names rather than into anything this spec describes.
37. `GET /text2text/tool-decision/` serves the page.

**The page that draws the flow.** Read by whoever is building it, and driven by nobody: every
answer in it is recomputed in its own script over a sample written into the file.

38. Eight rectangles: `input`, `personal data`, `duplicate`, `abnormal`,
    `human check · data quality`, `ai review label`, `human check · label`, `final result`.
39. Each rectangle shows the input it was handed and the output it produces.
40. Step 2 lists every span as an editable row — `start`, `end`, `personal_data_class`,
    `placeholder` — beside the value `review_text[start:end]` currently reads. A **check** button
    re-reads every row and re-slices. An unreadable edit says why: not an integer, end not past
    start, or outside the text.
41. Step 5 carries an `auto` toggle. On, it keeps the outermost *kept* span and drops any span
    inside one — measured over the rows still ticked, because a span is inside a kept longer one or
    it is inside nothing: untick an email and the phone number inside it is what is left to hand
    back. Off, every span stands. What the step holds is the `PersonalDataDetected` it hands on
    with the spans that survived — its input, on Requirement 47's terms, since it is the body of
    the call the step makes — badged `unchanged` where the spans leaving equal the spans step 2
    produced and `modified` otherwise; its output is the `PersonalDataRedacted` the redaction
    endpoint answers with over those spans.
42. Step 6 reads the sample, not step 5. It is a check on the label, and no data-quality answer is an
    argument to it.
43. Step 7 offers `correct` and `modify`. `correct` returns the label as it arrived. `modify` opens
    the label editor; a **check** button re-parses it, and a label that is not JSON is returned as
    `{unparsed: <text>}` rather than dropped.
44. Step 8 shows the assembled record, raw and as computed, and beside it the three `new_` keys —
    what would ship. It says on its face that the page built it, that no step above did, and that
    nothing stores it: the store is deferred. The redaction the drawing draws is its own — the
    labelling UI asks the route for it (Requirement 32) — so the two conflicts a reviewer can
    leave behind stay readable in one file with no service running.

**The labelling UI.** The other page, and the one a labeller works in: the same eight steps, but
every answer in it came from a route. **How they are laid out is not this spec's** — the screen,
what is one button and what is a decision, and where a corpus comes from are
`docs/tool-decision-store/spec.md` § *The page* and § *Raw data in*, because the corpus the page
walks and the statistics it shows are that spec's and they are what reshaped it. What this spec
still says about that page is what every one of its answers has to be true of, whatever shape it is
drawn in.

45. `ui/` is the UI: `index.html`, `style.css` and twelve ES modules that `app.js` loads, mounted
    as static files at `/ui` by `create_app()`. Fourteen files, no build step, no npm, nothing
    from a CDN — native modules give the file boundaries without any of the three, which is the
    reason a labeller needs nothing installed but the service. `docs/labelling-ui/layout.md`
    § *The tree* is the list, and what each module hides is the table under it.
46. It computes no answer of its own. Every rectangle shows what a route answered, and the only
    thing the UI composes is the record at the end (Requirement 3) — so a rule lives in one place,
    and the page that labels cannot disagree with the service about what a span or a vote is. The
    redaction behind the three `new_` keys is a route for that reason and not a walk over the
    record in the client (Requirement 32, Decision 24): a rule a caller can skip is not a rule.
47. **The drawing** is one rectangle per step, in flow order, each showing what it was handed and
    what it answered. What it was handed is the request body itself, so what it shows as a step's
    input is what went over the wire rather than the page's account of it. That is Requirement 1 on
    screen, which is why the flow is drawn as a flow rather than as one form with a submit button.
    **The labelling page is not obliged to be drawn that way**, and is not: a step the reviewer
    cannot influence is a call, not a screen. What both pages owe is that no step's answer is
    computed anywhere but its route, and that a step is re-runnable on its own — never that each
    has a rectangle and a button of its own.
48. **A sample arrives, and every endpoint still takes exactly one.** Where it comes from is the
    store spec's — the labelling page walks an imported corpus — and what this spec requires is
    unchanged by that: one sample per request, `{id, messages, tools, label}`. The language it is
    in is declared once, beside the sample, from the two the scans know: it is a declaration about
    this sample and both model steps are handed it (Decision 17), so it is declared where the
    sample is rather than twice in the two rectangles that send it. A different sample on screen
    clears every answer, because their answers are answers about something else.
49. The user can edit. In the drawing, every rectangle holding data the flow carries — the sample,
    the spans, the label — is editable in place, with a **check** button that re-reads what was
    typed, and what they edited is what the next call is made with. In the labelling UI it is the
    spans and the label and nothing else (Requirement 15). A human step *is* that edit plus the call after
    it (Requirement 2); nothing records that a human looked (Requirement 14).
    Which cuts the other way too: an answer given before an edit is not the answer to the edit, so
    an edit drops the answers made with what it replaced. Moving a span, unticking one or asking
    for the spans again drops the copy made over the old ones, and the step reads as unanswered
    until **replace** is pressed again; changing the language drops both model steps' answers.
    Nothing is silently carried into a record it is not about, and nothing is re-called on the
    user's behalf.
    Where the correction is made is wherever that answer is shown, which on a screen holding every
    answer at once is in front of the reviewer already. What a page may not do is carry an answer
    into a record it is not about: an edit drops the record assembled from it, and the record is
    built again from what the reviewer now says. Every other answer stands until the step it came
    from is actually edited, which is this requirement's own rule and not a second one.
50. Which models answer is ticked, not typed: the lists are `GET /models`' answer — **a bare array
    of names**, which is the shape to read it in — one tick for the verifier, many for the jury,
    one for the finetuned reviewer, and the ticks become `verifier_model`, `jury_models` and
    `sft_model` on the two requests. A UI that hard-codes the names is a second declaration of what
    this deployment serves, which is exactly what Requirement 27 refuses. A UI that reads the
    answer in a shape the route does not send is worse than one that hard-codes them: every list
    draws empty, every run stops asking to be told which model, and nothing on the screen says why.
    The lists sit where the models are spent.
    The answer is asked for again whenever the window is focused, because `config/model/` is a
    directory a deployment edits while the service is up and the endpoint reads it per call — so a
    model added to it appears in the lists without a reload. A list that came back unchanged is not
    drawn again, and a model still served keeps its tick, because alt-tabbing is not a reviewer
    changing their mind. On focus and not on an interval: a
    poll picks a number nobody chose, and the person who edited the directory is the person coming
    back to the tab. A redraw keeps every tick whose name is still served; a ticked name that is
    gone is unticked, and the list says which one, because a name off the list cannot be asked for
    (Requirement 29).
51. Personal data is **two calls with a human between them** (Requirement 5), and that is a fact
    about the calls, not about how many buttons a page draws: the scan claims the spans, the
    reviewer ticks, edits or adds them, and the redaction answers over what they handed back.
    Nothing is replaced before they looked, and no page may collapse that into one call. A row can
    be added as well as edited, since a reviewer may add a span: it is numbered after the last,
    because `id` is what the confirmation was asked about and nothing asks it again about a span it
    never saw.
52. A refusal is shown where it happened. A 422's `detail` is shown in the words the service used,
    and every answer the page already holds stays: one part failing fails that one call, and the
    step is re-runnable. The UI never retries on its own and never hides a refusal behind a spinner
    that stops. A step asked before it has what it needs says *not asked* instead, and says it
    differently: nothing was called, so nothing refused anything, and the two must not look alike.
53. The record is composed out of the redaction route's answer (Requirement 32) and everything the
    page already holds, and never out of anything the reviewer has to remember to rebuild. It is
    composed **as they work** and shown while they work: the copy it is built from is remade on
    every tick already, so a record that appeared only once the post had been made was a box
    promising to show what would be sent and showing it after it had been sent. It is composed
    once more at the moment of posting, over the copy as it reads that instant rather than as it
    read before the last keystroke. A record assembled before every step answered says which of
    them did not, rather than reading as complete.
54. Submitting posts the record to the store's own route (Requirement 36) and says what happened —
    that it landed, or which step did not run, or which variable to set where no database is
    attached. That route is what Requirement 36 had been holding open.
55. **The label panel draws the label it is asking about, and redraws it whenever it changes.**
    Three versions, and a line above says which is up: what arrived, what the reviewer is
    rewriting it to, and what ships once the redacted copy exists — the last being what becomes
    `new_label`. Painted once on opening and never again, it showed the bare name that arrived
    above a tick that would confirm something else, which is a panel lying about what the tick
    does. Something in the box that is not a list of calls is said as that rather than drawn as
    one.
56. **The label panel says what is wrong with the label before it asks whether it is right.** The
    check (Requirement 33) is asked when a sample opens, and again whenever the label is rewritten,
    over the label as it stands rather than as it arrived; its sentences are shown above the two
    verdicts, in the service's own words. A page that worded the fault itself would be a second
    opinion about what a callable label is. It warns and never blocks — the reviewer may still say
    the label is correct, and a corpus of hard rows is the corpus worth labelling — and a check
    that could not be made is said as that, because a warning nobody could compute is not a label
    with nothing wrong. The panel's own answer (Requirement 35) is offered into the label box
    beside it, verbatim: a consensus a reviewer agreed with was already on the screen as JSON, and
    retyping a call by hand is how a label two models had spelled out in full shipped as a bare
    name. Taking it is saying the label is being rewritten, so it ticks *modify* and opens the
    editor rather than filling a box nobody can see.
57. The drawing and the UI are two files and neither is generated from the other. `index.html`
    explains the flow — its rectangles carry prose about why each step is shaped as it is — and
    `ui/` labels with it. The cost, stated: a change to the flow is drawn in one and driven in the
    other, and the drawing is the one that goes stale silently, because no test drives either.

## Design

**Where a body lands.** The modality declares; the profile answers; the service composes. Every
socket gets its body in `profile/tool_decision/<part>.py`, and a method with a body in `modalities/`
is a rule shared across every task that modality serves. `verdict`, `find_exact_match_consensus` and
`find_llm_judge_consensus` are three of them, because a strict majority is arithmetic and does not change
with the question being asked. `PersonalDataChecking` holds two more. `PiiRuleDetector` is the
rule scans as one thing that detects — where two of them claim one value the first keeps it, so the
order and the rule are one object — and which scans, in what order, is the input's; the four are
its default. And `confirm_pii_by_llm`, with
`PiiLlmConfirmer` and the prompt it sends, is **the confirmation**: whether a detected value really
is personal data is a question about personal data and about nothing else, so every task asks it
the same way and gets the same narrowing — a value that was not detected is discarded, and an
answer that did not come back, or came back the wrong shape, confirms none. Neither varies by
task. Which model confirms does, so a checker is *constructed* with the declaration its
request carried, and the confirmation resolves it in `__init__`.

`services/tool_decision/` is what an endpoint calls: `detect_personal_data`,
`redact_personal_data` and `check_label_calls` in `data_quality.py`,
`predict_tool_decision_by_llm` and `predict_tool_decision_by_sft` in `ai_review.py`. Each takes a config and one sample and constructs
the profile class it needs — a config, not a built object, because the config is the only thing
that varies and a bag of pre-built reviewers passed between layers is one more thing to keep in
step. A `None` config is a
reviewer the deployment did not declare and answers `None`. `report_duplicates` and
`report_abnormalities` take a sample and nothing else: neither declares a shape to return, so neither
has a model to ask. `check_label_calls` takes the label and the catalog and nothing else, because
those are the two things the rule reads and a reviewer rewriting a label has not got a sample yet.
A handler is then three lines: read the body, call one function, map `ConfigError` to 422.

**Personal data is one socket and three functions beside it.** `detect` is abstract and the
profile writes the whole of it; replacing is not a socket, because a copy with placeholders in it
is one rule rather than a question two tasks answer differently. It sits in the profile beside
`detect` and not in the modality, and the reason is only that it has one caller: none of the three
names anything a task knows — `replace_node(node, pairs)` walks strings, mappings and lists — so
the day a second task replaces anything they move up a layer unchanged. A shared body with one
user is a body nobody has held against a second question. It is written once and reached twice: `read_span_values` reads what each placeholder stands for off `review_text` — the only thing a
span's offsets are good for — `replace_text` puts the placeholders into one string longest value
first, and `replace_node` walks a record doing the same to every string under it. The second
reach is the one the offsets cannot have: a span indexes `review_text`, and `messages`, `tools` and
`label` are other strings, so the rule that carries a confirmed value into them is replacement *by
value* (Requirement 12). What a
sample is scanned *as* is the task's answer, not the modality's: a tool-calling sample is its turns
plus the catalog it was offered, and a base that composed the text from turns alone would be wrong
for the only task there is. So the input carries the sample whole, and the
methods it is written out of are the profile's own, each declared because it is a rule worth naming
and none of them a socket. `build_review_text` builds the frame of reference.

**A detector is an object that detects, built when the checker is, and a method that asks it.**
`PiiRuleDetector` holds the scans and their order — where two claim one value the first keeps it,
so the order and the rule are one thing. `PiiLlmDetector` and `PiiLlmConfirmer` are each one
class over the same resolved model — a prompt in, its own answer out, like the rule detector beside
them — differing in the prompt they send and the shape they ask their model for: `PiiLlmDetected` is a
`{text, label}` per value, `PiiLlmConfirmed` a list of values. **A model's
answer is a declared shape**, in `data_quality/schema.py` beside every other shape here, so reading
one is a validation with a message rather than a walk through `isinstance` that ends in an empty
answer nobody can explain. Each is built once per checker and not once per record — the scan set is
the task's and the config file is the same file every time, so one checker over a corpus reads
`config/model/<name>.json` once, and a name with no config and no endpoint is refused before the
first record rather than during it.

Both detectors are asked directly and both are built with the checker: no method stands in front
of one to hand it its prompt, because a method whose body is one call and one filter is a name and
not a rule. `PiiLlmDetector.detect` takes the prompt and the review text, and drops a value that is
not in that text verbatim — the check belongs where the answer is read, since the whole of what is
read is a claim about that text. `pii_detect` takes the text and the language and unions the two
into what a reviewer is shown as detected, `find_and_number_spans` turns
that into numbered spans, and `confirm_pii_by_llm` — the modality's — narrows those to the ones that
ship, each carrying the reason it was confirmed for. Each prompt is built by a `build_..._prompt` method named for the step that sends it, and
outside the `try` that swallows a failed call, so a missing prompt file is a `ConfigError` rather
than a record quietly answering nothing. Which endpoint a step reaches, and the call
itself, are that step's own class: it takes the `<X>ModelConfig` a request carried, resolves it in
`__init__` — so a name with no endpoint is refused before the first record — and its one method
makes the call, reads its shape back, and answers nothing where a model said nothing. The rule is
therefore written once per asking class rather than once for the codebase, which is the price of
each class holding the whole of its own asking.

**AI review.** `verdict` calls `predict` once, counts agreement over the returned votes, then asks
`find_exact_match_consensus`; only where that is `None` does it ask `find_llm_judge_consensus`. The judge reads
the answers, not the conversation. `predict` builds the prompt and makes the call, both in the
profile, so the prompt and the shape it must return are read in one file.

The asking is one class per step there, on the same terms as the scan's: `ToolPredictor` is one
juror, resolving its own model when the panel is built — so a name with no config file is refused
before the first sample — and reading back a declared shape, `LLMReviewerAnswer`. What the modality
keeps is the arithmetic over what they said: the strict majority, the agreement count, and the
narrowing that lets a judge return only an answer some juror gave.

*Whether two answers are the same* is the third thing, and it is neither arithmetic nor a call, so
it is the third socket: `normalize_prediction`. The modality declares it and declares nothing about
it — `modalities/text2text/` serves any text2text task and cannot know that a tool call exists, so
the whole rule for reading one lives in `profile/tool_decision/ai_review.py` beside the prompt that
asked for it. It is one method and not a chain of named helpers: reading the calls, matching them,
and falling back to text where none is readable are one rule, and a method whose body is a single
`return` of another function is a name rather than a rule. That is also what leaves
`judge_prediction` answering `None` here: a panel whose answers can be matched needs no model to
match them.

**One record, and only at the end.** The UI holds the eight answers and composes them into one
record. Nothing else composes one: a handler answers for its own part and knows nothing about the
others, which is what makes each endpoint drivable by itself. `llm` and `sft` are the names the
votes carry; `personal_data`, `duplicate` and `abnormal` are the three checks' own. No pydantic
model declares the envelope.

**Which models a deployment serves, and which a request asks.** A model is served when
`config/model/<model name>.json` exists — `edge/served_models.py` reads that directory and nothing
declares the names a second time, so the list cannot disagree with what is actually configured.
`GET /models` is that list, the UI ticks from it, and a request carries the names it ticked. A
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

**The page that draws the flow.** One file, `edge/static/index.html` — markup, style and script
inline, no build step and no npm, nothing loaded from a CDN. Every shape in it is read off the
tree, and the span offsets are found with `indexOf` rather than written down, so the check button
can always reproduce them. It calls nothing: what each rectangle shows is recomputed in its own
script, which is what makes it readable as a description of the flow and useless as a labelling
tool.

**The labelling UI.** `src/dataforce/ui/` — `index.html`, `style.css`, and `app.js` loading
twelve ES modules — mounted by `create_app()` with Starlette's `StaticFiles` at `/ui`, so one
process serves the API and the tool that drives it and a labeller needs nothing installed.
Fourteen files rather than one, because a 1763-line script is the condition under which nobody can
tell which half of a change broke something; still no build step and no npm, so what is deployed
is what is written. `app.js` is the composition root and nothing imports it.

Inside the package and not at `src/ui/`, because `[tool.hatch.build.targets.wheel]` declares
`packages = ["src/dataforce"]` and ships every file under it — which is how
`edge/static/index.html` reaches an install. A directory beside the package would need a
`force-include` entry to ship at all, and a UI that is missing from the wheel is a UI that works
until someone installs the thing.

What it holds is one function per rectangle's worth of behaviour and one `fetch` per route, and it
holds no rule: the spans, the votes, the copy, the outcome and the redacted record are the
service's answers, rendered. The record at the end is the exception the spec already names — the
page composes it (Requirement 3), because nothing else does.

Each rectangle is in one of four states — untouched, waiting, answered, refused — and a fifth
sentence it can say instead: *not asked*, for a step whose button was pressed before it had what it
needs. That is not a refusal and is not marked like one, because nothing was called and so nothing
refused anything, and someone reading *refused* would go looking through a service log for a
request that was never made. A refusal is a 422's own `detail`, in the rectangle that asked, with
every other rectangle's answer left standing.

One rule does live in three places, and it is the containment Requirement 11 states: the scan
applies it to what it detects, the drawing draws it, and the UI's `auto` toggle applies it to the
rows the reviewer moved (Requirement 41). That is the cost of a reviewer being able to edit an
offset at all — a row they typed has to be resolved against the rows beside it, and only the page
knows which rows those are. It is the one rule two sides hold, and it is stated here so the next
person reading § *Invariants* knows what the claim does not cover.

**No store yet, and the record therefore stops at the page.** Where a reviewed record is kept is
one decision with several halves -- the table, the route that takes it, and which records are
refused -- and it is not this spec's (§ *Out of Scope*). Where the
redaction runs is not among them: it is a route (Decision 24), which is what the record's
three `new_` keys are answered by. Nothing above depends on it: every step answers its own
call, and the record is what the page composes out of those answers.

What that leaves is the consequence of keeping both halves, stated once because it does not depend
on where the record lands: it holds the personal data verbatim under `messages`, `tools` and
`label`, so the redaction protects a reader of the three `new_` keys and nothing else. Anything
holding the record holds the values.

What a reviewer let through is the page's to show, beside the reviewer who did it. Two cases it
draws and neither side resolves: unticking a span leaves its value in the record, which is then
redacted as far as the reviewer allowed and no further; and unticking a value another kept value
sits inside cuts it in half, because replacement is by value across every field, so a phone inside
a kept email becomes `minh<PHONE_1>@vd.vn`. Which of the two wins is not decided.

**Files.**

| file | change |
|---|---|
| `modalities/text2text/ai_review/llm_prediction.py` | bodies for `verdict`, `find_exact_match_consensus`, `find_llm_judge_consensus`; the `judge_prediction` and `normalize_prediction` sockets |
| `modalities/text2text/data_quality/personal_data_checking.py` | `PiiRuleDetector`, and `PiiLlmConfirmer` — which resolves its own model and makes its own call |
| `modalities/text2text/data_quality/schema.py` | `PersonalDataCheckingConfig`, `PersonalDataCheckingInput`, `Language`, `RuleScan`, `SCAN_FUNCTIONS` and the `SCANS` a config defaults to |
| `services/tool_decision/data_quality.py` | builds the scan's input, turns a record it cannot read into a `ConfigError`, and runs the replacement over the record the reviewer left |
| `modalities/text2text/ai_review/SFTmodel_prediction.py` | the `predict` socket, and nothing else: comparing two answers needs what a task knows |
| `profile/tool_decision/ai_review.py` | `ToolPredictor`, `predict`, `build_tool_prediction_prompt`, and `normalize_prediction` — the rule for matching two answers as calls |
| `profile/tool_decision/data_quality.py` | `detect`, the two detectors, and `order_claims_by_class`, `find_and_number_spans`, `read_span_values`, `replace_text`, `replace_node`, `decide_replacement_outcome` |
| `profile/tool_decision/label_statistics.py` | `list_label_faults` — BFCL's AST check answering sentences, which the store reads as `schema_valid` and the page reads as the warning |
| `profile/tool_decision/utils.py` | `list_conversation_turns` and `build_review_text`, which both parts read, and the two directions of the OpenAI tool format: the catalog as text, and text as calls |
| `config/prompts/profiles/tool_decision/pii_llm_detect.txt` | what the second detector is asked |
| `config/prompts/modalities/text2text/data_quality/pii_llm_confirm.txt` | the spans the confirmation is shown, and the `{id, reason, confirmed}` it answers |
| `ui/index.html` | every element the page has, and the one place an id is declared |
| `ui/style.css` | the layout, and the states a region can be in |
| `ui/app.js` | `wiring` · the composition root: every handler, the keyboard, the first paints, and the page's reaction to a change |
| `ui/wire.js`, `ui/screen.js` | `adapter` · one call and one reading of a refusal; that the page is a DOM at all |
| `ui/held.js` | `shape` · what the page holds between one sample and the next |
| `ui/record.js` | `logic` · the one thing this page composes |
| `ui/conversation.js`, `ui/checks.js`, `ui/models.js` | `adapter` · a turn, a call and a label drawn; the two checks; which models answer |
| `ui/personal-data.js`, `ui/label.js`, `ui/facets.js` | `adapter` · card 1; card 2 above the facets; the facets |
| `ui/queue.js`, `ui/importing.js`, `ui/corpus.js` | `adapter` · which sample is next; how a corpus gets in; what is already stored |
| `edge/main.py` | mounts `ui/` at `/ui`; it is `wiring`, which is the layer allowed to know both |

## Decisions

1. **Three axes: declare, answer, compose.** `modalities/` declares, `profile/` answers a task's
   sockets, `services/<task>/` composes one endpoint's full logic, and the router is thin.
   Alternative: let the handler compose the parts. Then the composition is only reachable over
   HTTP, cannot be tested without a client, and `edge/` grows the task's logic — while every
   endpoint's handler grows a second reason to change. The cost, stated: one more layer to open when
   following a call.
2. **Every step is independent, and the record exists only at the end.** Alternative: thread one
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
8. **The catalog is rendered by `convert_tools_to_text` for both parts.** Two renderers would be
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
15. **The page is static files the edge serves.** Alternative: a Vite app under `ui/`. A build
    step and a lockfile are a mouth to feed (`T-3`). The decision stands on that reason alone now:
    the other half of it — *for a skeleton meant to be deleted* — has expired, because the page is
    the labelling tool and nothing plans to delete it. What the build step was wanted for is file
    boundaries, and native ES modules give those with no lockfile and nothing to run.
16. **`auto` on step 5 is the outermost rule, not a confidence threshold.** It is the same rule spans
    are resolved by inside `detect`, applied again where a human did not override it.
17. **The language is declared, not guessed, and it is one of the two the scans know.** Alternative:
    detect it from the turns. A detector is a rule to write, test and keep, and it answers a
    mixed-language chat by guessing. `agent_toolkit`'s scans key their tables by `vi` or `en`, so
    `PersonalDataCheckingInput.language` is that choice and nothing else — `Tiếng việt` spelled out
    is a `KeyError` from inside the library, so the shape refuses it and `personal_data_scan` turns
    that into a `ConfigError` and a 422 rather than a 500. It defaults to `vi`, the language this
    corpus is in, so a record that says nothing is scanned in Vietnamese rather than refused. Every
    rule scan and both model steps take that one value. `ReviewRequest` declares the same field for
    the jurors' prompt slot: symmetric with the scan, and one vocabulary for both requests rather
    than a free-text language on one endpoint and a checked one on the other. Inside the parts it
    is text, because only the scans key a table by it.
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
    hands those back with its edits, and `redact` answers `{sample, review_text, outcome}`. The cost,
    stated: the detect answer carries `claims` as well as `spans`, and the page round-trips both.
    Without them the outcome could only say *nothing was handed over*, and a scan whose every
    candidate was dropped — both model steps failing, or a reviewer unticking the lot — would
    read `reported`, which is the word for a clean record.
20. **Two answers are the same when the calls in them are the same calls, and this task asks no
    judge.** An answer here is a tool-call array, so sameness is a rule and not a judgement:
    `ToolDecisionLLMPrediction.normalize_prediction` reads the calls out of what a juror wrote and
    matches name and arguments, in one method. It lives in the profile because the modality serves
    any text2text task and a layer that cannot know a tool exists cannot be the one to compare two
    of them; `normalize_prediction` is the socket between the two. The same rule is why
    `SFTPrediction` declares no comparison of its own: the finetuned reviewer's agreement with the
    label is a task rule, and it lands when that reviewer's half does.
    Alternative, built and then taken back out: a `judge_model` request key with its own prompt,
    asked wherever no answer won a majority. It was a model call, and a bill, paid to decide
    something arithmetic — and worse, most of what it was asked to resolve was never a
    disagreement at all, only two jurors spelling one answer differently. What is left after the
    matching is two genuinely different calls, and Decision 9 already says what a model would be
    doing there: casting the deciding vote without having read the conversation. So the socket
    stays in the modality for a task whose answers can only be compared as meaning — a summary —
    and this profile answers `None`. The cost, stated: the calls are matched *unordered*, so a
    corpus whose calls must run in the order they were written would read two answers as one, and
    the `sorted` in `normalize_prediction` is the one line that would change.

21. **Two pages: one draws the flow, one drives it.** `edge/static/index.html` is read by whoever
    is building this and answers *what is each step handed, and what does it answer*; `ui/` is
    worked in by whoever is labelling and answers *what did this sample come to*. Alternative: one
    page doing both, which is what it would become — the prose that makes the drawing readable is
    noise in a tool used every day, and the loading states that make the tool usable are noise in
    a description. The cost, stated: two files to keep in step, and the drawing is the one that
    rots quietly, because no test drives either.
22. **Static files, no build step, inside the package.** Alternative: the `ui/` layout with npm
    and a bundler. That buys components and a dependency tree, a second toolchain in the gate,
    and a `dist/` that can disagree with its source; the file boundaries it is really wanted for
    are what `<script type="module">` already gives. Inside `src/dataforce/` because the wheel
    ships every file under the package and nothing else, so a UI beside it would be missing from
    an install. Reversible: it is a directory and a mount.
23. **Approve posts nowhere, and says so.** Alternative: have approve write the record somewhere —
    a file, a queue, the store that was just deferred. Every one of those is the store's decision
    taken in the UI, and the UI is the last place that decision should be made. So approve froze
    the record and showed it until there was a store with a route of its own — and then that one
    rectangle changed and nothing else did, which is what deferring it bought.

24. **The redaction of the three `new_` keys is a route.** `POST .../personal-data/redact` takes
    the sample as the human left it and the spans they handed back, and answers the copy. The UI
    then composes the record out of it, which keeps Requirement 46 whole: the page renders answers
    and composes the record, and holds no rule.
    Alternative, and the one the drawing already does: the page walks the record replacing by
    value. It needs no route, and it is what `edge/static/index.html` is written with. The cost is
    the whole of why it was not chosen — a redaction rule living in the client, where a caller who
    skips it gets a record that says it was redacted and was not, and a second definition of
    replacement to keep in step with the service's. The rule was the service's before the store was
    deleted, in `replace_node`; this puts it back in the service rather than in the page. The
    cost, stated: a route nothing but this UI asks for yet, and the store's decision may well
    absorb it — at which point this is the endpoint that changes, not the page.

## Versions

No new dependency. FastAPI `>=0.141.1` serves the page through Starlette's `StaticFiles`.
`sqlalchemy >=2.0.52,<2.1` stays declared in `pyproject.toml` and nothing here imports it: it is
the store's, and `docs/tool-decision-store/spec.md` is what it is spent on. Nothing declares
`alembic` beside it, because that store has no migrations.

## Invariants

- Every span offset indexes the exact string in `PersonalDataDetected.review_text`. Check: slicing by a
  span's `start`/`end` yields the value it was made from.
- No span offset indexes the redacted copy. A placeholder is not the length of the value it
  replaced, so the two strings do not share offsets, and only the detect answer's `review_text` is
  a span's frame of reference — which is why a second scan of a redacted record is a second
  `detect`, never the old offsets read against the new text.
- One value gets one placeholder throughout a scan. Check: the map replacement runs over is keyed
  by value, so two spans carrying one placeholder are two entries and both values are replaced.
- No span survives inside a longer span. Check: no pair where one range contains the other.
- No juror sees another juror's answer. Check: `predict` builds each juror's prompt from the sample
  alone.
- `find_llm_judge_consensus` returns only a string some juror wrote, or `None`.
- Two answers with the same calls are one answer. Check: `normalize_prediction` is insensitive to
  the order of the calls, to prose around them, and to whether arguments arrived as an object or as
  JSON text; it reads nothing off a call but its name and its arguments.
- No module under `modalities/` names a tool call. Check: the answer shapes and the arithmetic
  there are written in terms of *an answer*, and every rule for reading one is in the profile.
- What a human step returns differs from what it was given only where the human changed something.
- No endpoint's response mentions a part it does not own. Check: each response model is one part's
  own shape.
- The UI holds no rule the service holds. Check: nothing under `ui/` computes a span, a consensus,
  a copy, an outcome or a redacted record — each of those is a field a module read off a response.
  The record it composes is the one thing nothing else composes, it composes it out of answers, and
  `record.js` is the only file under `ui/` tagged `logic`.
- One rule turns a value into a placeholder. Check: `replace_text` is the only place a value is
  swapped for one, `replace_node` is that rule over a record's strings, and both are handed the
  same `{value: placeholder}` pairs `read_span_values` read off `review_text` — which is also the map
  the outcome is measured against, so what was replaced and what counts as replaced cannot drift.
- Property order is preserved through `convert_tools_to_text`, so text re-rendered from the same
  tools is byte-identical.

## Error Behavior

- A juror call that fails is dropped from the vote list. The panel is smaller and `votes` says so; it
  is never an empty-label vote.
- Every juror failing gives a verdict with no votes, `label_agreement` 0.0 and `consensus` `None`. A
  valid answer, not an exception, and no judge is asked about an empty list of answers. Each juror
  that failed is one structured event on stdout naming it, so a panel that shrank is readable from
  the output and not only from `label_agreement`.
- A tie that survives the matching leaves `consensus` `None`. Nothing is asked about it: this task
  answers `judge_prediction` with `None`, so a panel that disagreed costs one call per juror and
  no more.
- A model call that fails answers nothing, and so does an answer that is not the shape the step
  asked for — one `except` covers both, because for the caller they are the same fact. Neither
  step raises: a failed detection leaves the rule scans' values, and a failed
  confirmation confirms none, which leaves every claimed value still standing in the copy. Either
  way it is a structured event on stdout naming the step that was asking and what went wrong
  (H-6); `outcome` is `withheld` where a rewrite was asked for.
- A value a detector returns that is not character-for-character in the review text is dropped, and
  an answer the confirmation returns about a span nobody showed it is discarded.
- A label the human typed that is not JSON is carried as `{unparsed: <text>}`. It is never dropped
  and never guessed at.
- One part failing fails that one call. The page keeps every answer it already has, and the step is
  re-runnable on its own.
- A request that ticks `sft_model` is refused with 422, and refused before the panel is asked. The
  name may well be served — `checked_names` passes it — but `ToolDecisionSFTPrediction.predict` has
  no answer to give while § *Open* stands, and a declaration this service cannot act on is a
  `ConfigError` here as everywhere else on the route. Its message says *unimplemented* rather than
  *unserved*, so the two refusals do not read alike.
- A handler stays thin: it calls the part and maps the error through `errors.py`.
- A call the UI makes that fails shows the service's own `detail` in the rectangle that made it,
  and every answer the page already holds stays. The step is re-runnable from its own button. The
  UI retries nothing by itself: a second call is a person pressing the button again.
- A rectangle asked before it has what it needs — no sample read, no verifier ticked, a span row
  that does not parse — says *not asked* and names what is missing. It is not a refusal and does
  not read as one: nothing was called, so no answer was withheld, and someone reading *refused*
  would go looking through the service's log for a request it never received.
- The redaction route asks no model, so nothing about it can be refused for a name this deployment
  does not serve. A body it cannot read is a `ValidationError` at the boundary and 422 in the
  rectangle that sent it — which is what a label edited into something that is not a list of
  messages comes back as.

## Testing Strategy

- `detect` over a hand-written sample: overlap resolution picks the declared first scan; a value said
  twice gets one placeholder; a span inside a longer span is dropped; every returned offset slices
  back to its value; the redacted copy replaces the longest value first.
- `find_exact_match_consensus`: two of three matching gives that answer; two-two gives `None`; a mode that
  is not a strict majority gives `None`.
- `verdict` with a stubbed `predict`: agreement counted over returned votes only, a failing juror not
  counted as agreement.
- `normalize_prediction`: the same calls in a different order, with prose around them, with the
  wire format's extra keys, or with arguments as JSON text are one answer; another tool, another
  argument value, or one call where another answer made two are not.
- `find_llm_judge_consensus`: not asked where the exact match answered, and an answer no juror wrote
  refused — the modality's rule, proved over a stubbed `judge_prediction`, since this task's own
  answers `None`. A juror that fails is read back as one event on stdout.
- `convert_tools_to_text` pinned against its known rendering, and `parse_text_to_tools`
  against the shape it reads a call into — which spellings of a call are one call, and which are two.
- Each endpoint through `TestClient` with the model calls stubbed, called with nothing but its own
  arguments — no fixture threads one payload through several of them. Which models may be ticked is
  a directory, so it is stubbed as one: `DATAFORCE_MODEL_DIR` pointed at files the test wrote,
  before the app is created. The two 422s are pinned apart — a name the directory does not hold,
  and a name it holds whose file declares no endpoint — and both are proved to happen with a
  `complete` installed that fails the test if it is reached.
- The `PersonalDataDetected` the replace route takes back is written out in the test, not fetched
  from the detect route: it is one part's second call, and a fixture that fetched it would be the
  threading Requirement 1 forbids.
- The redaction route over the same written-out `PersonalDataDetected`: a value handed back is
  replaced in the turns and in the label's arguments, a field it was not in comes back as it
  arrived, a corpus key nothing here reads comes back under its own name, and no span handed back
  answers the sample unchanged. Its own rule is pinned in the profile's tests as well — that the
  longest value goes first here too, that a value the reviewer dropped is readable in the copy,
  and that a node holding no string is copied rather than stringified.
- The label check over a hand-written label and catalog: a bare tool name, a call naming a tool the
  catalog does not offer, a call leaving out a required argument, and a required argument carrying a
  default are each pinned to the sentence they answer — a fault that does not name which call it is
  about is one nobody can act on. Every broken call is reported and not only the first, because a
  reviewer told about call 1, who fixes it and is then told about call 3, has been sent round the
  loop once per fault. The route and the stored column are checked against *one another* over the
  same label, which is the only way to prove they are one rule.
- **The drawing is driven by nobody; the UI is.** A browser is still the check for what either one
  *looks* like, and a test says of the drawing only that it is served. `ui/` is loaded in node as
  the modules a browser loads, against a DOM stub (`tests/ui/dom.js`), driven from pytest by
  `tests/ui/test_page.py`, so
  every sentence this spec makes about the page is a check that fails when the page stops saying
  it. Two things are read off the files rather than driven: `GET /ui/` answers the UI's
  `index.html`, and no model name the drawing writes down appears anywhere under `ui/`, because the
  second declaration of what this deployment serves is the one that would arrive by someone copying
  that line across (Requirement 50).

## Out of Scope

- `CommonAbnormalChecking.check_verdict`'s body. It declares no shape and this spec invents none.
  `DuplicateDataChecking` stood beside it and is gone: duplicates are a fact about a corpus, so the
  one implementation lives in `modalities/text2text/dataset_management/`. The `duplicate` step
  still answers `null`.
- Auth, rate limiting, and batching. **Not the corpus**: importing a file of samples, walking it
  one at a time and tracking which are done is `docs/tool-decision-store/spec.md` § *Raw data in*,
  which is also where the labelled ones go. Every route here still takes exactly one sample, which
  is what kept that decision separable from this spec.
- Which models the panel asks, and how many. A composition is a deployment's declaration, and
  nothing in this spec picks one.
- **The store, and everything that answers for it.** Where a reviewed record is kept, the route
  that takes it, which records are refused, and the schema management under all of it — one
  decision, and not this spec's: a route nothing may post to is worse than no route. That decision
  is `docs/tool-decision-store/spec.md`, and it has been taken — two tables, `POST .../records`,
  and a precondition that refuses a sample whose steps did not run.

## Open

**Where `SFTReviewerVerdict.confidence` comes from.** The shape carries one, `tool_prediction.txt`
asks for none, and `agent_toolkit.llm.complete` answers with text and no logprobs — so a number
put there today would be invented rather than measured. Either the finetuned reviewer gets a prompt
of its own asking for `{reason, label, confidence}`, or the shared prompt grows a key every juror
answers and nothing reads. Until that is settled `ToolDecisionSFTPrediction.predict` gives no
answer: `POST .../ai-review` answers `sft: null` for a request that ticks none, and refuses one
that ticks a reviewer with 422 — this deployment serves none, which is a declaration it cannot act
on rather than a failure inside a call. Its comparison against the label waits with it: that rule
needs to know what an answer is made of, so it belongs beside the prompt that asked for one and
not in the modality.

Everything else this spec opened has an answer above; the one thing left to another is the store,
under Out of Scope.
