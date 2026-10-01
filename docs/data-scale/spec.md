# A value a call passes is a slot, and a slot can be filled again

## What

A ninth step for `tool_decision`, and one act inside it.

**The step.** Once the label is settled, every value the sample's tool calls pass becomes a numbered
slot — `<SVCCALCULATEINTEREST__PRINCIPAL_AMOUNT_1>` where `800 triệu` stood — so that one labelled
conversation can be re-filled with a hundred different amounts afterwards and teach a model the
argument rather than the number. Two detectors find them: a rule scan that takes the settled
label's own argument values and searches the conversation for each, and a model for every mention
that is *not* those characters — half a phone number, a number said wrongly, one district out of a
longer location. A confirmation reads the numbered spans back, one at a time, and only what it
confirms reaches the reviewer. What happens to the claims afterwards is the arithmetic the
personal-data step already runs: the same numbering, the same containment rule, the same tick per
place, the same replacement, the same outcome.

**The act.** From that slotted sample, a model writes **one** new conversation using the same
catalog and the same slots. The reviewer edits it, runs the three cards over it, ticks its facets,
and one Submit writes the source and every generated conversation — **one row each**, never a row
holding a list of conversations.

What is *not* here: filling the slots back in. This step makes a corpus fillable; multiplying it is
somebody else's program reading the exported file, and § *Out of Scope* says so.

## Context

### What is already true, measured

Taken on 2026-09-28 at `21edf7d`, over `tool_decision_dataset` — 40 stored rows.

- The `personal_data` facet carries **32 distinct kinds**. Three of them (`EMAIL`, `NAME`, `PHONE`)
  are kinds a rule scan declares. **Twelve** are shaped `<TOOL>__<ARG>`. The rest —
  `CAR_PRICE`, `DOWN_PAYMENT`, `INTEREST_RATE`, `LOAN_TERM`, `WEIGHT`, `DELIVERY_OPTION` — are
  argument values too, named without the prefix.
- Of the twelve, eleven name a tool standing in that row's own catalog and one of that tool's own
  arguments. The twelfth, `SEARCH_PLACE_27D__DISTRICT_LOCATION`, names the tool and an argument
  it does not have — and **that one is the interesting one, because it is deliberate and it is the
  pattern.** The argument is `location`; the turn said a district and not the whole location, so
  the reviewer wrote a qualifier in front of the argument's name. The same row carries
  `SEARCH_PLACE_27D__LOCATION` beside it, and the two are one argument mentioned two ways. The
  corpus holds the same move on the personal-data side: `WRONG_PHONE` and `WRONG_ID_NUMBER` are a
  phone number and an ID the customer said incorrectly, filed so that the class **reads and is
  understood without opening the row**.
- So a class is not always `<TOOL>__<ARG>`, and the step is not always a search. A conversation
  mentions an argument's value in part (`PART_PHONE_NUMBER`), wrongly (`ERROR_PHONE_NUMBER`), or
  as one component of it (`DISTRICT_LOCATION`) — and none of those three stands in the record
  character for character beside the value the call passed. **Nothing that only searches for the
  argument's value can find them**, which is why this step has two detectors and not one.
- Inside the calls themselves, **31 of 44 argument values already stand as a slot placeholder** and
  13 are still bare. Thirty of the 40 rows carry no bare argument value at all.
- The placeholders for those kinds stand under `messages` 23 times and under `label` 6 times, and
  under `tools` never.

So the step specified here is one a reviewer has already been performing **by hand**, through card
1's *Offer this kind* box, on three quarters of the corpus. This does not invent a practice; it
gives one that exists a step of its own, a scan that proposes instead of a box that is typed into,
and a facet that does not count an interest rate as personal data.

**Six rows carry the consequence today** — a kind on `personal_data` that is a scale kind:

| row | the kinds |
|---|---|
| `cab00d87…` | `CAR_PRICE`, `DOWN_PAYMENT`, `INTEREST_RATE`, `LOAN_TERM` |
| `f448ebb7…` | `DELIVERY_OPTION`, `WEIGHT` |
| `fa519155…` | `SVC_TRACKFITNESSPROGRESS_1D6__ACTIVITY`, `…__CALORIES_BURNED`, `…__DURATION` |
| `1722d009…` | `CALCULATE_DELIVERY_COST_9E8__DELIVERY_OPTION`, `…__WEIGHT` |
| `b81aac81…` | `SVCCALCULATEINTEREST__INTEREST_RATE`, `…__PRINCIPAL_AMOUNT`, `…__TIME_PERIOD`, `SVCGETCONTACTINFO__NAME` |
| `d0d01db5…` | `SEARCH_PLACE_27D__DISTRICT_LOCATION`, `…__LOCATION`, `…__NAME` |

### What the code already has

The arithmetic. `profile/tool_decision/data_quality.py` holds nine functions that are about
*values, classes and spans* and mention personal data only in a field name:
`walk_record_strings`, `find_spans_in_text`, `name_placeholders`, `find_and_number_spans`,
`replace_spans_in_text`, `replace_node`, `group_spans_by_path`, `order_claims_by_class`,
`decide_replacement_outcome`. None of them is a judgement about a value; every one is a fact about
where a string stands in a document, and both steps need all nine. `C-7` — *do not split before a
second consumer needs half of it* — is why they move into a module of their own now and did not
before.

**What this step does not already have is the two detectors in front of them, and those are its
own.** Reading a settled label's arguments back into a conversation, spotting a mention that shares
no characters with the value, and naming a class a person can read at a glance are three questions
nothing in `data_quality/` asks or should learn to.

## Requirements

### The step

