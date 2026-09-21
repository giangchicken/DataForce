// What the page does, run in node against `ui/app.js` itself.
//
// Each check is one sentence the spec makes about the screen. What is *not* here is what the page
// looks like: nothing in a stub can tell you a panel is cramped or a colour unreadable, and saying
// otherwise would be the worst kind of green.
const path = require("path");
const { build, settled, waited } = require("./dom");

const APP = process.argv[2] || path.join(__dirname, "..", "..", "src", "dataforce", "ui", "app.js");

let failed = 0;
// The exit code is set the moment something fails, not at the end. A check that throws half way
// never reaches the end, and a run that reported green because it died early is the one result
// worse than a red one.
function fails(said) {
  failed += 1;
  process.exitCode = 1;
  console.log(`FAIL  ${said}`);
}

function claims(said, held) {
  if (held) console.log(`  ok  ${said}`);
  else fails(said);
}

process.on("unhandledRejection", error =>
  fails(`a promise was left rejected: ${error && error.stack ? error.stack : error}`));

const PHONE = "0912345678";
const SAID = `xin chào ${PHONE}`;
// **The number the customer gave, carried into the call that was labelled.** A label is copied out
// of the conversation, so it holds what the conversation held -- and a fixture whose label carries
// nothing personal is a fixture that cannot tell whether the label is redacted at all.
const ONE = {
  id: "s1",
  messages: [{ role: "user", content: SAID }, { role: "assistant", content: "vâng ạ" }],
  tools: [{ type: "function", function: { name: "Lookup", description: "tra cứu khách hàng",
    parameters: { type: "object", properties: { ma: { type: "string" } } } } }],
  label: [{ name: "Lookup", arguments: { ma: PHONE } }]
};

// The one string the scan reads and every offset indexes: the turns, the catalog, then the label.
// Written out here the way the service writes it, because what the page shows is this and not a
// route's JSON about it.
const REVIEW_TEXT = [
  `user: ${SAID}`,
  "assistant: vâng ạ",
  "[Lookup]\ntra cứu khách hàng",
  `label: [{"name": "Lookup", "arguments": {"ma": "${PHONE}"}}]`
].join("\n");

const REDACTED_TEXT = REVIEW_TEXT.split(PHONE).join("<PHONE_1>");

const occurrencesOf = (text, value) => {
  const found = [];
  for (let at = text.indexOf(value); at >= 0; at = text.indexOf(value, at + value.length)) {
    found.push(at);
  }
  return found;
};

const PHONE_SPANS = occurrencesOf(REVIEW_TEXT, PHONE).map((at, n) => ({
  id: n + 1,
  start: at,
  end: at + PHONE.length,
  personal_data_class: "PHONE",
  placeholder: "<PHONE_1>",
  reason: null
}));

const WHY = "khách tự cho số của mình";
const CONFIRMED_SPANS = PHONE_SPANS.map(span => ({ ...span, reason: WHY }));

const NOTHING_NUMBERED = { review_text: REVIEW_TEXT, claims: [], spans: [] };

// What `/redact` answers: the record with every confirmed value replaced, and that same record
// rendered again. Both halves, because the record is what a corpus stores and the text is the
// only thing a person can read the redaction off.
const REDACTED = {
  outcome: "redacted",
  sample: {
    ...ONE,
    messages: [{ role: "user", content: "xin chào <PHONE_1>" }, { role: "assistant", content: "vâng ạ" }],
    label: [{ name: "Lookup", arguments: { ma: "<PHONE_1>" } }]
  },
  review_text: REDACTED_TEXT
};
const TWO = { id: "s2", messages: [{ role: "user", content: "cảm ơn" }], tools: [], label: [] };
// **A sample as a corpus really arrives**: `{messages, tools, label}` and no name. Nothing writes
// an `id` into a raw line, so every fixture carrying one is a fixture testing the easy half.
const UNNAMED = {
  messages: [{ role: "user", content: "anh muốn học quản trị kinh doanh" }],
  tools: [{ type: "function", function: { name: "VerifyEmail", description: "kiểm tra email" } }],
  label: ["VerifyEmail"]
};
const THREE = { id: "s3", messages: [{ role: "user", content: "hủy dịch vụ" }], tools: [], label: [] };

const STATISTICS = {
  sample_totals: { tool_decision_record: 3, tool_decision_dataset: 3 },
  counted_distribution_by_facet: { domain: { debt_collection: 3, insurance_claims: 1 } },
  counted_distribution_by_domain_and_call_trigger: { debt_collection: { condition_met: 3 } },
  label_summary: { total: 3, number_not_null_label: 2, number_diff_label: 2 },
  number_tools_offered: 1,
  tool_call_counts: { Lookup: 2 },
  duplicate_groups: { same_label: [["a", "b"]], diff_label: [] }
};

const ANSWERS = () => ({
  // What `GET /models` really answers: a bare array of names, not an object with a key.
  models: ["m1", "m2"],
  statistics: STATISTICS,
  queue: [ONE, TWO],
  detected: {
    review_text: REVIEW_TEXT,
    claims: [["PHONE", PHONE]],
    spans: CONFIRMED_SPANS
  },
  numbered: { review_text: REVIEW_TEXT, claims: [["PHONE", PHONE]], spans: PHONE_SPANS },
  reviewed: { llm: { label_agreement: 0.75 }, sft: null },
  redacted: REDACTED,
  imported: { read: 4, imported: 2, already_held: 1, unreadable: [3] }
});

// Two stored rows: one whose label validates, and one that names a tool without calling it —
// which is the shape a corpus really arrives in and the reason this list exists.
const STORED = {
  total: 2,
  samples: [
    { key: "d1", said: "mail anh là <EMAIL_1>", language: "vi", domain: "debt_collection",
      ambiguous: "LOW", call_trigger: ["condition_met"], personal_data: ["EMAIL"],
      number_turns: 2, number_label_tools: 1, number_provided_tools: 1, schema_valid: true,
      modified_time: "2026-09-19T00:00:00" },
    { key: "d2", said: "anh muốn kiểm tra email", language: "vi", domain: "telesale",
      ambiguous: "HIGH", call_trigger: ["user_utterance"], personal_data: [],
      number_turns: 1, number_label_tools: 0, number_provided_tools: 1, schema_valid: false,
      modified_time: "2026-09-18T00:00:00" }
  ]
};

const STORED_ONE = {
  key: "d2",
  input: { messages: [{ role: "user", content: "anh muốn kiểm tra email" }], tools: [] },
  label: ["VerifyEmail_15d"],
  facets: { schema_valid: false, domain: "telesale" },
  created_time: "2026-09-18T00:00:00",
  modified_time: "2026-09-18T00:00:00"
};

// What the rule answers about a label that names a tool and stops there. The sentence is the
// service's own, copied here verbatim, because what the page is checked for is passing it through
// -- a fixture worded like the page's own summary could not tell the two apart.
const BARE_NAME_FAULT = {
  schema_valid: false,
  faults: ['call 1 is the bare name Lookup -- a label says which tool fires *and with what*,'
    + ' so it has to read {"name": "Lookup", "arguments": {...}}']
};

// **The label the panel would have written**, carrying the number the customer gave -- which is
// what makes taking it a real test: the call that lands in the box holds a phone number, and it
// has to leave in the same placeholder the turn does.
const CONSENSUS = `[{"name": "Lookup", "arguments": {"ma": "${PHONE}", "kenh": "app"}}]`;

// What `/ai-review` answers beside `consensus`: the same sentence read as calls by
// `parse_text_to_tools` -- arguments as the JSON text under one key ordering, which is the format
// the store already treats as one spelling of a call.
const CONSENSUS_CALLS = [{
  type: "function",
  function: { name: "Lookup", arguments: `{"kenh":"app","ma":"${PHONE}"}` }
}];

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const esc = said => String(said)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const shown = markup => markup
  .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
  .replace(/&quot;/g, '"').replace(/&amp;/g, "&");

const paths = page => page.asked.map(one => one.path.split("?")[0]);

const settle = async (times = 8) => { for (let n = 0; n < times; n += 1) await settled(); };
const askPanel = async page => {
  await page.byId.get("run-review").onclick();
  await settle();
};

// A call that spends something: a model, or a row. Three routes under `/data-quality` spend
// neither, so they are the ones the page may ask for without a reviewer having asked for
// anything: `label` is the store's `schema_valid` rule over two fields already in the browser,
// `classes` is a list this deployment declares, and `spans` is two pure functions over a text.
const FREE = ["/data-quality/label", "/data-quality/personal-data/classes",
  "/data-quality/personal-data/spans"];
const machine = one =>
  one === "/ai-review" || (one.startsWith("/data-quality") && !FREE.includes(one));

// A click and a tick as the page receives them: an event whose target answers `closest`, which is
// how both handlers find the row that was acted on.
const hit = (el, named, dataset, said = {}) =>
  el({
    target: {
      closest: asked => (asked === named ? { dataset, checked: dataset.on, ...said } : null)
    }
  });
const clickRow = (page, key) => hit(page.el("list-rows").onclick, "[data-open]", { open: key });
const tickRow = (page, key, on) =>
  hit(page.el("list-rows").onchange, "[data-pick]", { pick: key, on });
const posted = (page, named) => page.asked.filter(one => one.path.split("?")[0] === named);

// A file chosen in the picker, as the page receives it: the input holds it and fires `change`.
// Through the element and not by calling the page's own function by name -- a module keeps its
// declarations to itself, and a browser reaches this the same way this does.
const chose = (page, file) => {
  const box = page.el("file");
  box.files = [file];
  return box.onchange({ target: box });
};