1. **Scaling is a step of its own and it runs after the label is settled.** Measured: a slot
   placeholder stands inside `label` 6 times across the corpus, against 23 times inside `messages`
   — and the label is what card 2 is for. A scan run before the reviewer settled the label would
   read a call they were about to replace.
2. **Two detectors over the same text, unioned — a rule scan and a model.** The same shape the
   personal-data step has, for a different reason.
   - **The rule scan is the label read back into the conversation.** It takes the argument values
     the settled label and the turns' own calls carry — values the reviewer has already looked at
     on card 2 — and searches for each one in the record. It is a search and not a guess: the call
     says what the value is, so a place that holds it character for character is a slot with no
     opinion in it.
   - **The model is for every mention that is not that string.** A turn that says half the phone
     number, says it wrongly, or says the district out of a longer location holds the argument and
     holds none of its characters in a row. A search finds nothing there, and those are exactly the
     rows § *Context* measures the reviewer filing by hand.

   Where both claim one value the rule scan's class wins, on the same terms the personal-data step
   settles an overlap. The model picker travels with card 3's button, like every other check's.
3. **Neither detector answers an offset.** A detector answers a value and a class; where that value
   stands, how many times, which nested span is dropped and which `<CLASS_N>` it gets are found by
   searching afterwards, through the one function that does it for both steps. A model counting
   characters is a model nothing here can check, and a value it did not copy character for
   character out of the text it was shown is dropped, because no offset can be found for it. This
   is what puts a `start` and an `end` on every row of card 3's table whichever detector claimed
   it — the reviewer reads one table and cannot tell, which is the point.
4. **A confirmation is asked over the numbered spans, span by span.** The same second pass the
   personal-data step makes, and it is what sets the precision: only a span it confirms reaches
   card 3, and each one carries the reason it was confirmed for. It is asked per span because the
   same characters are an argument's value in one line and a coincidence in the next — `2` the
   loan term and `2` in *2 người* — and a detector cannot tell them apart while a reader of the
   line can. It **only ever narrows**: an id no span carries is discarded, a span answered twice
   keeps the first answer, and a span nothing came back about is not confirmed, which is what a
   failed call and an answer of the wrong shape both come to. Nothing detected is nobody asked.
5. **It runs over the record the personal-data redaction left**, not over the sample as it arrived.
   The two steps replace into one document, and a span numbered against the unredacted strings
   would index a string that no longer exists by the time it is applied.
6. **After the claims, the arithmetic is card 1's, and it is the same code.** One placeholder per
   distinct value numbered `<CLASS_N>`, one span per occurrence over the whole record, a span
   inside a longer span dropped, a tick per place, replacement from the highest offset down, and
   `outcome` measured by counting placeholders in the string each span's `path` names. None of
   those is a decision that can differ between the two steps — they are facts about where a string
   stands in a document — and a second spelling of any of them would be the two rotting apart
   (`T-6`). **What may differ is everything above them**, and § *Design* draws the line.

### What is claimed

7. **The rule scan claims every argument value of every call the sample makes**, read from
   `messages[*].tool_calls[*]` and from the label as it ships. Both spellings of a call are read,
   the corpus's `{name, arguments}` and the provider's
   `{function: {name, arguments: "<json text>"}}`, through `read_named_function` — the reader
   `utils.py` already owns, so what a call *is* stays defined once. The label is read **as the
   reviewer settled it on card 2**, not as it arrived, which is the other half of Requirement 1.
8. **The model claims what the rule scan cannot reach: a mention that is not the value.** It is
   handed the review text, the arguments the rule scan read — tool, argument and value — **and the
   catalog**, and answers with the stretches of the conversation that mean one of them, each with
   its class and the reason written before it. Three cases, which are the ones the corpus already
   holds by hand: part of a value, a value said wrongly, and one component of a longer value.
   **The catalog is what makes the qualifier a reading rather than a guess.** `time_period` is
   described as *đơn vị tính là năm*, `principal_amount` as *format thuần số, đơn vị VND* — so a
   model shown the argument's own description can say *this turn gave months where the argument
   takes years* and name it, where one shown the value alone can only say the two strings differ.
   The risk is the mirror of that: an argument described at length invites a model to invent
   categories nobody asked for, so the prompt names the three qualifiers the corpus uses and says
   a fourth needs a reason. The reviewer overrules either way — the class picker on every row is
   the same control card 1 has.
9. **The class is `<TOOL>__<ARG>`, and a qualifier goes in front of the argument.** Each part is
   upper-cased with runs of whitespace written as `_`, which is the rule `namedKind` already
   applies to a kind a reviewer types; the tool name is the catalog's own spelling upper-cased,
   which is why `SEARCH_PLACE_27d` files as `SEARCH_PLACE_27D`. A mention that is not the whole
   value carries a word saying which — `<TOOL>__PART_<ARG>`, `<TOOL>__WRONG_<ARG>`,
   `<TOOL>__DISTRICT_<ARG>` — **so that the class reads and is understood without opening the
   row**, which is the reason the reviewer has been writing them that way. The qualifier is the
   model's to propose and the reviewer's to overrule; no rule reading the catalog could have
   invented one, and none tries.
10. **A value already standing as a placeholder is claimed like any other, and re-filing it is the
    point.** A customer's name passed as `SvcGetcontactinfo(name=…)` is personal data *and* an
    argument: card 1 replaces it with `<NAME_1>`, and card 3 then claims `<NAME_1>` and replaces it
    with `<SVCGETCONTACTINFO__NAME_1>` — which is exactly what the corpus already ships. The two
    steps chain, and the second overwrites the first wherever the value is an argument. Nothing is
    merged by this: `name_placeholders` keys by value, so two distinct placeholders are two distinct
    values and stay two. Where the claim order is unchanged the re-file is the identity — `<X_1>`
    comes back as `<X_1>` under its new class — and where it is not, the placeholder box on the row
    is the override, as it is for anything else.
11. **A value is claimed only where it stands character for character** — for the rule scan, and
    for the model, whose answer is dropped where it did not copy what it saw. `arguments` is JSON
    *text*, so a value holding a quote, a backslash or a newline is spelled one way inside the call
    and another way in the turn that said it, and the search claims it at the second and not the
    first. This is the same disagreement the pipeline spec measures for `review_text`
    (`Nguyễn "Nam" Văn`, twice in the record and once in the text), read from the argument side. It
    is stated rather than fixed: the reviewer sees one row fewer than they expected, which is a
    missing slot and not a leak.
12. **A short value is claimed at every word boundary it stands on.** `time_period: 2` claims each
    standalone `2` in the conversation and not the `2` inside `12`. Nothing narrows it, because
    nothing here can tell the two apart; **the tick per place is the answer**, and it is the same
    answer card 1 gives for `Nam` the given name beside `miền Nam`.
13. **The reviewer's three acts are card 1's three acts**, for the same reason and with the same
    words: re-file a value under another kind, name a kind neither detector proposed, and retype
    what a value stands in for. The corpus already shows why the second is needed —
    `SEARCH_PLACE_27D__LOCATION` and `SEARCH_PLACE_27D__DISTRICT_LOCATION` are one argument whose
    two mentions a reviewer chose to keep apart.

### The generation

14. **One press writes one conversation.** How many a reviewer wants is how many times they press.
    The route answers a conversation and never a list, so nothing anywhere holds *a batch of
    generated samples* as a shape.
15. **The prompt is a template in a box, and the service fills its slots.** The box opens holding
    the deployment's own file; the reviewer may edit every word of it. Whatever stands in the box
    when the button is pressed is filled with `{language}`, `{tools}`, `{conversation}` and
    `{slots}` by the same `slot_filling` every other prompt goes through. A slot the reviewer
    deleted is a fact the model is not told — that is theirs to do, and it is not an error.
    **This is also how two generations are made to differ.** Nothing here tells the second press
    about the first, and nothing tries: the box is edited between presses, which is a reviewer
    steering a corpus rather than a rule guessing at what variety means. A page that appended
    *and do not repeat yourself* would be inventing the one judgement this step exists to keep
    with the person.
16. **The catalog is not generated.** The new conversation offers the source's `tools`, verbatim.
    The point of the act is another conversation *for these tools*, so asking a model to invent a
    catalog would be asking it to invent the thing being held constant.
17. **The label is not generated either.** The model writes turns; what the last turn should call
    is what card 2 exists to settle, and a generated label arriving pre-settled is the panel's
    answer wearing the reviewer's name. The draft opens with the source's label on card 2's form,
    which is where a reviewer edits one already.
18. **A generated conversation is editable. An imported one is not.** The prohibition card 2 states
    — *a page that let a reviewer retype the turns is a page that can quietly make the sample agree
    with the label* — is about a conversation that **arrived**: it is evidence, and evidence is not
    edited. A generated conversation is not evidence. It is a draft the reviewer is authoring, and
    the label is settled from it afterwards rather than beside it. This rewrites a passage of
    `docs/labelling-ui/spec.md`; § *What this rewrites* says which.
19. **The generation is asked with the slotted, redacted sample and nothing else.** This is
    labelling-ui Requirement 20 read one step further along: a juror reads `<EMAIL_1>` and writes
    `<EMAIL_1>`, and a generator reads `<…PRINCIPAL_AMOUNT_1>` and writes it back. A model that had
    been shown the raw values would write raw values into a conversation nobody scanned.
20. **A generated conversation is a sample like any other.** It runs cards 1, 2 and 3 on its own
    and is stored under its own name. It has to: the store refuses a record whose `personal_data`
    is null, and a model asked to write a conversation about a customer will write a phone number
    into it whether or not the slots it was given held one.
21. **What the model wrote that will not read as turns is carried, never guessed at.** Same rule as
    a label the human typed that is not JSON: the text comes back beside an empty conversation, the
    reviewer sees what was said, and nothing is invented to fill the gap.

### The record

22. **`scale` is one more key on the record** — `ScaledValues`, what the step answered and how far
    replacing got, declared beside `ScannedPersonalData` and shaped like it without being it.
    Nothing else about the record moves, and a record written before this step reads back
    unchanged.
23. **`scale` is optional where `personal_data` is mandatory, and checked identically where it is
    there.** `personal_data: null` is refused because de-identification is a legal obligation the
    `dataset` table has to be able to prove; nobody has an obligation to scale anything, so
    `scale: null` is a record that skipped an optional step and stores fine. But a `scale` that
    *exists* and names a span whose placeholder is not standing where it says it stands is a record
    lying about itself, and that is refused in the same sentence and by the same function.
24. **`scale` is a facet, and it is a key in `notes` rather than a column.** It is computed from the
    step's spans exactly as `personal_data` is, lands in `notes` because it is not in
    `ToolDecisionSample.FACETS`, and is therefore counted by `count_by_note`, charted by the dataset
    sheet and readable on an opened row **with no schema change and no migration at all**. Making
    it a column later is one line in `FACETS` plus a rebuild of a derived table; making it a column
    now is that migration with nothing yet asking for it (`T-1`).