async function start(answers = ANSWERS()) {
  const page = await build(answers, APP);
  for (let n = 0; n < 8; n += 1) await settled();
  return page;
}

async function main() {
  // ------------------------------------------------------------------ what happens on load
  let page = await start();
  const onLoad = paths(page);
  claims("the models, the statistics and the queue are asked on load",
    ["/models", "/records/stats", "/queue/next"].every(one => onLoad.includes(one)));
  claims("**no machine step runs on load** — the vote costs a model call and a skipped sample must cost nothing",
    !onLoad.some(machine));
  claims("**the label is checked against its catalog the moment a sample opens** — the warning is about the question the panel is asking, so it cannot arrive after the answer",
    onLoad.includes("/data-quality/label"));

  // ------------------------------------------------------------------ the sample, as itself
  const turns = page.byId.get("turns").innerHTML;
  claims("the conversation is drawn as turns, with the role and what was said",
    turns.includes("user") && turns.includes(SAID) && turns.includes("vâng"));
  claims("the conversation is not drawn as JSON", !turns.includes('"role":'));
  claims("the catalog names the tool and what it is for",
    page.byId.get("catalog").innerHTML.includes("Lookup")
    && page.byId.get("catalog").innerHTML.includes("tra cứu"));
  claims("the label that arrived is drawn as a call",
    page.byId.get("arrived-call").innerHTML.includes("Lookup"));
  claims("the sample's name is on the pane", page.byId.get("sample-name").textContent.includes("s1"));

  // ------------------------------------------------------------------ which model answers what
  claims("**the model that answers a check is on that check's own row**, not further down the page",
    page.el("verifier-ticks").innerHTML.includes("m1")
    && page.el("jury-ticks").innerHTML.includes("m1")
    && page.el("sft-ticks").innerHTML.includes("m1"));
  claims("**the route's own answer is read** — a bare array of names, not a `models` key",
    !page.el("verifier-ticks").innerHTML.includes("no model is configured"));
  claims("a verifier is picked for the reviewer, so a run does not stop on a tick nobody made",
    page.inputsNamed("verifier").some(box => box.checked));
  page = await start({ ...ANSWERS(), models: [] });
  claims("a deployment serving nothing says so where the tick would be",
    page.el("verifier-ticks").innerHTML.includes("no model is configured"));

  // A model file added to the directory while somebody is labelling. The page asks again when the
  // window comes back, because that directory is edited while the service is up.
  page = await start();
  const wake = page.woken.find(one => one.kind === "focus").handler;
  page.inputsNamed("jury").find(box => box.value === "m2").checked = true;
  page.inputsNamed("jury").find(box => box.value === "m1").checked = false;
  page.el("jury-ticks").onchange();
  const drawnOnce = page.el("verifier-ticks").innerHTML;
  await wake();
  for (let n = 0; n < 6; n += 1) await settled();
  claims("coming back to the tab asks which models are served",
    posted(page, "/models").length === 2);
  claims("**and the jury the reviewer picked survives coming back**, rather than being reset",
    page.el("verifier-ticks").innerHTML === drawnOnce
    && page.inputsNamed("jury").filter(box => box.checked).map(box => box.value).join() === "m2");
  page.answers.models = ["m1", "m2", "m3"];
  await wake();
  for (let n = 0; n < 6; n += 1) await settled();
  claims("**a model added to the directory appears without a reload**",
    page.el("verifier-ticks").innerHTML.includes("m3"));
  claims("and the jury the reviewer had picked survives the list growing",
    page.inputsNamed("jury").filter(box => box.checked).map(box => box.value).join() === "m2");
  page.answers.models = ["m3"];
  await wake();
  for (let n = 0; n < 6; n += 1) await settled();
  claims("a model that stopped being served falls back rather than staying ticked",
    page.inputsNamed("jury").filter(box => box.checked).map(box => box.value).join() === "m3");

  // A model directory that went away and came back — moved aside, or a mount that dropped. What
  // is drawn on the screen is then a sentence and not a list, so *the same list as last time* has
  // to stop being a reason to leave it alone: it would be left saying there is no model to tick
  // over a deployment that serves one.
  page = await start({ ...ANSWERS(), models: ["m1"] });
  const wakeAgain = page.woken.find(one => one.kind === "focus").handler;
  page.answers.models = [];
  await wakeAgain();
  for (let n = 0; n < 6; n += 1) await settled();
  claims("a directory that emptied says so where the ticks were",
    page.el("verifier-ticks").innerHTML.includes("no model is configured"));
  page.answers.models = ["m1"];
  await wakeAgain();
  for (let n = 0; n < 6; n += 1) await settled();
  claims("**and the same list coming back is drawn again**, not skipped as unchanged",
    page.el("verifier-ticks").innerHTML.includes("m1")
    && !page.el("verifier-ticks").innerHTML.includes("no model is configured"));

  // ----------------------------------------- two acts, and a human decision in between them
  page = await start();
  const before = page.byId.get("turns").innerHTML;
  claims("**the panel cannot be asked before the spans have been approved**, and the button says so",
    page.byId.get("run-review").disabled
    && page.el("run-note").textContent.includes("find the personal data first"));
  await page.byId.get("run-detect").onclick();
  await settle();
  const scanned = paths(page);
  claims("**finding the personal data spends no vote** — the scan and the copy, and nothing else",
    JSON.stringify(scanned.filter(machine))
    === JSON.stringify(["/data-quality/personal-data", "/data-quality/personal-data/redact"]));
  claims("**and only then can the reviewers be asked**, with nothing left in the way",
    !page.byId.get("run-review").disabled && page.el("run-note").textContent.includes("replaced"));
  await askPanel(page);
  const ran = paths(page);
  claims("asking the reviewers is what spends the vote",
    JSON.stringify(ran.filter(machine))
    === JSON.stringify(["/data-quality/personal-data", "/data-quality/personal-data/redact",
      "/ai-review"]));
  claims("**the panel is handed the redacted record**, so a juror reads the placeholder rather than"
    + " the number and writes what it read",
    JSON.parse(posted(page, "/ai-review").at(-1).body).messages[0].content.includes("<PHONE_1>")
    && !JSON.stringify(JSON.parse(posted(page, "/ai-review").at(-1).body)).includes(PHONE));
  claims("**the duplicate and abnormal scans are off the screen** and nothing asks for them",
    !ran.includes("/data-quality/duplicate") && !ran.includes("/data-quality/abnormal"));
  claims("**the sample never leaves the screen** — running the checks does not rewrite the left pane",
    page.byId.get("turns").innerHTML === before);
  claims("the scan's answer is one cell, not a payload",
    page.el("said-2").textContent.includes("1 value found"));
  claims("**the replacement reports on the scan's own row**, because it is not a step to run",
    page.el("said-2").textContent.includes("1 value replaced"));
  claims("**the reviewers' verdict is a number on the check's row and a state word on the card**",
    page.el("said-6").textContent.includes("75%")
    && page.byId.get("label-verdict").textContent === "reviewed");
  claims("**and the number is said once, beside the label it is about** — it counts the jurors"
    + " whose own answer matches the one that *arrived*, so it belongs nowhere else",
    page.el("arrived-note").textContent.includes("75%")
    && !page.el("proposed-note").textContent.includes("75%"));
  claims("**both checks' cells are painted by one hand** — both say `verdict`",
    page.el("said-2").className.split(" ")[0] === "verdict"
    && page.el("said-6").className.split(" ")[0] === "verdict");
  claims("**the text is shown as a text** — the sample as one string, not a route's JSON about it",
    page.el("review-text").textContent === REDACTED_TEXT);
  claims("**and its line breaks are line breaks**, not `\\n` printed into a payload",
    page.el("review-text").textContent.split("\n").length === 5
    && !page.el("review-text").textContent.includes("\\n"));
  claims("**nothing on the panel prints what the scan keyed or how it decided**",
    !page.el("review-text").textContent.includes('"spans"')
    && !page.el("review-text").textContent.includes('"outcome"'));
  claims("**the text on screen is the one the reviewers will be handed**, said so before the"
    + " button that hands it over",
    page.el("text-which").textContent.includes("reviewers will be handed"));
  claims("a scan that found something opens its own working unasked",
    page.byId.get("scan-raw").open === true);
  claims("the data panel says how many values there are to confirm",
    page.byId.get("data-verdict").textContent.includes("1"));
  const kept = () => page.el("keep-table").markup();
  claims("**a row is a value, and how many times it occurs is answered beside it**",
    kept().includes(PHONE) && kept().includes(`×${PHONE_SPANS.length}`));
  claims("**and no offset is on the screen**: the row carries the value, not two numbers",
    !kept().includes(`value="${PHONE_SPANS[0].start}"`));
  claims("the spans it made are shown read-only, each with what it stands in for",
    shown(page.el("scan-raw").markup()).includes("<PHONE_1>"));

  // ------------------------------------------------------------------ a step that fails
  page = await start({ ...ANSWERS(), refuse: { "/data-quality/personal-data": { status: 500, detail: "the service fell over" } } });
  await page.byId.get("run-detect").onclick();
  await settle();
  claims("**a scan that fails leaves the panel unaskable**, rather than spending a vote on a"
    + " record nothing redacted",
    page.byId.get("run-review").disabled
    && !paths(page).includes("/data-quality/personal-data/redact")
    && !paths(page).includes("/ai-review"));
  claims("the refusal is the service's own sentence, not a paraphrase, on the row that was refused",
    page.el("said-2").textContent.includes("the service fell over")
    && page.el("said-6").textContent === "not run");

  // A refusal from the *replacement* lands on the scan's row too, and must not write over the
  // scan's payload — which is the thing a reviewer opens to check a verdict they doubt.
  page = await start({ ...ANSWERS(), refuse: { "/data-quality/personal-data/redact": { status: 500, detail: "the copier fell over" } } });
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  claims("a replacement that fails says so on the scan's row",
    page.el("said-2").textContent.includes("the copier fell over"));
  claims("**and the text says why rather than showing a copy nothing made**",
    page.el("review-text").textContent.includes("the copier fell over"));
  claims("**and the vote cannot be spent on a sample whose copy could not be made**, with the"
    + " service's own sentence on the button that would spend it",
    page.byId.get("run-review").disabled
    && page.el("run-note").textContent.includes("the copier fell over"));
  await askPanel(page);
  claims("and pressing it anyway asks nothing", !paths(page).includes("/ai-review"));

  // ----------------------------------------- the panel goes back out of reach, and says so
  //
  // Every other claim about this button sits on a path where it was **never enabled** — before a
  // scan, after a refused scan, after a refused copy — so the `disabled` in the markup satisfies
  // them and a page that never takes the button back would pass all of them. This is the
  // transition, on the one path where `copyLater` is the only thing that invalidates the copy.
  page = await start();
  await page.byId.get("run-detect").onclick();
  await settle();
  await waited(320);
  await settle(6);
  claims("the panel is in reach once there is a copy to hand it", !page.byId.get("run-review").disabled);
  page.el("v-keep").checked = true;
  await page.el("v-keep").onchange();
  claims("**settling the label takes it back out of reach at once** — the label is in that text,"
    + " so the copy the panel would have been handed is the one being remade",
    page.byId.get("run-review").disabled
    && page.el("run-note").textContent.includes("replacing"));
  await page.byId.get("run-review").onclick();
  await settle(4);
  claims("and nothing is asked in that window", !paths(page).includes("/ai-review"));
  await waited(400);
  await settle(10);
  claims("**and it comes back once the copy has**", !page.byId.get("run-review").disabled);

  // While the vote itself is in flight the button is dead, and a note still reading *they read
  // the text above* is a page saying it is ready to do the thing it is already doing.
  page = await start({ ...ANSWERS(), slow: { "/ai-review": [500] } });
  await page.byId.get("run-detect").onclick();
  await settle();
  await waited(320);
  await settle(6);
  const asking = page.byId.get("run-review").onclick();
  await settle(4);
  claims("**a button that is dead says why, whatever made it dead** — including its own answer"
    + " being in flight, which is the longest wait on the page",
    page.byId.get("run-review").disabled
    && !page.el("run-note").textContent.includes("they read the text above"));
  await asking;
  await settle(8);
  claims("and it is live again once that answer lands",
    !page.byId.get("run-review").disabled && page.el("said-6").textContent.includes("75%"));

  // --------------------------------- the window between a value being typed and the copy remade
  //
  // Every edit to the table takes a round trip to be numbered, and for its whole length the copy
  // on screen is the one made *before* the edit. The tick path took the copy down before asking;
  // the add and reclass paths took it down after the answer came back, which left **Ask the
  // reviewers** live over a record that does not hold what the reviewer has just said is personal
  // data. A value typed in and handed straight to a model in the clear is the exact thing this
  // card exists to prevent.
  const MISSED_EARLY = "vâng ạ";
  const NUMBERED_LATE = {
    review_text: REVIEW_TEXT,
    claims: [["PHONE", PHONE], ["NAME", MISSED_EARLY]],
    spans: [...PHONE_SPANS, {
      id: PHONE_SPANS.length + 1,
      start: REVIEW_TEXT.indexOf(MISSED_EARLY),
      end: REVIEW_TEXT.indexOf(MISSED_EARLY) + MISSED_EARLY.length,
      personal_data_class: "NAME",
      placeholder: "<NAME_1>",
      reason: null
    }]
  };
  page = await start({ ...ANSWERS(), numbered: [ANSWERS().numbered, NUMBERED_LATE],
    // The second copy has the added value replaced too. A stub that answered the first copy twice
    // would be a service that ignored what the reviewer just typed, and the gate below is exactly
    // the thing that would catch it -- so the fixture has to be the honest one.
    redacted: [REDACTED, { ...REDACTED,
      review_text: REDACTED_TEXT.split(MISSED_EARLY).join("<NAME_1>") }],
    slow: { "/data-quality/personal-data/spans": [0, 500] } });
  await page.byId.get("run-detect").onclick();
  await settle();
  page.el("value-new").value = MISSED_EARLY;
  page.el("value-class").value = "NAME";
  const adding = page.el("value-add").onclick();
  await settle(4);
  claims("**a value being numbered takes the panel out of reach**, because the copy on screen is"
    + " the one made before the reviewer said it was personal data",
    page.byId.get("run-review").disabled
    && page.el("run-note").textContent.includes("numbering"));
  await page.byId.get("run-review").onclick();
  await settle(4);
  claims("and pressing it in that window hands nothing to a model",
    !paths(page).includes("/ai-review"));
  await adding;
  await waited(600);
  await settle(10);
  claims("**once the copy has caught up the panel is in reach again**",
    !page.byId.get("run-review").disabled
    && page.el("run-note").textContent.includes("replaced"));

  page = await start({ ...ANSWERS(), numbered: [ANSWERS().numbered, ANSWERS().numbered],
    slow: { "/data-quality/personal-data/spans": [0, 500] } });
  await page.byId.get("run-detect").onclick();
  await settle();
  const reclassing = hit(page.el("keep-table").onchange, "[data-class]", { class: PHONE }, { value: "OTP" });
  await settle(4);
  claims("**and so does saying a value is a different kind** — the placeholder in the copy is the"
    + " one the old class counted, so it is not what the reviewers would be reading",
    page.byId.get("run-review").disabled);
  await reclassing;
  await waited(600);
  await settle(10);

  // ------------------------------- a copy the service could not finish making
  //
  // `/redact` replaces **by value over the record's own fields**, and a claimed value that is not
  // a contiguous substring of any of them -- one that stands in the rendered text only because of
  // how the turns are joined -- can never be placed. The route answers 200 and says `withheld`,
  // and the copy still holds the value. Read off the copy rather than off `outcome`, because
  // `outcome` is `withheld` on the ordinary path too: an unticked value is a claim left in the
  // text on purpose, and gating on the word would stop the flow every time somebody unticks one.
  page = await start({ ...ANSWERS(),
    redacted: { sample: ONE, review_text: REVIEW_TEXT, outcome: "withheld" } });
  await page.byId.get("run-detect").onclick();
  await settle();
  await waited(320);
  await settle(6);
  claims("**a copy that still holds a value the reviewer kept is not a text a model may read**",
    page.byId.get("run-review").disabled
    && page.el("run-note").textContent.includes("still holds"));
  claims("and the scan's row says so rather than counting it replaced",
    page.el("said-2").textContent.includes("still holds")
    && !page.el("said-2").textContent.includes("1 value replaced"));
  await page.byId.get("run-review").onclick();
  await settle(6);
  claims("**and no vote is spent on it**", !paths(page).includes("/ai-review"));

  // ------------------------------------------------- the copy follows the ticking, with no button
  page = await start({ ...ANSWERS(), numbered: [ANSWERS().numbered, NOTHING_NUMBERED] });
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  const copies = () => posted(page, "/data-quality/personal-data/redact").length;
  const numbering = () => posted(page, "/data-quality/personal-data/spans");
  const first = copies();
  hit(page.el("keep-table").onchange, "[data-keep]", { keep: PHONE, on: false });
  claims("unticking a value says at once that the copy is being made again",
    page.el("said-2").textContent.includes("replacing…"));
  await waited(320);
  for (let n = 0; n < 6; n += 1) await settled();
  claims("**the copy is made again when a value is unticked** — nothing is asked for",
    copies() === first + 1);
  claims("**and every occurrence of it is out of what was sent**, not just the first",
    JSON.parse(posted(page, "/data-quality/personal-data/redact").at(-1).body).detected.spans.length === 0);
  claims("**a value unticked is left out of what is numbered** — so a value the reviewer keeps that"
    + " sat inside it is free to earn a span of its own",
    numbering().length === 2
    && JSON.parse(numbering().at(-1).body).claimed.every(([, said]) => said !== PHONE));
  claims("**but it is still a claim the record is measured against**, because a rewrite asked for"
    + " and not done is not a clean record",
    same(JSON.parse(posted(page, "/data-quality/personal-data/redact").at(-1).body)
      .detected.claims, [["PHONE", PHONE]]));
  claims("the row then says nothing was left to replace",
    page.el("said-2").textContent.includes("nothing to replace"));
  claims("and the row says the value was left in the text, rather than counting nothing",
    page.el("keep-table").markup().includes("left in the text"));

  const MISSED = "vâng ạ";
  const WITH_MISSED = {
    review_text: REVIEW_TEXT,
    claims: [["PHONE", PHONE], ["NAME", MISSED]],
    spans: [...PHONE_SPANS, {
      id: PHONE_SPANS.length + 1,
      start: REVIEW_TEXT.indexOf(MISSED),
      end: REVIEW_TEXT.indexOf(MISSED) + MISSED.length,
      personal_data_class: "NAME",
      placeholder: "<NAME_1>",
      reason: null
    }]
  };
  const RECLASSED = {
    ...WITH_MISSED,
    claims: [["OTP", PHONE], ["NAME", MISSED]],
    spans: WITH_MISSED.spans.map(span => (span.personal_data_class === "PHONE"
      ? { ...span, personal_data_class: "OTP", placeholder: "<OTP_1>" } : span))
  };
  page = await start({ ...ANSWERS(),
    numbered: [ANSWERS().numbered, WITH_MISSED, RECLASSED, { ...RECLASSED,
      spans: RECLASSED.spans.filter(span => span.personal_data_class !== "OTP") }] });
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  const made = copies();
  const numberings = () => posted(page, "/data-quality/personal-data/spans");
  claims("the class picker offers what the service says a value may be, not a list the page holds",
    page.el("value-class").innerHTML.includes("EMAIL")
    && page.el("value-class").innerHTML.includes("NAME"));
  page.el("value-new").value = MISSED;
  page.el("value-class").value = "NAME";
  await page.el("value-add").onclick();
  for (let n = 0; n < 6; n += 1) await settled();
  const sentValues = JSON.parse(numberings().at(-1).body).claimed;
  claims("**a value the scan missed is sent as a value and a class**, and no offset with it",
    same(sentValues.at(-1), ["NAME", MISSED]) && !JSON.stringify(sentValues).includes("start"));
  claims("**and the value the scan claimed goes with it**, so nothing already numbered is renumbered",
    same(sentValues[0], ["PHONE", PHONE]));
  claims("**the values go as an ordered list**, because where two start at one offset the order is"
    + " what settles which is numbered first",
    same(sentValues, [["PHONE", PHONE], ["NAME", MISSED]]));
  claims("what comes back is what is drawn: the occurrences are the service's answer",
    kept().includes(MISSED) && shown(page.el("scan-raw").markup()).includes("<NAME_1>"));
  await waited(320);
  for (let n = 0; n < 6; n += 1) await settled();
  claims("**a value added remakes the copy too**, over the spans that value earned",
    copies() === made + 1
    && JSON.parse(posted(page, "/data-quality/personal-data/redact").at(-1).body)
      .detected.spans.length === WITH_MISSED.spans.length);

  const noKinds = await start({ ...ANSWERS(), classes: [] });
  await noKinds.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  noKinds.el("value-new").value = MISSED;
  await noKinds.el("value-add").onclick();
  for (let n = 0; n < 4; n += 1) await settled();
  claims("**a deployment that says nothing about the kinds says so where a value is added**",
    noKinds.el("value-note").textContent.includes("no kind")
    && !posted(noKinds, "/data-quality/personal-data/spans").some(one =>
      JSON.parse(one.body).claimed.some(([, value]) => value === MISSED)));
  claims("**and it asks again rather than staying empty for the rest of the shift** — a page opened"
    + " while the service was restarting is not a page that can never add a value",
    posted(noKinds, "/data-quality/personal-data/classes").length === 2);

  const before6 = numberings().length;
  hit(page.el("keep-table").onchange, "[data-class]", { class: PHONE }, { value: "OTP" });
  for (let n = 0; n < 6; n += 1) await settled();
  claims("**saying a value is a different kind asks for it to be numbered again**",
    numberings().length === before6 + 1
    && JSON.parse(numberings().at(-1).body).claimed.some(pair => same(pair, ["OTP", PHONE])));
  claims("**and what stands in the text for it is drawn as it came back**, because `<CLASS_N>`"
    + " counts per class and the page counts nothing",
    shown(page.el("scan-raw").markup()).includes("<OTP_1>")
    && !shown(page.el("scan-raw").markup()).includes("<PHONE_1>"));

  const before7 = numberings().length;
  hit(page.el("keep-table").onchange, "[data-keep]", { keep: PHONE, on: false });
  await waited(320);
  for (let n = 0; n < 8; n += 1) await settled();
  claims("**unticking one value asks for the rest to be numbered again**, because what is dropped"
    + " for being inside a longer span is measured over what is still ticked",
    numberings().length === before7 + 1
    && JSON.parse(numberings().at(-1).body).claimed.every(([, value]) => value !== PHONE));
  claims("and neither occurrence of it is handed back to be replaced",
    JSON.parse(posted(page, "/data-quality/personal-data/redact").at(-1).body)
      .detected.spans.length === WITH_MISSED.spans.length - PHONE_SPANS.length);

  const twoNumbered = [
    ANSWERS().numbered,
    { review_text: REVIEW_TEXT, claims: [["NAME", "the numbering of an edit already undone"]],
      spans: [] },
    { review_text: REVIEW_TEXT, claims: [["PHONE", PHONE]], spans: PHONE_SPANS }
  ];
  page = await start({ ...ANSWERS(), numbered: twoNumbered,
    slow: { "/data-quality/personal-data/spans": [0, 400, 0] } });
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  hit(page.el("keep-table").onchange, "[data-keep]", { keep: PHONE, on: false });
  await waited(60);
  hit(page.el("keep-table").onchange, "[data-keep]", { keep: PHONE, on: true });
  await waited(700);
  for (let n = 0; n < 10; n += 1) await settled();
  claims("**a numbering that lands after a newer one is dropped**, not read as the answer to what"
    + " is on the screen",
    page.el("keep-table").markup().includes(`×${PHONE_SPANS.length}`)
    && shown(page.el("scan-raw").markup()).includes("<PHONE_1>"));

  page = await start({ ...ANSWERS(),
    refuse: { "/data-quality/personal-data/spans": { status: 503, detail: "service restarting" } } });
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  await waited(320);
  for (let n = 0; n < 6; n += 1) await settled();
  const madeBefore = copies();
  page.el("value-new").value = MISSED;
  await page.el("value-add").onclick();
  await waited(400);
  for (let n = 0; n < 8; n += 1) await settled();
  claims("**a value the service could not number does not go on the table**",
    !page.el("keep-table").markup().includes(MISSED));
  claims("and what was typed is still in the box, so it is not retyped from memory",
    page.el("value-new").value === MISSED);
  claims("it says why, where the value was typed",
    page.el("value-note").textContent.includes("could not be numbered"));
  claims("**and no copy that ships is made from a claim the page could not place**",
    copies() === madeBefore);

  page = await start({ ...ANSWERS(), slow: { "/data-quality/personal-data/spans": [0, 400] } });
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  hit(page.el("keep-table").onchange, "[data-class]", { class: PHONE }, { value: "OTP" });
  await page.byId.get("skip").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  await waited(700);
  for (let n = 0; n < 10; n += 1) await settled();
  claims("**a numbering that lands after the sample changed is dropped**, not painted onto the next",
    page.byId.get("sample-name").textContent.includes("s2")
    && !page.el("keep-table").markup().includes(PHONE)
    && !page.el("scan-raw").markup().includes(PHONE));
  page.inputsNamed("f-domain")[0].checked = true;
  await page.byId.get("submit").onclick();
  for (let n = 0; n < 12; n += 1) await settled();
  claims("**and the record posted for the next sample carries no scan of the one before it**",
    JSON.parse(posted(page, "/records").at(-1).body).personal_data === null);

  page = await start();
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  await waited(320);
  for (let n = 0; n < 6; n += 1) await settled();
  claims("**why the confirmation said a value is personal data reaches the record**",
    JSON.parse(posted(page, "/data-quality/personal-data/redact").at(-1).body)
      .detected.spans.every(span => span.reason === WHY));

  const INSIDE = "Lookup";
  const nested = {
    review_text: REVIEW_TEXT,
    claims: [["PHONE", PHONE], ["NAME", INSIDE]],
    spans: [...CONFIRMED_SPANS, {
      id: CONFIRMED_SPANS.length + 1,
      start: REVIEW_TEXT.indexOf(INSIDE),
      end: REVIEW_TEXT.indexOf(INSIDE) + INSIDE.length,
      personal_data_class: "NAME",
      placeholder: "<NAME_1>",
      reason: WHY
    }]
  };
  page = await start({ ...ANSWERS(),
    detected: nested, numbered: { ...nested, spans: PHONE_SPANS } });
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  claims("**a value the service placed but numbered nothing for is not called missing**",
    page.el("keep-table").markup().includes("inside something longer")
    && !page.el("keep-table").markup().includes("not in the text"));

  const stray = page.el("keep-table").onchange;
  const rowsDrawn = page.el("keep-table").markup();
  hit(stray, "[data-class]", { class: "a value no row carries" }, { value: "OTP" });
  for (let n = 0; n < 4; n += 1) await settled();
  claims("**a row the page does not hold changes nothing** — an attribute that did not survive"
    + " being read back would otherwise put a second row on the table",
    page.el("keep-table").markup() === rowsDrawn
    && !page.el("keep-table").markup().includes("a value no row carries"));

  const AWKWARD = '<b>Trần "Minh" & Co</b>';
  const AWKWARD_TEXT = `user: ${AWKWARD}`;
  page = await start({ ...ANSWERS(),
    detected: {
      review_text: AWKWARD_TEXT,
      claims: [["NAME", AWKWARD]],
      spans: [{ id: 1, start: AWKWARD_TEXT.indexOf(AWKWARD), end: AWKWARD_TEXT.length,
                personal_data_class: "NAME", placeholder: "<NAME_1>", reason: null }]
    } });
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  claims("**a row keys itself by the value, escaped into the attribute a browser reads back**",
    page.el("keep-table").markup().includes(`data-keep="${esc(AWKWARD)}"`)
    && shown(page.el("keep-table").markup()).includes(`data-keep="${AWKWARD}"`));
  claims("and the value on it is the corpus\'s own text, not markup the page let through",
    page.el("keep-table").markup().includes("&lt;b&gt;"));

  // Two edits close together, the first copy slow. It lands last and is about spans that are no
  // longer on the screen, so the page must not paint it -- a reviewer who untickes a span and
  // then reticks it would otherwise be shown the copy without it and store that.
  page = await start({ ...ANSWERS(),
    replaced: [
      { redacted_text: "the run's copy", outcome: "redacted" },
      { redacted_text: "the copy of an edit already undone", outcome: "reported" },
      { redacted_text: "the copy of what is on the screen", outcome: "redacted" }
    ],
    slow: { "/data-quality/personal-data/redact": [0, 400, 0] } });
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  hit(page.el("keep-table").onchange, "[data-keep]", { keep: PHONE, on: false });
  await waited(240);
  hit(page.el("keep-table").onchange, "[data-keep]", { keep: PHONE, on: true });
  await waited(600);
  for (let n = 0; n < 8; n += 1) await settled();
  claims("**a copy that lands after a newer one is dropped**, not read as the answer to what is on the screen",
    page.el("said-2").textContent.includes("1 value replaced"));
  claims("and the row is not left saying it is still replacing",
    !page.el("said-2").textContent.includes("replacing…"));

  // ------------------------------- the copy that ships, and the moment a reviewer may see it
  //
  // **The label is rendered into this text**, so the number in the turn and the number in the
  // call have to carry the *same* placeholder. That co-reference is the whole reason the label
  // goes through the scan: a label redacted on its own would say `<PHONE_1>` about nobody. What
  // the reviewer is shown is the replaced copy from the moment there is one -- the vote below it
  // is spent on that text, and a text nobody was shown is a vote nobody can check.
  page = await start();
  await page.byId.get("run-detect").onclick();
  await settle();
  // Past the debounce, not straight after the run: asserted on the next tick, *nothing has been
  // shown yet* would be true of a page whose timer simply had not fired.
  await waited(320);
  await settle(6);
  claims("**the copy is made as the reviewer ticks** — the scan's own row reports on it",
    posted(page, "/data-quality/personal-data/redact").length === 1);
  claims("**and it is on the screen before anything is confirmed**, which is the text the vote"
    + " below it will be spent on",
    page.el("review-text").textContent === REDACTED_TEXT
    && page.el("text-which").textContent.includes("reviewers will be handed"));
  claims("**the unreplaced text is never drawn into that block**, at any point in the flow",
    !page.el("review-text").textContent.includes(PHONE));
  claims("and neither verdict is ticked for the reviewer",
    !page.el("v-keep").checked && !page.el("v-write").checked);
  page.el("v-keep").checked = true;
  await page.el("v-keep").onchange();
  claims("saying the label is right says at once that the copy is being made again",
    page.el("review-text").textContent.includes("replacing…"));
  await waited(400);
  await settle(10);
  claims("**and confirming it is what makes the block say the text ships**",
    page.el("review-text").textContent === REDACTED_TEXT
    && page.el("text-which").textContent.includes("ships"));
  const halves = page.el("review-text").textContent.split("label: ");
  claims("**the label is redacted with the turns**, which is what it being in the text buys",
    !halves[1].includes(PHONE) && halves[1].includes("<PHONE_1>"));
  claims("**and in the placeholder the turn carries**, so the two still read as one person's number",
    halves[0].includes("<PHONE_1>"));
  claims("the copy is made from every occurrence of the values the reviewer kept",
    JSON.parse(posted(page, "/data-quality/personal-data/redact").at(-1).body)
      .detected.spans.length === PHONE_SPANS.length);
  claims("**why the scan's confirmation said a value is personal data goes back with it**",
    JSON.parse(posted(page, "/data-quality/personal-data/redact").at(-1).body)
      .detected.spans.every(span => span.reason === WHY));
  claims("**the language the scan is asked in is the one the markup selects**, nobody having picked",
    JSON.parse(posted(page, "/data-quality/personal-data").at(-1).body).language === "vi");

  // The box says *the record this page will post*. It held nothing until the post had been made,
  // and the next sample opening then wiped it — so the one thing it promised to show was the one
  // thing it never showed.
  claims("**the record the page will post is on the screen before it is posted**",
    page.byId.get("record").textContent.includes("new_label")
    && posted(page, "/records").length === 0);
  const level = page.inputsNamed("f-ambiguous")[0];
  level.checked = true;
  page.el("facet-ticks").onchange();
  claims("and a facet ticked reaches it too, which nothing else on the page does",
    JSON.parse(page.byId.get("record").textContent).class.ambiguous === level.value);

  // The other half of the same rule: what gets redacted is the label the reviewer wrote.
  page = await start();
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  page.el("v-write").checked = true;
  await page.el("v-write").onchange();
  await waited(400);
  for (let n = 0; n < 10; n += 1) await settled();
  page.el("label-text").value = '[{"name": "Lookup", "arguments": {"ma": "KH-9"}}]';
  await page.el("label-text").oninput();
  claims("typing in the label takes the shipping copy down with it",
    page.el("review-text").textContent.includes("replacing…"));
  await waited(400);
  for (let n = 0; n < 10; n += 1) await settled();
  claims("**the copy is made from the label the reviewer wrote**, not the one that arrived",
    JSON.parse(posted(page, "/data-quality/personal-data/redact").at(-1).body).label[0].arguments.ma === "KH-9");

  // -------------------------------------------------- a label the catalog cannot take at all
  // `["VerifyEmail_15d"]` is a tool's name, not a call. The store marks that row
  // `schema_valid: false` at write time -- which somebody finds days later, reading the corpus --
  // and the reviewer who ticked *correct* on it was told nothing at all. Same rule, asked while
  // they are still looking at the sample.
  page = await start({ ...ANSWERS(), labelChecked: BARE_NAME_FAULT });
  claims("**a label the catalog cannot take is said before the reviewer is asked anything**",
    !page.el("label-fault").hidden
    && page.el("label-fault").innerHTML.includes("call 1 is the bare name Lookup"));
  claims("**and in the service's own words**, rather than the page's summary of them",
    page.el("label-fault").innerHTML.includes("which tool fires *and with what*"));
  claims("one broken call is one line, because a label makes more than one",
    (page.el("label-fault").innerHTML.match(/<li>/g) || []).length === 1);
  page.inputsNamed("f-domain")[0].checked = true;
  await page.byId.get("submit").onclick();
  for (let n = 0; n < 10; n += 1) await settled();
  claims("**a warning and not a gate** — what the label ought to be is still the reviewer's to say",
    posted(page, "/records").length === 1);

  page = await start({ ...ANSWERS(), labelChecked: BARE_NAME_FAULT });
  page.el("v-write").checked = true;
  await page.el("v-write").onchange();
  page.el("label-text").value = '[{"name": "Lookup", "arguments": {"ma": "KH-9"}}]';
  await page.el("label-text").oninput();
  await waited(400);
  for (let n = 0; n < 10; n += 1) await settled();
  claims("**rewriting the label asks the catalog about the label as it now stands**",
    JSON.parse(posted(page, "/data-quality/label").at(-1).body).label[0].arguments.ma === "KH-9");
  page.answers.labelChecked = { schema_valid: true, faults: [] };
  page.el("label-text").value = '[{"name": "Lookup", "arguments": {"ma": "KH-8"}}]';
  await page.el("label-text").oninput();
  await waited(400);
  for (let n = 0; n < 10; n += 1) await settled();
  claims("and a label that now validates takes the warning back down",
    page.el("label-fault").hidden);

  // A check nobody could make is not a label that passed, and the difference has to be on screen
  // where somebody is looking for the faults.
  page = await start({ ...ANSWERS(),
    refuse: { "/data-quality/label": { status: 422, detail: "the catalog will not read" } } });
  claims("**a check that could not be made is said**, not read as a label with nothing wrong",
    !page.el("label-fault").hidden
    && page.el("label-fault").textContent.includes("the catalog will not read"));

  // -------------------------------------------------- the panel's answer is the proposal
  // Two models spelled the call out in full, agreed with each other, and the page put it on the
  // screen as JSON in a disclosure under the bare name that arrived. A reviewer who agreed had to
  // retype it by hand -- which is how a label two models had written out shipped as a bare name.
  const PANEL = {
    llm: {
      label_agreement: 0,
      consensus: CONSENSUS,
      votes: [
        { model_name: "m1", reason: "Khách đã cho số.", label: CONSENSUS },
        { model_name: "m2", reason: "Đủ thông tin.", label: CONSENSUS }
      ]
    },
    sft: null,
    consensus_calls: CONSENSUS_CALLS
  };
  page = await start({ ...ANSWERS(), labelChecked: BARE_NAME_FAULT, reviewed: PANEL });
  claims("**before anybody is asked the proposal says so**, rather than sitting empty",
    page.el("proposed-call").innerHTML.includes("Nobody has been asked"));
  claims("and there is nothing to take, so the act that takes it cannot be picked",
    page.el("v-take").disabled === true);
  claims("**none of the three acts is ticked for the reviewer**",
    !page.el("v-take").checked && !page.el("v-keep").checked && !page.el("v-write").checked);
  claims("what arrived is drawn from the moment the sample opens",
    page.el("arrived-call").innerHTML.includes("Lookup"));
  await page.byId.get("run-detect").onclick();
  await settle(10);
  claims("finding the personal data proposes nothing, because no panel has spoken",
    page.el("v-take").disabled === true);
  await askPanel(page);

  const proposal = page.el("proposed-call").innerHTML;
  claims("**the proposal is a table: the tool once, then one row per argument**",
    proposal.includes('class="calltable"') && proposal.includes("Lookup")
    && proposal.includes("<th scope=\"row\">ma</th>")
    && proposal.includes("<th scope=\"row\">kenh</th>"));
  claims("**and it is not JSON** — no braces, no quoted keys, nothing to parse by eye",
    !shown(proposal).includes('"ma":') && !shown(proposal).includes("{"));
  claims("the heading says how the panel came to it, over how many reviewers",
    page.el("proposed-note").textContent.includes("more than half of 2"));
  claims("**what arrived is drawn the same way**, so the two compare without either being read as JSON",
    page.el("arrived-call").innerHTML.includes('class="calltable"'));
  claims("and how much of the panel agreed with *what arrived* is said beside it, where it is true",
    page.el("arrived-note").textContent.includes("0%"));
  claims("**the panel having answered is what offers its answer to be taken**",
    page.el("v-take").disabled === false);

  const jury = page.el("jury-said").markup();
  claims("**each reviewer's own answer is a row**, drawn as a call like the other two",
    jury.includes("m1") && jury.includes("m2") && jury.includes('class="calltable"'));
  claims("and its reason with it, which is what a disagreement is read from",
    jury.includes("Khách đã cho số") && jury.includes("Đủ thông tin"));
  claims("**the raw JSON is under that and not instead of it**",
    page.byId.get("out-6").textContent.includes("consensus"));

  page.el("v-take").checked = true;
  await page.el("v-take").onchange();
  claims("taking it is one click — it does not open an editor to be retyped in",
    page.el("label-editor").hidden === true);
  await waited(400);
  await settle(10);
  const took = JSON.parse(posted(page, "/data-quality/personal-data/redact").at(-1).body);
  claims("**and it lands in the record**, as the service read it rather than as the page re-read it",
    same(took.label, CONSENSUS_CALLS));
  claims("the number that came with it goes to be redacted like any other",
    JSON.stringify(took.label).includes(PHONE));

  page.el("v-write").checked = true;
  page.el("v-take").checked = false;
  await page.el("v-write").onchange();
  claims("**writing it yourself starts from the panel's answer**, because the label that arrived"
    + " is the weak half and retyping theirs is the thing this card exists to stop",
    same(JSON.parse(page.el("label-text").value), CONSENSUS_CALLS));
  page.el("label-text").value = "[{not json";
  await page.el("label-text").oninput();
  claims("a box holding something that is not a label says so, rather than drawing `(unnamed)`",
    page.el("label-note").textContent.includes("not JSON"));

  // A panel that could not agree. `consensus` is null and `consensus_calls` empty, which is not
  // the same as a panel that said *no tool is needed* -- and the act that takes it has to say so
  // rather than being a live button that puts nothing in the record.
  page = await start({ ...ANSWERS(),
    reviewed: { llm: { label_agreement: 0, consensus: null, votes: [] }, sft: null,
      consensus_calls: [] } });
  await page.byId.get("run-detect").onclick();
  await settle(10);
  await askPanel(page);
  claims("**a panel that agreed on nothing offers nothing to take**, and says which",
    page.el("v-take").disabled === true
    && page.el("proposed-note").textContent.includes("agreed on nothing"));

  // **The label, and nothing else.** The turns are what a customer said and the catalog is what
  // the assistant was offered; a page that let either be retyped is a page that can make the
  // sample agree with the label instead of the other way round.
  let offered = true;
  for (const id of ["messages-text", "tools-text"]) {
    try { page.el(id); } catch { offered = false; }
  }
  claims("**nothing on the page can retype the turns or the catalog**",
    offered === false);
  page = await start();
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  page.el("v-write").checked = true;
  await page.el("v-write").onchange();
  page.el("label-text").value = '[{"name": "Lookup", "arguments": {"ma": "KH-9"}}]';
  await page.el("label-text").oninput();
  await waited(400);
  for (let n = 0; n < 10; n += 1) await settled();
  const shipping = JSON.parse(posted(page, "/data-quality/personal-data/redact").at(-1).body);
  claims("so what ships carries the turns as they arrived, whatever was done to the label",
    same(shipping.messages, ONE.messages) && same(shipping.tools, ONE.tools)
    && shipping.label[0].arguments.ma === "KH-9");

  // A value unticked after the label was settled. What is on screen is then a copy of spans nobody
  // is ticking any more, which is the same staleness the replacement has and gets the same answer.
  page = await start({ ...ANSWERS(), numbered: [ANSWERS().numbered, NOTHING_NUMBERED] });
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  page.el("v-keep").checked = true;
  await page.el("v-keep").onchange();
  await waited(400);
  for (let n = 0; n < 10; n += 1) await settled();
  const shipped = () => posted(page, "/data-quality/personal-data/redact").length;
  const madeOnce = shipped();
  hit(page.el("keep-table").onchange, "[data-keep]", { keep: PHONE, on: false });
  claims("unticking a value takes the shipping copy down with it too",
    page.el("review-text").textContent.includes("replacing…"));
  await waited(600);
  for (let n = 0; n < 10; n += 1) await settled();
  claims("**and it is made again over what is left**, with nothing to press",
    shipped() === madeOnce + 1
    && JSON.parse(posted(page, "/data-quality/personal-data/redact").at(-1).body).detected.spans.length === 0);

  // Two edits close together with the first copy slow, the same hazard the replacement has: it
  // lands last and is about a label the reviewer has already retyped. Painted, it would put the
  // *old* label's text on the screen and leave them reading a redaction of something they undid.
  page = await start({ ...ANSWERS(),
    redacted: [
      { sample: REDACTED.sample, review_text: "the copy of a label already retyped" },
      { sample: REDACTED.sample, review_text: "the copy of what is on the screen" }
    ],
    slow: { "/data-quality/personal-data/redact": [400, 0] } });
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  page.el("v-write").checked = true;
  await page.el("v-write").onchange();
  await waited(240);
  page.el("label-text").value = '[{"name": "Lookup", "arguments": {"ma": "KH-9"}}]';
  await page.el("label-text").oninput();
  await waited(800);
  for (let n = 0; n < 10; n += 1) await settled();
  claims("**a shipping copy that lands after a newer one is dropped**, not painted over it",
    page.el("review-text").textContent === "the copy of what is on the screen");

  // ------------------------------------------------------------------ submitting
  page = await start();
  page.inputsNamed("f-domain")[0].checked = true;
  page.byId.get("language").value = "en";
  await page.byId.get("submit").onclick();
  for (let n = 0; n < 10; n += 1) await settled();
  const records = posted(page, "/records");
  claims("submit posts one record", records.length === 1);
  claims("**the queue key travels with the record**, so the row is marked done in that transaction",
    records[0].path.includes("queue_key=s1"));
  const sent = JSON.parse(records[0].body);
  claims("the record carries what arrived and what ships",
    sent.messages !== undefined && sent.new_messages !== undefined);
  claims("**what ships is the record the route answered**, not the envelope it came in",
    JSON.stringify(sent.new_label) === JSON.stringify(REDACTED.sample.label)
    && JSON.stringify(sent.new_messages) === JSON.stringify(REDACTED.sample.messages));
  claims("the facets a person ticked travel with the record",
    sent.class.domain === page.inputsNamed("f-domain")[0].value);
  claims("the language declared on the pane rides along", sent.class.language === "en");
  claims("**submit opens the next sample in one motion**",
    page.byId.get("turns").innerHTML.includes("cảm ơn"));
  claims("the statistics are asked again once a row is written",
    posted(page, "/records/stats").length === 2);
  claims("a sample with no call says so, rather than reading as a skipped row",
    page.byId.get("arrived-call").innerHTML.includes("No call"));
  // The facets describe *this* sample. One carried over from the last is a row nobody ticked,
  // stored as though somebody had, and nothing downstream can tell the difference.
  claims("**the next sample starts with no facet ticked**, the domain included",
    !page.inputsNamed("f-domain").some(box => box.checked)
    && !page.inputsNamed("f-ambiguous").some(box => box.checked));

  // Submitting the last one runs the queue out, and the bar must not come back live over an
  // empty screen: `frozen(false)` in a `finally` would undo the freeze the empty queue just asked
  // for, and a reviewer would be looking at a live Submit with nothing to submit.
  page = await start({ ...ANSWERS(), queue: [ONE] });
  await page.byId.get("submit").onclick();
  for (let n = 0; n < 12; n += 1) await settled();
  claims("**submitting the last sample leaves the bar disabled**",
    page.byId.get("submit").disabled && page.byId.get("skip").disabled);
  claims("and says so rather than showing an empty pane",
    page.byId.get("turns").innerHTML.includes("Nothing is waiting"));

  // --------------------------------------------- a refusal a person can act on
  // A body the service could not read comes back as a list with the whole sample echoed inside
  // it. Printed whole, the one thing worth reading — which field — is buried in a cell holding
  // the entire conversation, which is how a missing field went unnoticed for a round.
  page = await start({ ...ANSWERS(), refuse: { "/data-quality/personal-data": { status: 422,
    detail: [{ type: "missing", loc: ["body", "id"], msg: "Field required",
               input: { messages: [{ role: "user", content: SAID }] } }] } } });
  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  claims("**a body the service could not read names the field and what was wrong with it**",
    page.el("said-2").textContent.includes("id: Field required"));
  claims("**and does not print the sample back into the cell**",
    !page.el("said-2").textContent.includes(SAID));

  // ------------------------------------------------------------------ a refused record
  page = await start({ ...ANSWERS(), refuse: { "/records": { status: 422, detail: "tick every declared facet: domain went unanswered" } } });
  await page.byId.get("submit").onclick();
  for (let n = 0; n < 10; n += 1) await settled();
  claims("a refusal lands on the panel that owns it, by name",
    page.byId.get("label-refusal").hidden === false
    && page.byId.get("label-refusal").textContent.includes("domain"));
  claims("**a refused record leaves the reviewer on the sample**",
    page.byId.get("turns").innerHTML.includes(SAID));
  claims("a refused record does not go looking for the next one",
    posted(page, "/queue/next").length === 1);

  // ------------------------------------------------------------------ skipping
  page = await start();
  await page.byId.get("skip").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  claims("skip marks that row, by key", posted(page, "/queue/s1/skip").length === 1);
  claims("skip writes no record", posted(page, "/records").length === 0);
  claims("skip opens the next sample", page.byId.get("turns").innerHTML.includes("cảm ơn"));

  // ------------------------------------------------- the corpus, read back off the store
  //
  // The one thing this page could not do: the queue says what is *waiting* and the statistics say
  // what the whole comes to, and a row somebody wrote was readable nowhere between them. A sample
  // pasted straight in never had a queue row at all, so it went invisible the moment it stored.
  page = await start({ ...ANSWERS(), dataset: STORED, datasetOne: STORED_ONE });
  await page.byId.get("open-dataset").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  claims("opening the corpus asks the store for a page of it",
    posted(page, "/records").some(one => one.method === "GET"));
  const drawn = page.el("dataset-rows").querySelector("tbody").innerHTML;
  claims("every stored row is a line, with the facets it was filed under",
    drawn.includes("debt_collection") && drawn.includes("telesale") && drawn.includes("HIGH"));
  claims("**the redacted copy is what is shown** — the row reads as it ships",
    drawn.includes("&lt;EMAIL_1&gt;"));
  claims("a row nothing could validate says so in its own column",
    drawn.includes(">no<") && drawn.includes(">yes<"));
  claims("the sheet says how much the corpus holds",
    page.byId.get("dataset-note").textContent.includes("2"));

  page.el("dataset-bad").checked = true;
  page.el("dataset-bad").onchange();
  const only = page.el("dataset-rows").querySelector("tbody").innerHTML;
  claims("**the filter leaves only the rows worth going back to**",
    only.includes("telesale") && !only.includes("debt_collection"));

  hit(page.el("dataset-rows").onclick, "[data-stored]", { stored: "d2" });
  for (let n = 0; n < 8; n += 1) await settled();
  const one = page.byId.get("dataset-one").innerHTML;
  // Read off the drawing and not off the absence of a quote: markup the page writes is escaped,
  // so a JSON dump would come out as `&quot;role&quot;` and slip past a check looking for `"role":`.
  claims("opening a row draws its conversation as turns, not as its JSON",
    one.includes("kiểm tra email") && one.includes('class="turn')
    && !one.includes("&quot;role&quot;"));
  claims("**a bare-name label is drawn as the call it claims to be**",
    one.includes("VerifyEmail_15d") && !one.includes("(unnamed)"));
  claims("**and the row says why nothing could validate it**",
    one.includes("never offered") || one.includes("requires"));

  // ------------------------------------------------------------------ the keyboard
  page = await start();
  const steer = page.keys.find(one => one.kind === "keydown").handler;
  let prevented = 0;
  const press = (key, target) => steer({ key, target, preventDefault: () => { prevented += 1; } });
  press("Enter", { tagName: "TEXTAREA" });
  for (let n = 0; n < 6; n += 1) await settled();
  claims("**Enter inside a textarea types a newline** and does not submit",
    prevented === 0 && posted(page, "/records").length === 0);
  press("Enter", { tagName: "DIV" });
  for (let n = 0; n < 10; n += 1) await settled();
  claims("Enter outside a field submits", posted(page, "/records").length === 1);

  // ------------------------------------------------------------------ the facets a person ticks
  page = await start();
  claims("**how arguable a sample is has three levels**, not a yes and a no",
    page.inputsNamed("f-ambiguous").map(box => box.value).join(",") === "LOW,MED,HIGH");
  claims("none of them is ticked for the reviewer, because a level is a claim somebody makes",
    !page.inputsNamed("f-ambiguous").some(box => box.checked));
  page.inputsNamed("f-ambiguous")[1].checked = true;
  page.inputsNamed("f-domain")[0].checked = true;
  await page.byId.get("submit").onclick();
  for (let n = 0; n < 12; n += 1) await settled();
  claims("the level travels with the record as the level, not as a boolean",
    JSON.parse(posted(page, "/records")[0].body).class.ambiguous === "MED");

  // ------------------------------------------------------------------ adding a domain
  page = await start();
  const domains = () => page.el("domain-ticks").innerHTML;
  claims("the domains are drawn in their own block, next to the box that adds one",
    domains().includes("debt_collection") && !page.el("facet-ticks").innerHTML.includes("debt_collection"));
  claims("**a domain the corpus already carries is offered**, though nothing here declares it — "
    + "which is what makes an added one outlast the tab it was typed in",
    domains().includes("insurance_claims"));
  page.inputsNamed("f-domain")[1].checked = true;
  page.el("domain-new").value = "insurance_sales";
  page.el("domain-add").onclick();
  claims("**a domain typed in is offered from that moment**", domains().includes("insurance_sales"));
  claims("**and the domain that was ticked is unticked**, because a sample has one",
    page.inputsNamed("f-domain").filter(box => box.checked).map(box => box.value).join()
    === "insurance_sales");
  claims("and is ticked, because typing it and pressing the button is the claim",
    page.inputsNamed("f-domain").filter(box => box.checked).map(box => box.value).join() === "insurance_sales");
  claims("the box is emptied, so the next one is not typed on top of it",
    page.el("domain-new").value === "");
  await page.byId.get("submit").onclick();
  for (let n = 0; n < 12; n += 1) await settled();
  claims("the added domain travels with the record like any other",
    JSON.parse(posted(page, "/records")[0].body).class.domain === "insurance_sales");

  // A corpus that grew while somebody was labelling. The list has to take the new domain in, and
  // the tick already on it has to survive that: a reviewer who picked a domain and then had the
  // statistics land underneath them has not changed their mind.
  page = await start({ ...ANSWERS(),
    statistics: [STATISTICS,
      { ...STATISTICS,
        counted_distribution_by_facet: { domain: { debt_collection: 3, a_new_domain: 1 } } }] });
  page.inputsNamed("f-domain")[0].checked = true;
  chose(page, { name: "more.jsonl", size: 9, text: async () => '{"a":1}' });
  await page.el("import-run").onclick();
  for (let n = 0; n < 10; n += 1) await settled();
  claims("a domain the corpus grew into is taken into the list without a reload",
    page.el("domain-ticks").innerHTML.includes("a_new_domain"));
  claims("**and the tick already made survives the list being redrawn under it**",
    page.inputsNamed("f-domain").filter(box => box.checked).map(box => box.value).join()
    === "debt_collection");

  page = await start();
  page.el("domain-new").value = "debt_collection";
  page.el("domain-add").onclick();
  claims("a domain already on the list is refused rather than drawn twice",
    page.el("domain-note").textContent.includes("already")
    && (domains().match(/value="debt_collection"/g) || []).length === 1);
  page.el("domain-new").value = "  ";
  page.el("domain-add").onclick();
  claims("and an empty box adds nothing", page.el("domain-note").textContent.includes("type a domain"));

  // ------------------------------------------------------------------ the strip
  page = await start();
  const strip = page.byId.get("strip").innerHTML;
  claims("the strip says how much of the queue is left", strip.includes("waiting"));
  claims("the strip says how many rows are stored", strip.includes("<b>3</b> rows stored"));
  claims("**the strip says how many cells are still empty**, which is the number that changes what to label next",
    strip.includes("<b>14</b> of 15 cells still empty"));
  claims("a figure of one does not read as many", !page.el("said-2").textContent.includes("1 spans"));

  // ------------------------------------------------------------------ the statistics panel
  const stats = page.byId.get("stats").innerHTML;
  // Scoped to the table: the sentence naming the empty cells under it carries the same words, and
  // a check that read the whole panel would pass against a matrix drawn over the corpus alone.
  const matrix = stats.slice(stats.indexOf('<table class="matrix"'), stats.indexOf("</table>"));
  claims("the matrix is drawn over the page's own lists, so an unused value is a visible row of noughts",
    matrix.includes("telesale") && matrix.includes("every_turn"));
  claims("an empty cell is marked as one", matrix.includes('class="cell zero"'));
  claims("the empty cells are named, not just counted", stats.includes("telesale × condition_met"));
  claims("how many tools were offered is read", stats.includes("<b>1</b> tool the catalogs put in front of the model"));
  claims("the duplicate groups are read", stats.includes("<b>1</b> group agreeing"));

  // ------------------------------------------------------------------ import
  page = await start();
  chose(page, { name: "corpus.jsonl", size: 40, text: async () => '{"a":1}\n{"b":2}' });
  await page.byId.get("import-run").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  const sentFile = posted(page, "/queue/import");
  claims("import posts the file's own text, one JSON object per line",
    sentFile.length === 1 && sentFile[0].body === '{"a":1}\n{"b":2}');
  const said = page.byId.get("import-said").innerHTML;
  claims("the import says how many lines were read and how many now wait",
    said.includes("<b>4</b> lines read") && said.includes("<b>2</b> now waiting"));
  claims("**an unreadable line is named by its number**, which is the only thing that can be acted on",
    said.includes("line 3"));
  claims("an import moves the statistics", posted(page, "/records/stats").length === 2);

  // ------------------------------------------------------------------ which database
  page = await start();
  claims("the header says which database a record lands in",
    page.el("store").textContent === "store.sqlite3");
  claims("and never the DSN, which would carry a password",
    !page.el("store").textContent.includes("://"));
  page = await start({ ...ANSWERS(),
    store: { attached: false, describes: null, variable: "DATAFORCE_DATABASE_URL" } });
  claims("with nothing attached it names the variable to set",
    page.el("store").textContent.includes("DATAFORCE_DATABASE_URL")
    && page.el("store").className.includes("none"));
  page = await start({ ...ANSWERS(), store: null });
  claims("**a 200 in the wrong shape claims nothing** rather than saying `set undefined`",
    page.el("store").textContent === "");

  // ------------------------------------------------------------------ pasting one in
  page = await start({ ...ANSWERS(), queue: [] });
  claims("**an empty queue opens the paste box** rather than only saying there is nothing",
    page.el("pasting").hidden === false);
  page = await start();
  claims("with a sample on screen the paste box is put away",
    page.el("pasting").hidden === true);
  page.el("paste-open").onclick();
  claims("and the pane's own button opens it", page.el("pasting").hidden === false);
  page.el("paste-open").onclick();
  claims("and closes it again", page.el("pasting").hidden === true);

  page = await start({ ...ANSWERS(), queue: [] });
  page.el("paste-text").value = JSON.stringify(ONE);
  page.el("paste-now").onclick();
  for (let n = 0; n < 6; n += 1) await settled();
  claims("**a pasted sample is labelled straight away**, with an empty queue behind it",
    page.byId.get("turns").innerHTML.includes(SAID));
  claims("and the box is put away once its sample is on screen",
    page.el("pasting").hidden === true);
  claims("pasting touches the queue not at all", !paths(page).includes("/queue/import"));
  claims("and the bar is live, so it can be submitted",
    !page.byId.get("submit").disabled);
  await page.byId.get("submit").onclick();
  for (let n = 0; n < 12; n += 1) await settled();
  const pasted = posted(page, "/records");
  claims("a pasted sample stores like any other", pasted.length === 1);
  claims("**and carries no queue key**, because nothing was ever waiting for it",
    !pasted[0].path.includes("queue_key"));

  page = await start({ ...ANSWERS(), queue: [] });
  page.el("paste-text").value = `${JSON.stringify(ONE)}\n${JSON.stringify(TWO)}`;
  await page.el("paste-queue").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  claims("paste can add to the queue instead, as the same lines a file would",
    posted(page, "/queue/import").length === 1
    && JSON.parse(posted(page, "/queue/import")[0].body.split("\n")[1]).id === "s2");

  // ------------------------------------------------- pasting one that carries no name at all
  page = await start({ ...ANSWERS(), queue: [] });
  page.el("paste-text").value = JSON.stringify(UNNAMED);
  await page.el("paste-now").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  claims("**a sample with no `id` is named before it is opened** — a raw line carries no name, "
    + "and every route from here on reads a sample by one",
    paths(page).includes("/samples/named"));
  claims("and the line pasted is what was sent to be named",
    JSON.parse(posted(page, "/samples/named")[0].body).messages[0].content.includes("quản trị"));
  claims("**the name is the service's, not one the page made up**",
    page.byId.get("sample-name").textContent.includes("named-by-the-service"));
  claims("and naming it writes no queue row, so this still works with the store turned off",
    !paths(page).includes("/queue/import"));
  claims("the sample is on the screen, not an error where it should be",
    page.byId.get("turns").innerHTML.includes("quản trị"));

  await page.byId.get("run-detect").onclick();
  for (let n = 0; n < 10; n += 1) await settled();
  claims("**the checks run on it** rather than being refused for a field it never had",
    JSON.parse(posted(page, "/data-quality/personal-data")[0].body).id
      === "named-by-the-service-1"
    && page.el("said-2").textContent.includes("value"));

  page.inputsNamed("f-domain")[0].checked = true;
  await page.byId.get("submit").onclick();
  for (let n = 0; n < 12; n += 1) await settled();
  claims("and it stores under that name",
    JSON.parse(posted(page, "/records")[0].body).id === "named-by-the-service-1");

  // A corpus that names its own samples keeps those names: what a corpus calls its rows is not
  // this service's to overwrite, and a re-paste has to land on the row it landed on last time.
  page = await start({ ...ANSWERS(), queue: [] });
  page.el("paste-text").value = JSON.stringify(ONE);
  await page.el("paste-now").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  claims("**a sample that named itself keeps its name**",
    page.byId.get("sample-name").textContent.includes("s1"));

  // A corpus whose label is a list of tool *names* — which is what a sample asking *which tool
  // fires* holds. Drawn as the names they are: `(unnamed)` reads as a call that lost its name.
  page = await start({ ...ANSWERS(), queue: [{ ...UNNAMED, label: ["VerifyEmail_15d"] }] });
  claims("**a label written as bare tool names is drawn as those names**",
    page.byId.get("arrived-call").innerHTML.includes("VerifyEmail_15d")
    && !page.byId.get("arrived-call").innerHTML.includes("(unnamed)"));

  page = await start();
  page.el("paste-text").value = '{"messages": []}\nnot json';
  page.el("paste-now").onclick();
  for (let n = 0; n < 4; n += 1) await settled();
  claims("a paste that will not read names the line, and opens nothing",
    page.el("paste-note").textContent.includes("line 2")
    && page.byId.get("turns").innerHTML.includes(SAID));

  // ------------------------------------------------------------------ the list to pick from
  page = await start({ ...ANSWERS(), queue: [ONE, TWO, THREE], states: { s2: "done" } });
  await page.el("open-list").onclick();
  for (let n = 0; n < 6; n += 1) await settled();
  const rows = page.el("list-rows").innerHTML;
  claims("the list shows every sample, whatever state it is in",
    [ONE, TWO, THREE].every(one => rows.includes(one.messages[0].content)));
  claims("a row already labelled says so, rather than being hidden",
    rows.includes("labelled") && rows.includes('class="row done'));
  claims("each row can be opened and ticked separately",
    rows.includes("data-open=") && rows.includes("data-pick="));

  await clickRow(page, "s3");
  for (let n = 0; n < 6; n += 1) await settled();
  claims("**clicking a row opens that sample**",
    page.byId.get("turns").innerHTML.includes("hủy"));

  page = await start({ ...ANSWERS(), queue: [ONE, TWO, THREE] });
  await page.el("open-list").onclick();
  for (let n = 0; n < 6; n += 1) await settled();
  tickRow(page, "s3", true);
  tickRow(page, "s1", true);
  claims("the button counts what is ticked",
    page.el("list-walk").textContent.includes("2"));
  await page.el("list-walk").onclick();
  for (let n = 0; n < 8; n += 1) await settled();
  claims("**the selected rows become the walk, in arrival order and not tick order**",
    page.byId.get("turns").innerHTML.includes(SAID));
  page.inputsNamed("f-domain")[0].checked = true;
  await page.byId.get("submit").onclick();
  for (let n = 0; n < 14; n += 1) await settled();
  claims("submitting walks on to the next selected row, skipping the unticked one",
    page.byId.get("turns").innerHTML.includes("hủy"));
  claims("and never asks the queue for its own next while a selection is live",
    posted(page, "/queue/next").length === 1);

  // A list is a photograph. Ticking a row the list showed and finding it gone when the walk
  // reaches it is the one way this happens -- a tick cannot pick a row that was never listed.
  page = await start({ ...ANSWERS(), queue: [ONE, TWO],
    refuse: { "/queue/s1": { status: 404, detail: "no queued sample under s1" } } });
  await page.el("open-list").onclick();
  for (let n = 0; n < 6; n += 1) await settled();
  tickRow(page, "s1", true);
  await page.el("list-walk").onclick();
  for (let n = 0; n < 10; n += 1) await settled();
  claims("a ticked row that has gone since the list was drawn is said, not skipped in silence",
    page.el("submit-note").textContent.includes("gone"));
  claims("and the walk carries on to the queue rather than dead-ending",
    paths(page).filter(one => one === "/queue/next").length === 2
    && !page.byId.get("turns").innerHTML.includes("Nothing is waiting"));

  // ------------------------------------------------------------------ nothing waiting
  page = await start({ ...ANSWERS(), queue: [] });
  claims("an empty queue is said in words, not left blank",
    page.byId.get("turns").innerHTML.includes("Nothing is waiting"));
  claims("an empty queue disables the acts that need a sample",
    page.byId.get("submit").disabled && page.byId.get("run-detect").disabled);

  // ------------------------------------------------------------------ no database
  page = await start({ ...ANSWERS(), refuse: { "/records/stats": { status: 503, detail: "no database attached: set DATAFORCE_DATABASE_URL" } } });
  claims("with no store the strip says so in the service's own words",
    page.byId.get("strip").textContent.includes("DATAFORCE_DATABASE_URL"));
  claims("with no store the guide shows the guide and no statistics",
    page.byId.get("stats").innerHTML.includes("DATAFORCE_DATABASE_URL")
    && !page.byId.get("stats").innerHTML.includes("matrix"));

  // ------------------------------------------------------------------ a 200 that is not an answer
  page = await start({ ...ANSWERS(),
    statistics: { ...STATISTICS, counted_distribution_by_domain_and_call_trigger: { debt_collection: null } } });
  claims("**a 200 in the wrong shape is caught** rather than left saying the request is in flight",
    page.byId.get("strip").textContent.includes("unreadable"));
  claims("a 200 in the wrong shape leaves the statistics saying so too",
    page.byId.get("stats").innerHTML.includes("unreadable"));

  console.log(failed ? `\n${failed} failed` : "\nall green");
}

// A throw anywhere in `main` is a failed run, not a silent one.
main().catch(error => fails(`the run stopped: ${error && error.stack ? error.stack : error}`));