25. **A personal-data placeholder that scale replaced still satisfies the personal-data
    precondition.** This is the one thing Requirement 9 breaks and it has to be repaired here.
    `build_sample` refuses a record where a confirmed personal-data span's placeholder is not
    standing in the string its path names — and where card 3 re-filed that value, `<NAME_1>` is
    gone on purpose, replaced by `<SVCGETCONTACTINFO__NAME_1>`. Left alone, **every row where a
    customer's name is also an argument would be refused**, which is the commonest row this corpus
    holds. So the precondition reads the chain: a personal-data placeholder that the `scale` key
    claims as one of *its* values is satisfied by the scale placeholder that replaced it. The
    question the check asks is unchanged — *is the value the reviewer confirmed out of what ships*
    — and a placeholder swapped for another placeholder is still out. A record with no `scale` key
    reads exactly as it reads today.
26. **A generated row's `scale` is not empty, and that is how the chain stays readable.** A
    conversation generated from slots carries slots as its argument values, so card 3 claims them
    (Requirement 9), re-files each under the class it already wears, and replaces it with itself.
    The facet therefore names the slots the row carries, the same as its parent's, and a corpus
    reader asking *which rows carry `SVCCALCULATEINTEREST__PRINCIPAL_AMOUNT`* gets both. A
    generated row carrying a class its parent did not is one where the model invented a fresh
    value instead of reusing the slot, and the reviewer is looking straight at it.
27. **The six rows listed in § *Context* are re-reviewed by hand.** Re-opening one from the samples
    list and saving it writes the same key, so the row is replaced rather than duplicated, and its
    argument kinds move from `personal_data` to `scale`. No backfill is written: a rule that moved
    every `<TOOL>__<ARG>`-shaped kind would still leave `CAR_PRICE`, `WEIGHT` and `LOAN_TERM` where
    they are, so the automatic half of the job is the half that is not worth having.

### The screen

28. **Card 3, headed by its question, under card 2.** *Which values should this sample vary?* — the
    labelling-ui rule that a decision is a card headed by its question, and the order is the order
    the work happens in.
29. **One drawing of the keep table, used twice.** The seven columns, the tick per place, the kind
    picker on every row, the placeholder box and its two refusals are one behaviour; two copies
    would be the first screen where unticking a row meant two different things. The drawing takes
    the ids it writes into, so each card still owns its own ids and `ui/` Requirement 4 holds.
30. **The extraction lands first, with the screen frozen.** `tests/ui/page.js` passes unedited
    across the commit that moves the table drawing out of `personal-data.js`. That is the whole
    evidence that card 1 did not change while being made reusable, and there is no other way to
    get it — the repository's own rule, applied again.
31. **The generation box is a text area, a picker and one button**, and it is at the foot of card 3
    because that is where the reviewer is standing the moment the slots are approved.
32. **The generated conversations stand in a list under the box, and one Submit writes all of
    them.** The reviewer opens one, works it through the three cards, ticks its facets, and comes
    back; the list says which are finished and which are not. Submit posts **one `POST /records`
    per conversation**, the source first. Each says its own outcome on its own line. A refusal
    stops nothing already written, and re-pressing Submit rewrites the same keys rather than making
    second rows — which is what makes fixing one draft and saving again safe.
33. **A draft lives on the page and nowhere else.** Closing the tab loses every conversation
    generated and not yet stored, and the page says so beside the list rather than leaving it to be
    discovered. Making a draft survive a reload is a second store for a thing that already has one,
    and § *Open* is where it waits.

### The routes

34. **`POST /spans` and `POST /redact` move out from under `/data-quality/personal-data/`.** Neither
    is about personal data: one answers where a set of `(class, value)` claims stand in a record,
    the other replaces every handed-back span in one. Two steps now use both, and a URL saying
    *personal-data* while the scale card posts to it is a name that would have to be explained
    every time it is read. The page is the only client, and nothing stored carries either path.
35. **`POST /data-scale/values`** — the new route on the masking half. A sample, a language and the
    model that reads it; a `ScaleDetected` back, so card 3 can paint the moment it returns. A model
    name this deployment does not serve is 422 before anything is asked, like every other
    model-taking route.
36. **`POST /data-scale/conversation`** — one sample, one prompt, one model name, one language; one
    conversation back.
37. **`GET /data-scale/prompt`** — the deployment's template, unfilled, so the box can open holding
    it. It answers the file and never a filled prompt, so nothing a sample carries passes through
    it.

## Design

### The modules

| file | tag | holds |
|---|---|---|
| `modalities/text2text/value_spans.py` | `shape` | `ValueSpan`, the span both steps place, and the one field name the arithmetic reads |
| `profile/tool_decision/value_spans.py` | `logic` | the nine functions § *Context* lists, moved out of `data_quality.py` and owned by neither step |
| `modalities/text2text/data_scale/schema.py` | `shape` | `ScaleSpan`, `ScaleDetected`, `ScaleRedacted`, `ScaleScanningConfig`, `ScaleScanningInput`, `ScaleLlmDetected` |
| `modalities/text2text/data_scale/argument_scaling.py` | `logic` | `ValueScaling` — the socket `detect`, and the model detector's body |
| `profile/tool_decision/data_scale.py` | `logic` | `read_argument_claims`, `name_argument_class`, the three prompts, `ToolDecisionValueScaling`, `ConversationGenerator` |
| `services/tool_decision/data_scale.py` | `logic` | one function per endpoint |
| `modalities/.../dataset_management/schema.py` | `shape` | `ScaledValues` beside `ScannedPersonalData` |
| `modalities/.../dataset_management/sample_building.py` | `logic` | the optional half of the precondition, and the chain Requirement 24 names |
| `ui/spans.js` | `adapter` | the keep table, drawn into the ids it is handed |
| `ui/scale.js` | `adapter` | card 3's values: `scale-table`, `scale-verdict`, `run-scale`, … |
| `ui/generating.js` | `adapter` | the box and the drafts: `gen-prompt`, `gen-run`, `gen-list`, … |

**`data_scale/` is its own package under `modalities/`, and this is the reviewer's decision rather
than a reading of the rules.** The argument for sharing is that scaling's shapes are
personal-data's shapes with one field renamed. The argument that wins is the one that says these
two will not stay alike: **a value being personal data and a value being worth varying are
different questions about different sets** — an interest rate is one and not the other, a
customer's name is both, and the two steps will grow apart at the detector, at the prompt, at
whether a confirmation is asked and at what a class is allowed to be called. A shape shared because
it is identical today is a shape two features have to agree about tomorrow. The cost, stated once:
six field declarations and three model classes exist twice, and the check that keeps them honest is
that neither copy holds a rule — only nouns.

**What is *not* duplicated is the arithmetic, and that is the line.** Where a value stands in a
document, which nested span is dropped, how `<CLASS_N>` is numbered and how a span is replaced are
facts about strings, not judgements about values: they cannot diverge, so a second copy would only
ever be the wrong one (`T-6`). They move to `profile/tool_decision/value_spans.py`, imported by
`data_quality.py` and `data_scale.py` alike, owned by neither.

**One base shape, so the arithmetic has a field to read.** `modalities/text2text/value_spans.py`
declares `ValueSpan` — `id`, `path`, `start`, `end`, `value_class`, `placeholder`, `reason`.
`PersonalDataSpan` and `ScaleSpan` each extend it and each alias `value_class` to their own name on
the wire: `personal_data_class` and `scale_class`. The alias is what keeps the rename off what is
already written — measured, so the scope is known rather than feared: the key
`personal_data.spans[].personal_data_class` stands **102 times across the 40 documents in
`tool_decision_record`, and nowhere else**. The exported corpus does not carry it (a `StoredSample`
is the key, the input, the label and the facets — no spans), and `tool_decision_dataset` holds no
span at all. The same pattern the router already uses for `declared_facets` aliased to `class`.

### The claims

```python
def name_argument_class(tool: str, argument: str, qualifier: str = "") -> str:
    """`<TOOL>__<ARG>`, or `<TOOL>__<QUALIFIER>_<ARG>` where a mention is not the whole value.

    Each part upper-cased with runs of whitespace written as `_` -- the rule the page applies to a
    kind a reviewer types, so a class a detector proposes and a class a reviewer types are one
    spelling and not two.
    """

def read_argument_claims(sample: Mapping[str, Any]) -> Mapping[str, str]:
    """Which class claims each value the sample's calls pass, keyed by value.

    Every call in `messages` and every call in `label` as it ships, both spellings, through
    `read_named_function`. An empty value is left out -- it can carry no offset. A value already
    standing as a placeholder is **not**: re-filing `<NAME_1>` under the argument that passed it is
    what Requirement 9 is about. First claim wins, so a value two arguments pass keeps the first
    argument's class, and the reviewer re-files it where that is wrong.
    """
```

The model detector sends `config/prompts/profiles/tool_decision/argument_scale_detect.txt` — the
task's own file, beside `pii_llm_detect.txt` and on the same terms, `ConfigError` where it is
missing. Four slots: `{language}`, `{review_text}`, `{tools}` (through `convert_tools_to_text`, so
the model reads the catalog the reviewer reads and not a second rendering of it), and
`{arguments}`, one `tool | argument | value` per line the way `build_pii_llm_confirm_prompt` writes
its spans. It answers `ScaleLlmDetected` — a `{reason, text, label}` per mention, the reason
written before the value, which is the rule every model answer on this flow follows. `text` must be
copied out of the review text character for character or the claim is dropped, because that is the
string an offset is searched in.

The two are unioned the way the personal-data step unions its own, the rule scan's class winning an
overlap, and the result goes to the same `order_claims_by_class` and `find_and_number_spans` the
other step uses. No class is declared for this step, so every scale class orders after the declared
ones in first-claim order — which is already what happens to a kind a reviewer types today.

The confirmation sends `argument_scale_confirm.txt` — **the task's own file and not the modality's,
which is where it differs from the personal-data one.** `pii_llm_confirm.txt` lives under
`modalities/` because *whether a value is personal data* is a question about personal data and
nothing else; *whether this stretch is a mention of that argument* is a question about a tool call,
so it sits with the code that asks it. Three slots — `{language}`, `{review_text}` and `{spans}`,
one `id | CLASS | value` per line — and it answers one `{id, reason, confirmed}` per span it was
shown, read back through the same narrowing rule.

### The precondition, and the chain

`dataset_management/sample_building.py` gains two things, both small.

```python
def read_replaced_placeholders(scaled: ScaledValues | None) -> Mapping[str, str]:
    """Placeholder to the placeholder that replaced it, for every value scaling re-filed.

    A scale claim whose value reads as a placeholder is the second step overwriting the first:
    `<NAME_1>` claimed as `SVCGETCONTACTINFO__NAME` ships as `<SVCGETCONTACTINFO__NAME_1>`. Empty
    where nothing scaled, which is every record written before this step existed.
    """
```

`find_surviving_spans` then counts a span satisfied where its own placeholder stands **or** where
the one that replaced it does. Nothing else about the check moves: it still asks whether the value
the reviewer confirmed is out of what ships, and it still refuses the record where it is not.

### The generation

`config/prompts/profiles/tool_decision/conversation_generation.txt`, on the same terms as the other
four: the deployment's file, read from the working directory, `ConfigError` where it is missing or
empty. It is the one prompt in this repository a reviewer edits, and the box holds the template
rather than a filled one, so the sample can never be pasted into it by hand. Four slots — `{language}`, `{tools}` (through `convert_tools_to_text`), `{conversation}`
(through `list_conversation_turns`) and `{slots}` (one `<CLASS_N> — what it stands for` per line,
read off the step's own spans).

`ConversationGenerator` is built the way `ToolPredictor` and `PiiLlmDetector` are: `resolve_config`
at construction, `ConfigError` before any record where the name resolves to no endpoint, `complete`
to ask, one declared shape read back, and a failed call is one structured event on stdout and an
empty answer — never a raise (`H-6`).

### The order

Four landings, and each of the first three is usable on its own.

1. **The extraction, with nothing new on the screen and nothing new in the API.** The nine
   functions move to `profile/tool_decision/value_spans.py`; `ValueSpan` lands with
   `PersonalDataSpan` extending it under the alias; `ui/spans.js` takes the keep-table drawing and
   `held` grows a bucket per step so two cards can hold their own `claimed`, `keeps` and `stands`.
   **Every existing test passes unedited** — `tests/ui/page.js`, `tests/ui/reading.js`,
   `tests/profile/test_personal_data.py`, `tests/edge/test_endpoints.py`. That is the whole
   evidence that the personal-data step was made shareable without being changed, and there is no
   other way to get it. A commit that moves and edits in one proves neither.
2. **The rule half of the scan.** `data_scale/` lands with its shapes and its socket,
   `read_argument_claims` answers it, `POST /data-scale/values` runs the search alone, card 3
   appears, `scale` joins the record and the facet, and the precondition learns the chain. **This
   is the half that pays for itself**: the label's own values are three quarters of the slots, and
   at this point the six rows in § *Context* can be re-reviewed and the corpus's charts come apart
   correctly.
3. **The model half of the scan.** Two prompt files, the detector, the confirmation, the model
   picker on card 3's button. It goes third because a scan that answers without a model is a scan
   whose search half can be proved on its own — and because a table full of rule-scan rows is what
   makes a wrong model row visible. Within this landing the detector lands before the
   confirmation, for the same reason again: a confirmation is only readable against claims
   somebody has already looked at.
4. **The generation.** The second prompt file, the two routes, the box, the drafts, and Submit
   writing more than one record. This is where the page grows a list where it held one sample, and
   it is the only part of this spec that touches `app.js`'s `openSample` and `forgetEverything`.

## Decisions

1. **Scaling is its own module with its own functions, and shares only the arithmetic.** The
   reviewer's call, and the reason is the one that matters: personal data and scalable values are
   different sets of values answering different questions, so the two steps will change
   separately. An earlier draft of this spec had scaling import the personal-data shapes and call
   `detect_personal_data`'s composition; that would have made every later change to one of them a
   change to both, and the first such change is already visible — scaling wants a qualifier in a
   class name and personal data does not. Alternative: share everything and split when it hurts.
   Rejected because the splitting is what would then be expensive, and because a shared shape is a
   standing invitation to put a scale rule inside a personal-data function. The cost is stated in
   § *Design*: six field declarations and three model classes written twice, with no rule in
   either copy.
2. **`scale` is a note and stays one.** Settled by the reviewer, not deferred. A column is one
   SQLite will not add to an existing table, so it costs dropping `tool_decision_dataset` and
   rebuilding it from `tool_decision_record`, for which no command exists — and it buys two things
   nobody wants: a column on the rows table of the dataset sheet, and a place on an axis of the
   joint matrix. As a note it is counted by `count_by_note`, charted by the dataset sheet and
   readable on an opened row, for nothing. `direction` and `have_conversation_flow` have lived
   there since the store spec's own § *The page*, so this is the arrangement that already works
   rather than a concession.
3. **The scan asks a model, and is not a search alone.** An earlier draft of this spec said it
   asked none, on the grounds that the calls already say what the values are. That was wrong, and
   the corpus says so: `SEARCH_PLACE_27D__DISTRICT_LOCATION`, `WRONG_PHONE` and `WRONG_ID_NUMBER`
   are mentions that share no run of characters with the value the call passed, and a search
   cannot reach any of them. The rule scan is kept beside the model rather than replaced by it,
   because where a value *is* spelled out there is nothing for a model to be wrong about.
   Alternative: the model alone. Then the cheapest and most certain half of the answer is paid
   for, and a failed call loses the values the label was already holding in plain sight.
4. **The step runs after the label, not before.** Alternative: fold it into card 1, so one scan
   claims both. Then the label's own arguments — where a slot placeholder already stands 6 times
   across the corpus — are read before the reviewer has said what the label is, and the two kinds
   of claim land in one facet,
   which is the state § *Context* measures and this spec exists to end.
5. **The generated conversations are held on the page and written by one Submit.** Alternative: a
   generated conversation is pushed into the queue the moment it is accepted, and labelled later
   like any imported sample. That is far less state — nothing on the page, and a draft that
   survives a reload — but it defers the review to another sitting, and the request is explicit
   that the new conversations are reviewed alongside the one they came from and saved together.
   The cost is Requirement 32, stated on the screen. Reversible: the queue route already exists and
   takes one line.
6. **`POST /records` is unchanged and is called once per conversation.** Alternative: a route that
   takes several. The store's answer to *what is a record* is one conversation, the reviewed
   sample, under its own key; a route taking a list would need its own partial-failure shape, and
   every caller would have to read it. N posts give the page one outcome per conversation for
   nothing.
7. **The two shared routes are renamed now rather than aliased.** Alternative: leave
   `/data-quality/personal-data/spans` where it is and post the scale card's claims to it.
   Two steps posting to a URL that names one of them is a name that needs a footnote, and the only
   client is a page in this repository. Alternative rejected for the opposite reason: adding
   `/data-scale/spans` and `/data-scale/redact` beside the old pair is two URLs for one act, and
   `C-3` is about not leaving a rule for somebody to remember.
8. **The already-stored rows are re-reviewed by hand, not backfilled.** The reviewer's decision.
   A name-shaped rule would move 12 kinds and leave 8 — `CAR_PRICE`, `DOWN_PAYMENT`,
   `INTEREST_RATE`, `LOAN_TERM`, `WEIGHT`, `DELIVERY_OPTION` and the two `WRONG_` kinds are
   judgements about what a value *is*, not about how it is spelled. Six rows, and the record table
   keeps what arrived, so nothing is lost by taking them one at a time.

## Invariants

- A raw value is never reached by the scale step. Check: scaling runs over the record the
  personal-data redaction left, so a confirmed personal-data value is already a placeholder when
  scaling reads it. What scaling re-files is that placeholder, never what stood under it.
- Two distinct values never share a placeholder, through either step or across both. Check:
  `name_placeholders` keys by value, so `<NAME_1>` and `<NAME_2>` re-filed under one class come
  back as two placeholders and stay co-referent to two things.
- One rule numbers a placeholder, and both steps go through it. Check: `name_placeholders` is
  called from one place, `find_and_number_spans`, and both steps reach it through the one
  `value_spans` module that neither owns.
- A personal-data value the reviewer confirmed is out of what ships, whether or not scaling
  overwrote its placeholder. Check: `find_surviving_spans` counts the span's own placeholder or
  the one `read_replaced_placeholders` says replaced it, and a record with no `scale` reads
  exactly as it read before this step existed.
- The `scale` facet and the `scale` key on the record cannot disagree. Check: the facet is
  `read_redacted_classes` over the key's own spans, computed at write time, the way
  `personal_data` already is.
- A record whose `scale` says a value was replaced and whose shipped text still holds it does not
  become a row. Check: `find_surviving_spans` over the `scale` key, the same function and the same
  refusal as `personal_data`.
- `scale: null` stores; `personal_data: null` does not. Check: two paths through `build_sample`,
  pinned apart in the store's tests.
- Nothing under `ui/` decides what class a value is. Check: the scale card reads `scale_class` off
  a span the service answered, exactly as card 1 reads `personal_data_class`, and the guard
  forbidding a declared class name in `ui/` source sweeps every file under `ui/`, so it covers the
  new modules with nothing added.
- The wire and the stored documents keep the field names they have. Check: `PersonalDataSpan`
  serialises `value_class` as `personal_data_class` under its alias, and a record written before
  this step reads back unchanged.
- The generated conversation offers the source's catalog unchanged. Check: the route copies `tools`
  from the request and the prompt asks for turns only.
- No raw value reaches the generator. Check: the page posts `held…shipped.sample`, and the route's
  request model carries no path to the sample as it arrived.

## Error Behavior

- A generation call that fails answers a conversation with no turns and the model's own text under
  `said`, plus one structured event on stdout naming the model (`H-6`). The reviewer presses again;
  nothing else on the page moves.
- An answer that will not read as a list of turns is the same fact and the same answer. It is never
  partially read and never repaired.
- A generator model this deployment does not serve is a 422 raised by `check_served_models` before
  the call, like every other model-taking route.
- A missing or empty prompt file — `conversation_generation.txt`, `argument_scale_detect.txt` or
  `argument_scale_confirm.txt` — is a `ConfigError` and so a 422, on the same terms as the two
  prompts that came before them: a deployment with no prompt is not a provider having a bad day.
- **A failed model call in the scan leaves the rule scan's claims standing**, the same way a failed
  `pii_llm_detect` leaves the rule scans' values. One structured event on stdout naming the step
  (`H-6`), no raise, and a card 3 holding every slot the label spelled out — which is most of them.
  Nothing on the card says *refused*, because nothing was: the reviewer is looking at a shorter
  table and the button re-runs it.
- **A failed confirmation confirms nothing, and card 3 comes back empty rather than wrong.** This
  is the one place the two steps' failures differ in what they cost: a personal-data confirmation
  that fails leaves every claimed value standing in the copy, which is a record held back; a scale
  confirmation that fails leaves a reviewer with no slots, which is a button to press again. Both
  are one event on stdout and neither raises.
- A model answer naming a class that is not a class — empty, or holding a character a placeholder
  may not carry — is dropped, one claim at a time. A bad row is one claim, not a reason to lose
  the rest of the answer.
- A body `POST /data-scale/values` cannot read as a sample is a 422 at the boundary, drawn in the
  rectangle that sent it.
- A record refused by the store during a multi-conversation Submit stops that conversation and no
  other. The line beside it says the service's own words; the ones already written stay written;
  pressing Submit again rewrites every key rather than making second rows.
- A sample with no calls at all is an empty claim set, not an error. Card 3 says *nothing to vary*,
  which is a finished card — 30 of 40 rows in the corpus already have nothing left to find.

## Testing Strategy

- `read_argument_claims` over a hand-written sample: both call spellings read; a call in the label
  read as readily as one in a turn; an empty value left out; a value already standing as `<NAME_1>`
  **claimed, and claimed under the argument that passed it**; two arguments passing one value
  settled by first claim; a tool name lower-cased in the catalog claimed under its upper-cased
  class. Each assertion proved by mutating the source and confirming exactly the expected claims
  go red.
- The model half with `complete` stubbed: a mention sharing no characters with the value is
  claimed under the class the model proposed; an answer whose `text` is not in the review text is
  dropped; a class the rule scan also claimed keeps the rule scan's; a failed call leaves the rule
  scan's claims standing and writes one event. The prompt is pinned to carry the catalog, because
  a slot silently unfilled is a model told less with nothing saying so.
- The confirmation with `complete` stubbed, over the same four rules the personal-data one is
  pinned to: an id no span carries is discarded, a span answered twice keeps the first answer, a
  span nothing came back about is not confirmed, and an empty span list asks nothing at all.
- `name_argument_class` with and without a qualifier, pinned against the three the corpus already
  holds — `SEARCH_PLACE_27D__DISTRICT_LOCATION` is the one that proves the qualifier goes in front
  of the argument and not behind the tool.
- **The chain, over one record**: a name that is both personal data and an argument ships as
  `<SVCGETCONTACTINFO__NAME_1>`, the `personal_data` key still names its `<NAME_1>` span, and
  `build_sample` stores the row rather than refusing it. Proved red first, by writing the test
  against the precondition as it stands today.
- The full masking half over the sample § *Context* quotes: `SvcCalculateinterest`'s three
  arguments claimed, each one spanning the turn that said it, the call that passed it and the reply
  that repeated it, and the redacted copy reading as the corpus already stores it.
- The word-boundary case pinned: `time_period: 2` claims the standalone `2` and not the `2` inside
  `12`, and the claim is one row per place.
- The escaping limit pinned as a known one: a value holding a quote is claimed in the turn and not
  inside `arguments`, so the test says what the step does rather than leaving it to be found.
- The store's precondition: a record with `scale: null` stores; one whose `scale` names a span that
  did not take is refused with the same sentence `personal_data` is refused with; the `scale` facet
  comes back off an opened row and is counted by `count_by_facet`.
- Each route through `TestClient`, called with nothing but its own arguments — no fixture
  threads a detect answer from one route into another, which is pipeline Requirement 1.
- The generation route with `complete` stubbed: the catalog comes back as it went in; a model
  answer that is not turns comes back under `said` with no turns; a model name the directory does
  not hold is 422 and is proved to refuse *before* `complete` is reached.
- The page, in `tests/ui/page.js`: card 3 draws a row per place; its verdict follows its own table;
  the generation box opens holding what `GET /data-scale/prompt` answered; one press asks for one
  conversation; a draft appears in the list unfinished and is posted by Submit; two drafts are two
  posts; a refused draft leaves the others posted.
- The extraction commit changes no test. That is Requirement 29 and it is checked by the diff.

## What this rewrites

- `docs/labelling-ui/spec.md` Requirement 24 and the comment above `#call-form` in `index.html`:
  *the turns are what a customer said … a page that let a reviewer retype either is a page that can
  quietly make the sample agree with the label.* It stays true of a sample that arrived and gains
  the sentence that makes it false of one the page generated (Requirement 17).
- `docs/labelling-ui/spec.md` Requirement 26's opening, *the corpus is one button away*: the sheet's
  charts now separate `personal_data` from `scale`, and the paragraph naming `personal_data` as the
  facet nobody declares values for names both.
- `docs/tool-decision-pipeline/spec.md` Requirement 3: the record gains `scale`, and the sentence
  *the record is assembled by the page, once* becomes *once per conversation the reviewer is
  saving* — the record is still the flow's last answer and still exists in one place.
- `docs/tool-decision-store/spec.md` § *The page*: two route paths move, and the facet list grows a
  note.
- `docs/tool-decision-pipeline/spec.md` § *Context*, the paragraph naming three prompts: there are
  six, and the sentence that sorts them — *the shared one is shared because whether a detected
  value is personal data is a question about personal data and about nothing else* — now has a
  case on the other side of it. `argument_scale_detect.txt` and `argument_scale_confirm.txt` are
  both the task's, because *whether this stretch is a mention of that argument* is a question
  about a tool call; the confirmation is not the modality's the way the personal-data one is.
  `conversation_generation.txt` is the first prompt in this repository that is **edited by the
  person sending it** — every other one is a file only a deployment changes.
- `docs/tool-decision-pipeline/spec.md` Requirement 5, *detecting and replacing are two calls,
  because a human sits between them*: that is now true twice, of two steps, and the sentence names
  which.

The plans keep the history. None of the passages above is annotated in place — the spec states
current truth.

## Out of Scope

- **Filling the slots.** Turning one slotted row into a hundred rows with a hundred different
  amounts is a program reading the exported corpus, and it needs a table of candidate values per
  class that nothing here has. This step makes a corpus fillable and says nothing about who fills
  it.
- **Checking that a slot was filled sensibly.** `principal_amount` is a number and
  `<SVCCALCULATEINTEREST__PRINCIPAL_AMOUNT_1>` is not, so a filled corpus can carry a type error
  that this step cannot see. Whatever fills the slots owns that.
- **Naming a slot's type or its range.** The class says which argument a value came from, nothing
  more. The catalog already declares the type and the constraint beside that argument, so a second
  declaration would be the two rotting apart.
- **A generated conversation that offers a different catalog**, or one generated from nothing. Both
  are *making a sample*, and this step multiplies one that exists.
- **Duplicate detection over generated rows.** Two generations from one source may well be near
  copies, and `calculate_duplicates` compares canonical inputs, so it will not see it. Duplicates
  are `dataset_management`'s question and are deferred there already.

## Open

- **Whether `personal_data_class` should stop being an alias and become the field.** § *Design*
  keeps it as a wire and storage name over `ValueSpan.value_class`, so nothing already written
  moves. The alias is one line, and it is also one more thing a reader has to hold: the class says
  `value_class`, a response says `personal_data_class`, and knowing they are one thing is
  knowledge rather than code. Dropping it means rewriting that key in 102 spans across 40
  documents of `tool_decision_record`, which is a morning's work today and more every week. It is
  the only thing this spec leaves undecided.
