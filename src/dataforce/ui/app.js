// The labelling UI: one fetch per route, and no rule of its own.
//
// Every panel shows what a route answered. The spans, the copy, the outcome, the votes, the
// consensus and the redaction are fields read off a response -- nothing here computes one, because
// a client that disagreed with the service about what a span or a vote is would be a second
// definition of it. The one thing this page composes is the record it submits, because nothing
// else composes one.
//
// The screen is two panes. The left one holds the sample and is never replaced; the right one
// holds the two decisions a person actually makes. Everything between those two -- five calls the
// reviewer cannot influence -- is one button, because a screen per machine step is a screen with
// nothing on it to decide.

const API = "/text2text/tool-decision";

// --------------------------------------------------------------------------- plumbing

const $ = id => document.getElementById(id);
const json = v => JSON.stringify(v, null, 2);
// Every interpolation into markup goes through this. What a span reads is a value out of the
// sample, and a corpus that says `<b>` is a corpus, not an instruction.
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const wordFor = (number, one, more) => (number === 1 ? one : more);

// Offsets are code points, because that is what slicing `review_text` in Python counts. A browser
// indexes UTF-16 units, so `text.slice(start, end)` reads a different string from the same two
// numbers the moment something outside the BMP is in the text.
const chars = text => Array.from(text);
const sliced = (text, start, end) => chars(text).slice(start, end).join("");

// One call, and one reading of what came back. A refusal is the service's own `detail`, never
// paraphrased and never retried: a second call is a person pressing the button again.
async function ask(path, how) {
  let resp;
  try {
    resp = await fetch(API + path, how);
  } catch (error) {
    return { ok: false, detail: `no answer from the service: ${error}` };
  }
  const text = await resp.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (resp.ok) return { ok: true, data };
  const detail = data && data.detail !== undefined ? data.detail : data;
  return { ok: false, detail: `${resp.status} — ${sayDetail(detail)}` };
}

// What a refusal reads as. A sentence is the service's own and is passed through untouched.
//
// **A body the service could not read is not a sentence.** FastAPI answers one with a list of
// `{loc, msg, input}`, and `input` is *the whole sample echoed back* -- so dumping it prints the
// entire conversation into a cell and buries the one thing a person can act on. Which field, and
// what was wrong with it, is the whole of what they need.
function sayDetail(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length && detail.every(one => one && one.msg)) {
    return detail.map(one =>
      `${(one.loc || []).filter(at => at !== "body").join(".") || "the body"}: ${one.msg}`).join("; ");
  }
  return json(detail);
}

const call = (path, body) => ask(path, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body)
});

function show(id, value, kind = "") {
  const el = $(id);
  el.className = kind;
  el.textContent = value === undefined ? "" : json(value);
}

function say(id, said, kind = "") {
  const el = $(id);
  el.className = kind ? `${el.dataset.base || "note"} ${kind}` : (el.dataset.base || "note");
  el.textContent = said;
}

// --------------------------------------------------------------------------- what the page holds

const held = {
  key: null,        // the queue row this sample came from, posted back to say it is done
  sample: null,     // the sample as the queue handed it over
  detected: null,   // the scan's answer, with the spans as they came back
  rows: [],         // the span rows as the human is editing them, added ones included
  keeps: {},        // which rows the human is handing back
  handed: null,     // the detect shape with the spans as they left it
  replaced: null,   // what the replacement answered
  review: null,     // what the reviewers said
  edited: null,     // the three, as they ship before redaction
  record: null      // what will be posted
};

const ticked = { verifier: null, jury: [], sft: null };

// ---------------------------------------------------------------------------- the machine steps

// The two checks, and the row each one writes on. The step numbers are the service's own and are
// kept because the refusals name them; what the reviewer reads is the `what`.
//
// **The replacement is not one of them.** It is not a decision and never was: a span the reviewer
// keeps is a value that has to come out, so it comes out as they tick. It reports on the row of
// the scan that found it, because that is the check it belongs to.
const CHECKS = [
  { step: 2, what: "Personal data", said: "said-2" },
  { step: 6, what: "Label", said: "said-6" }
];

const checked = {};

// A machine answer is a verdict, not a payload: one cell each, with the route's own JSON behind a
// disclosure. A verdict nobody can check is worse than a payload nobody reads, which is why the
// disclosure stays.
function mark(step, state, text) {
  checked[step] = { state, text };
  paintChecks();
}

// Only the third column. The first is the check's name and the second holds the tick boxes, both
// written once in the markup: a repaint that rebuilt the middle cell would throw away the model
// the reviewer picked every time a step reported.
function paintChecks() {
  for (const { step, said } of CHECKS) {
    const at = checked[step] || { state: "", text: "not run" };
    const kind = { answered: "ok", bad: "bad", unasked: "bad", wait: "busy", edited: "ok" }[at.state] || "";
    const cell = $(said);
    cell.className = `said${kind ? ` ${kind}` : ""}`;
    cell.textContent = at.text || "not run";
  }
}

// A step that could not ask at all, which is not a refusal and does not read like one: nothing was
// called, so nothing refused anything, and someone sent looking for a refusal would be reading a
// service log for a request it never received.
function cannotAsk(step, why) {
  mark(step, "unasked", why);
  return false;
}

// **A refusal is shown in the cell of the check that was refused**, in the service's own words.
// Not in the payload box beside it: that box holds what the route last answered, and writing a
// refusal into it would write over the very thing a reviewer opens to check a verdict they doubt.
async function asking(step, body, path) {
  mark(step, "wait", "asking…");
  const answer = await call(path, body);
  if (!answer.ok) mark(step, "bad", answer.detail);
  return answer;
}

// --------------------------------------------------------------------------- the queue

// The sample on screen, and how much of the corpus is left. Nothing is pasted: a reviewer who has
// to paste JSON before each sample is doing data entry, and the time that costs is the whole of
// what makes a corpus expensive.
let left = null;

// Rows a reviewer ticked in the list, in the order they will be walked. Empty means *whatever the
// queue offers next*, which is what a reviewer who never opens the list gets.
let walking = [];

async function askNext() {
  while (walking.length) {
    const key = walking.shift();
    const answer = await ask(`/queue/${encodeURIComponent(key)}`, {});
    if (answer.ok) {
      left = answer.data;
      openSample(answer.data.sample, answer.data.key);
      return paintStrip();
    }
    // A picked row the queue no longer holds. Said rather than skipped in silence: the reviewer
    // chose it, and a selection that quietly shrinks is a selection they cannot trust.
    say("submit-note", `a picked sample is gone: ${answer.detail}`, "bad");
  }
  const answer = await ask("/queue/next", {});
  if (!answer.ok) {
    left = null;
    return sayNoQueue(answer.detail);
  }
  left = answer.data;
  openSample(answer.data.sample, answer.data.key);
  paintStrip();
}

function sayNoQueue(said) {
  held.key = null;
  held.sample = null;
  $("turns").innerHTML = `<div class="empty">${esc(said)}</div>`;
  $("catalog").innerHTML = "";
  $("sample-name").textContent = "";
  $("tool-count").textContent = "";
  paintStrip();
  frozen(true);
  // Nothing waiting is not a dead end. The box a person would go looking for is opened for them,
  // in the pane that says *the sample*, so the screen offers the next move rather than only
  // reporting that there is none.
  showPasting(true);
}

// The pasting box, shown or put away. Kept out of `openSample` on purpose: a reviewer who opened
// it and then submitted the sample they were on should find it where they left it.
function showPasting(open) {
  $("pasting").hidden = !open;
  if (open) $("paste-text").focus();
}

function frozen(off) {
  for (const id of ["run-checks", "skip", "submit"]) $(id).disabled = off;
}

// Every answer on the right belongs to the sample that was on the left. A new sample makes all of
// them answers about something else, so they go rather than being carried into a record they are
// not about.
function openSample(sample, key) {
  held.key = key || null;
  held.sample = sample || null;
  forgetEverything();
  if (!sample) {
    return sayNoQueue("Nothing is waiting. Import a file, or come back when somebody adds one.");
  }
  frozen(false);
  $("sample-name").textContent = sample.id ? `#${sample.id}` : "";
  show("raw-sample", sample);
  paintTurns();
  paintCatalog();
  paintCalls();
  fillEditors();
  $("v-correct").checked = true;
  $("label-editor").hidden = true;
  // By name, over the declaration: `domain` is drawn in its own block now, and a sweep of one
  // container would leave the previous sample's domain ticked on this one.
  for (const facet of DECLARED_FACETS) {
    for (const box of document.querySelectorAll(`input[name="f-${facet.name}"]`)) box.checked = false;
  }
  say("domain-note", "");
}

// --------------------------------------------------------------- the sample, rendered as itself

// A conversation and not a payload. The reviewer is judging whether a label fits a conversation,
// and a conversation shown as JSON is one they have to decode before they can judge it.
function paintTurns() {
  const turns = held.sample.messages || [];
  if (!turns.length) {
    $("turns").innerHTML = '<div class="empty">This sample carries no turns.</div>';
    return;
  }
  $("turns").innerHTML = turns.map(turn => {
    const who = String(turn.role ?? "?");
    const said = typeof turn.content === "string" ? turn.content
      : turn.content == null ? "" : json(turn.content);
    const calls = turn.tool_calls ? `<div class="calls">${drawCalls(turn.tool_calls)}</div>` : "";
    return `<div class="turn ${esc(who)}"><div class="who">${esc(who)}</div>`
      + `<div class="said">${esc(said)}${calls}</div></div>`;
  }).join("");
}

function paintCatalog() {
  const tools = held.sample.tools || [];
  $("tool-count").textContent = `${tools.length} ${wordFor(tools.length, "tool", "tools")}`;
  if (!tools.length) {
    $("catalog").innerHTML = '<div class="empty">No tools were offered.</div>';
    return;
  }
  $("catalog").innerHTML = tools.map(tool => {
    const spec = tool.function || tool;
    const args = Object.keys((spec.parameters || {}).properties || {});
    return `<div class="tool"><b>${esc(spec.name ?? "(unnamed)")}</b>`
      + (args.length ? `<span class="args"> (${esc(args.join(", "))})</span>` : "")
      + (spec.description ? `<div class="note">${esc(spec.description)}</div>` : "")
      + "</div>";
  }).join("");
}

// One call, drawn however the corpus wrote it: `{name, arguments}`, an OpenAI-shaped
// `{type, function}`, or **a bare tool name**, which is what a corpus labelling *which tool fires*
// and nothing else holds. A string drawn through `spec.name` reads `(unnamed)`, which looks like a
// broken call rather than like the kind of label it is.
const drawCalls = calls => calls.map(one => {
  const spec = typeof one === "string" ? { name: one } : (one && one.function) || one || {};
  const args = spec.arguments === undefined ? "" : json(spec.arguments);
  return `<div class="call"><b>${esc(spec.name ?? "(unnamed)")}</b>`
    + (args ? `<div class="args">${esc(args)}</div>` : "") + "</div>";
}).join("");

// The label the sample arrived with, drawn where the decision about it is made.
function paintCalls() {
  const label = held.sample.label;
  $("calls").innerHTML = !label || !label.length
    ? '<div class="nocall">No call — the turn needs no tool. That is an answer, not a skipped row.</div>'
    : drawCalls(label);
}

// --------------------------------------------------------------------------- which models answer

const TICK_LISTS = ["verifier-ticks", "jury-ticks", "sft-ticks"];

let drawn = null;

async function paintTicks() {
  const answer = await ask("/models", {});
  if (!answer.ok) return sayInTicks(answer.detail);
  // **The route answers a bare array of names.** Reading a `models` key off it finds `undefined`
  // on every deployment, every list draws empty, and the run stops on `tick a verifier first`
  // with nothing to tick -- which is exactly what it did. Anything else claims nothing.
  const served = Array.isArray(answer.data) ? answer.data : [];
  if (!served.length) {
    // And forgotten, so a directory that fills up again is drawn rather than matching what was
    // last drawn and being skipped.
    drawn = null;
    return sayInTicks("no model is configured: config/model/ holds none this deployment can serve");
  }
  // Asked again whenever the window comes back, because `config/model/` is a directory a
  // deployment edits while the service is up. A list that has not changed is not drawn again:
  // rewriting the markup builds new elements, which takes the focus out of one and flickers the
  // row. What it does *not* protect is the reviewer's picks -- `retick` holds those, because a
  // list that really did change rewrites the markup too.
  if (same(served, drawn)) return;
  drawn = served;
  $("verifier-ticks").innerHTML = served.map(name => tickBox("verifier", name)).join("");
  $("jury-ticks").innerHTML = served.map(name => tickBox("jury", name)).join("");
  $("sft-ticks").innerHTML = '<label class="inline"><input type="radio" name="sft" value="" checked> none</label>'
    + served.map(name => tickBox("sft", name)).join("");
  retick(served);
}

// What the page starts with: the first model served, verifying and on the panel alone. A default
// here and not on the facets because this is not a claim about the sample -- it is which machine
// answers, and a reviewer who never touches it gets a run rather than a refusal.
//
// A model the reviewer had picked and that is still served keeps its tick: the lists are redrawn
// only because the directory changed, and that is no reason to undo their choice.
function retick(served) {
  const wasVerifier = ticked.verifier;
  const wasJury = ticked.jury.filter(name => served.includes(name));
  const wasSft = ticked.sft;
  ticked.verifier = served.includes(wasVerifier) ? wasVerifier : served[0];
  ticked.jury = wasJury.length ? wasJury : [served[0]];
  ticked.sft = served.includes(wasSft) ? wasSft : null;
  for (const box of document.querySelectorAll('input[name="verifier"]')) {
    box.checked = box.value === ticked.verifier;
  }
  for (const box of document.querySelectorAll('input[name="jury"]')) {
    box.checked = ticked.jury.includes(box.value);
  }
  for (const box of document.querySelectorAll('input[name="sft"]')) {
    box.checked = box.value === (ticked.sft || "");
  }
}

const tickBox = (name, value) =>
  `<label class="inline"><input type="${name === "jury" ? "checkbox" : "radio"}" name="${name}"`
  + ` value="${esc(value)}"> ${esc(value)}</label>`;

const sayInTicks = said => TICK_LISTS.forEach(id => { $(id).innerHTML = `<span class="none">${esc(said)}</span>`; });
const readTick = name => (document.querySelector(`input[name="${name}"]:checked`) || {}).value || "";

// --------------------------------------------------------------------------- forgetting

function forgetEverything() {
  held.detected = null;
  held.rows = [];
  held.keeps = {};
  held.review = null;
  held.record = null;
  held.handed = null;
  held.replaced = null;
  clearTimeout(copySoon);
  copyAt += 1;
  for (const id of ["span-table", "keep-table"]) $(id).querySelector("tbody").innerHTML = "";
  for (const id of ["out-2", "out-5", "out-6", "record"]) show(id, undefined);
  say("span-note", "");
  say("checks-note", "Two calls: the personal-data scan, then the reviewers.");
  hideRefusals();
  for (const step of CHECKS.map(one => one.step)) delete checked[step];
  paintChecks();
  sayVerdict("checks-verdict", "not run", "");
  sayVerdict("data-verdict", "no scan yet", "");
  sayVerdict("label-verdict", "", "");
}

function sayVerdict(id, said, kind) {
  $(id).className = `verdict${kind ? ` ${kind}` : ""}`;
  $(id).textContent = said;
}

function hideRefusals() {
  for (const id of ["data-refusal", "label-refusal"]) {
    $(id).hidden = true;
    $(id).textContent = "";
  }
}

// --------------------------------------------------------------------------- the one button

// Both checks in order. One that fails names itself and stops the one after it: a vote asked
// about a sample the service has already refused to read is a model call spent on nothing.
//
// Never on load. The reviewers' vote spends a model call, and a corpus is walked by people who
// skip -- so a sample opened and passed over has to be able to cost nothing.
const RUNS = { 2: detect, 6: review };

async function runChecks() {
  if (!held.sample) return;
  frozen(true);
  sayVerdict("checks-verdict", "running…", "busy");
  hideRefusals();
  try {
    for (const { step, what } of CHECKS) {
      say("checks-note", `Asking: ${what.toLowerCase()}…`);
      if (!await RUNS[step]()) {
        sayVerdict("checks-verdict", `stopped at ${what.toLowerCase()}`, "bad");
        say("checks-note", `${what} did not answer, so the steps after it were not asked.`, "bad");
        return;
      }
    }
    sayVerdict("checks-verdict", "both answered", "ok");
    say("checks-note", "Every machine step answered. What is left is yours.");
  } finally {
    frozen(!held.sample);
  }
}

// --------------------------------------------------------------------------- personal data

async function detect() {
  if (!held.sample) return cannotAsk(2, "no sample");
  if (!ticked.verifier) return cannotAsk(2, "tick a verifier first");
  const answer = await asking(2, {
    ...held.sample, language: $("language").value, verifier_model: ticked.verifier
  }, "/data-quality/personal-data");
  if (!answer.ok) return false;
  held.detected = answer.data;
  held.rows = answer.data.spans.map(span => ({ ...span }));
  held.keeps = {};
  held.handed = null;
  held.replaced = null;
  held.record = null;
  const found = held.rows.length;
  show("out-2", answer.data);
  paintSpanTable();
  paintKeepTable();
  sayVerdict("data-verdict", found ? `${found} to confirm` : "nothing found",
    found ? "bad" : "ok");
  // A scan that found something opens its own working behind the verdict, unasked: the reviewer
  // is about to be asked which of those spans are real, and the numbers are how they tell.
  $("scan-raw").open = found > 0;
  // Straight on, not on a timer: the run is asking for the whole check, and a copy made 200ms
  // after the run said it was done is a copy the reviewer never saw being made.
  return refreshCopy();
}

function paintSpanTable() {
  $("span-table").querySelector("tbody").innerHTML = held.rows.map((span, i) => `
    <tr>
      <td>${esc(span.id)}</td>
      <td><input class="num" data-f="start" data-i="${i}" value="${esc(span.start)}"></td>
      <td><input class="num" data-f="end" data-i="${i}" value="${esc(span.end)}"></td>
      <td><input data-f="personal_data_class" data-i="${i}" value="${esc(span.personal_data_class)}"></td>
      <td><input data-f="placeholder" data-i="${i}" value="${esc(span.placeholder)}"></td>
      <td class="value" data-value="${i}"></td>
    </tr>`).join("");
  paintValues();
}

const typedIn = (field, i) => $("span-table").querySelector(`[data-f="${field}"][data-i="${i}"]`).value;

// Every row re-read and re-sliced, and the rule an unreadable edit broke named. Nothing is
// computed here: the slice is what the offsets already say, shown so an edit is visible.
function editedSpans() {
  const text = held.detected.review_text;
  const length = chars(text).length;
  return held.rows.map((span, i) => {
    const numbers = { start: typedIn("start", i), end: typedIn("end", i) };
    for (const [field, value] of Object.entries(numbers)) {
      if (!/^\d+$/.test(String(value).trim())) return { i, broke: `row ${i + 1}: ${field} is not a whole number` };
    }
    const start = Number(numbers.start);
    const end = Number(numbers.end);
    if (end <= start) return { i, broke: `row ${i + 1}: end is not past start` };
    if (end > length) return { i, broke: `row ${i + 1}: end is outside the text, which is ${length} characters long` };
    return {
      i,
      id: span.id,
      start,
      end,
      personal_data_class: typedIn("personal_data_class", i),
      placeholder: typedIn("placeholder", i),
      reason: span.reason ?? null,
      value: sliced(text, start, end)
    };
  });
}

function paintValues() {
  for (const row of editedSpans()) {
    const cell = $("span-table").querySelector(`[data-value="${row.i}"]`);
    cell.className = row.broke ? "value bad" : "value";
    cell.textContent = row.broke || row.value;
  }
}

const comparable = spans => spans.map(({ start, end, personal_data_class, placeholder }) =>
  ({ start, end, personal_data_class, placeholder }));

function checkSpans() {
  const rows = editedSpans();
  paintValues();
  const broke = rows.filter(row => row.broke);
  say("span-note", broke.length
    ? `${broke.map(row => row.broke).join("; ")} — nothing was called`
    : "every row re-sliced", broke.length ? "bad" : "");
  const edited = !broke.length && !same(comparable(rows), comparable(held.detected.spans));
  if (!broke.length) {
    held.rows = rows.map(({ i, value, ...span }) => span);
    if (edited) copyLater();
    paintKeepTable();
  }
}

// A row the reviewer added. Numbered after the last, because `id` is 1-based in span order and is
// what the confirmation was asked about -- and nothing asks it again about a span it never saw.
function addSpan() {
  if (!held.detected) return say("span-note", "the scan has not answered: there is no text for a span to index", "bad");
  // Read off the table as it stands, an unreadable row included: what someone typed is theirs,
  // and a row that does not parse yet is not a reason to put the detected offsets back.
  held.rows = held.rows.map((span, i) => ({
    ...span,
    start: typedIn("start", i),
    end: typedIn("end", i),
    personal_data_class: typedIn("personal_data_class", i),
    placeholder: typedIn("placeholder", i)
  }));
  held.rows.push({
    id: Math.max(0, ...held.rows.map(span => span.id)) + 1,
    start: 0, end: 0, personal_data_class: "", placeholder: "", reason: null
  });
  paintSpanTable();
  copyLater();
  say("span-note", "a row added: type its offsets, then re-read");
}

// --------------------------------------------------------------- which spans the reviewer keeps

// `auto` keeps the outermost span, which is the rule the scan already applied to what it detected.
// It is here for the rows *you* moved or added: an edit can put one span inside another, and this
// says which of the two you meant to hand back.
//
// Over the rows still ticked, and that is the whole of the rule: a span is inside a *kept* longer
// one or it is inside nothing. Untick the outer row and the inner one is what is left to hand
// back -- measured against every row instead, unticking an email would take the phone number
// inside it out of the record with no way to put it back.
const inside = (span, spans) => spans.some(other =>
  !other.broke && held.keeps[other.i] !== false
  && other.start <= span.start && span.end <= other.end
  && other.end - other.start > span.end - span.start);

const dropped = (row, rows) => held.keeps[row.i] === false || ($("auto").checked && inside(row, rows));

function paintKeepTable() {
  if (!held.detected) return;
  const rows = editedSpans();
  $("keep-table").querySelector("tbody").innerHTML = rows.map(row => {
    if (row.broke) return `<tr><td></td><td colspan="4" class="value bad">${esc(row.broke)}</td></tr>`;
    const nested = $("auto").checked && inside(row, rows);
    const out = dropped(row, rows);
    return `<tr class="${out ? "dropped" : ""}">
      <td><input type="checkbox" data-keep="${row.i}"${held.keeps[row.i] === false ? "" : " checked"}${nested ? " disabled" : ""}></td>
      <td>${esc(row.personal_data_class)}</td>
      <td>${esc(row.placeholder)}</td>
      <td class="value">${esc(row.value)}</td>
      <td class="note">${nested ? "inside a longer span" : held.keeps[row.i] === false ? "not personal data" : ""}</td>
    </tr>`;
  }).join("");
}

// The spans as the human left them: what the reviewer hands back, and the only spans anything
// replaces.
function handedBack() {
  const rows = editedSpans().filter(row => !row.broke);
  return {
    review_text: held.detected.review_text,
    claims: held.detected.claims,
    spans: rows.filter(row => !dropped(row, rows)).map(({ i, value, ...span }) => span)
  };
}

// How long a pause counts as *done typing*. An offset is typed a digit at a time and each digit
// is a different set of spans, so one call per keystroke would be a call per character.
const COPY_AFTER = 180;

let copySoon = null;
// Which replacement is the newest. An answer to an older one landing after it is dropped rather
// than painted: it is the copy of spans that are no longer on the screen.
let copyAt = 0;

// **Nothing here is asked for.** A span the reviewer keeps is a value that has to come out, so
// unticking one, dragging an offset or adding a row makes the copy wrong the moment it happens --
// and a copy that is wrong until somebody presses a button is a copy that ships wrong.
function copyLater() {
  held.handed = null;
  held.replaced = null;
  held.record = null;
  show("out-5", undefined);
  sayPersonalData();
  clearTimeout(copySoon);
  copyAt += 1;
  copySoon = setTimeout(refreshCopy, COPY_AFTER);
}

async function refreshCopy() {
  if (!held.detected) return cannotAsk(2, "the scan has not answered");
  if (editedSpans().some(row => row.broke)) {
    mark(2, "bad", "a span row is unreadable, so nothing was replaced");
    return false;
  }
  const handed = handedBack();
  const mine = (copyAt += 1);
  const answer = await call("/data-quality/personal-data/replace", handed);
  if (mine !== copyAt) return false;
  if (!answer.ok) {
    mark(2, "bad", answer.detail);
    return false;
  }
  held.handed = handed;
  held.replaced = answer.data;
  show("out-5", answer.data);
  sayPersonalData();
  return true;
}

// One line for the scan and the copy together, because they are one act. What the scan found is a
// number the reviewer is about to change, and what came out is the consequence of their ticking.
function sayPersonalData() {
  if (!held.detected) return;
  const found = held.rows.length;
  const scan = found ? `${found} ${wordFor(found, "span", "spans")} found` : "nothing found";
  if (!held.replaced) return mark(2, "wait", `${scan} · replacing…`);
  const kept = held.handed.spans.length;
  mark(2, "answered", `${scan} · ${kept
    ? `${kept} ${wordFor(kept, "value", "values")} replaced`
    : "nothing to replace"}`);
}

// --------------------------------------------------------------------------- the reviewers

async function review() {
  if (!held.sample) return cannotAsk(6, "no sample");
  const answer = await asking(6, {
    ...held.sample,
    language: $("language").value,
    jury_models: ticked.jury,
    sft_model: ticked.sft
  }, "/ai-review");
  if (!answer.ok) return false;
  held.review = answer.data;
  mark(6, "answered", sayAgreement(answer.data));
  show("out-6", answer.data);
  sayVerdict("label-verdict", sayAgreement(answer.data), "");
  return true;
}

// What the panel came to, in one line. The number is the service's own `label_agreement`: this
// reads it and rounds it for the screen, and computes nothing.
function sayAgreement(reviewed) {
  const agreed = ((reviewed || {}).llm || {}).label_agreement;
  if (typeof agreed !== "number") return "reviewed";
  return `${Math.round(agreed * 100)}% agreement with the label`;
}

// --------------------------------------------------------------------------- the label editor

function fillEditors() {
  if (!held.sample) return;
  $("messages-text").value = json(held.sample.messages ?? []);
  $("tools-text").value = json(held.sample.tools ?? []);
  $("label-text").value = json(held.sample.label ?? null);
  paintShipped();
}

// A box the human did not open reads back what was in it, so `correct` and an untouched editor
// agree. Something that is not JSON is carried as `{unparsed: <text>}` -- never dropped, never
// guessed at.
function typedOr(id, arrived) {
  if (!$("v-modify").checked) return arrived;
  try { return JSON.parse($(id).value); } catch { return { unparsed: $(id).value }; }
}

function paintShipped() {
  if (!held.sample) return;
  const arrived = {
    messages: held.sample.messages ?? [],
    tools: held.sample.tools ?? [],
    label: held.sample.label ?? null
  };
  held.edited = {
    messages: typedOr("messages-text", arrived.messages),
    tools: typedOr("tools-text", arrived.tools),
    label: typedOr("label-text", arrived.label)
  };
  const unparsed = [["messages", "messages-text"], ["tools", "tools-text"], ["label", "label-text"]]
    .filter(([, id]) => ($("v-modify").checked ? typedOr(id, {}).unparsed !== undefined : false))
    .map(([named]) => named);
  say("label-note", unparsed.length
    ? `${unparsed.join(", ")}: not JSON, carried as {unparsed: …}`
    : "all three re-parsed", unparsed.length ? "bad" : "");
  held.record = null;
}

// ------------------------------------------------------------------ the facets a person ticks

// **This page's own list, and the only one there is.** A tickable value is a thing a person
// chooses, and the store has no use for one until a sample carries it -- so a read of the store
// answers what the rows hold, never what they were allowed to hold, and nothing below the edge
// keeps a copy of this. The cost, stated: a facet the profile declares and this list never draws
// is a column that is always null, and nothing but somebody reading both catches it.
//
// `language` is not in it. The sample pane declares it for the scan and the jury, and it rides to
// the row from there -- asking again would be one sample described in two places.
const DECLARED_FACETS = [
  { name: "domain", pick: "one",
    values: ["debt_collection", "telesale", "bill_reminder", "customer_care"],
    said: "what the bot does, not the customer's industry. A column, so a sample without it is "
      + "refused. Add one below if none of these is it" },
  { name: "call_trigger", pick: "any",
    values: ["condition_met", "user_utterance", "every_turn"],
    said: "one per call, so tick every way this sample fires. Nothing ticked is a sample that calls nothing" },
  { name: "direction", pick: "one", values: ["inbound", "outbound"],
    said: "who placed the call. Goes to notes, because not every corpus this table holds is a call bot" },
  { name: "ambiguous", pick: "one", values: ["LOW", "MED", "HIGH"],
    said: "how arguable this sample is. A column, so a sample without it is refused — two "
      + "annotators differing on a HIGH one is signal, not a mistake by either" },
  { name: "have_conversation_flow", pick: "yes",
    said: "a step in a scripted flow, where reaching it is what obliges the call. Goes to notes" }
];

// How many of a facet's values one sample carries. Said in words because the shape of the input
// is not an explanation: a person reading the guide before they start has no tick box in front of
// them to infer it from.
const PICK_SAID = {
  one: "tick one",
  any: "tick every one that applies",
  yes: "tick it, or leave it"
};

// A value somebody typed into the *add* box, per facet. Offered from that moment, and still
// offered after a reload as soon as one sample carries it -- the statistics answer which values
// the rows hold and those are folded in below. Until a sample carries it, it is this tab's own.
const addedValues = {};

// Which values a facet offers: what is declared here, what the corpus already holds, and what was
// added here. The corpus is folded in only for a facet that picks **one** -- a set-valued facet is
// counted by the whole set, so its keys are combinations and not values, and folding them in would
// offer `["condition_met"]` as something to tick.
function facetValues(name) {
  const facet = DECLARED_FACETS.find(one => one.name === name);
  if (!facet || !facet.values) return [];
  const byFacet = (counted || {}).counted_distribution_by_facet || {};
  const stored = facet.pick === "one" ? Object.keys(byFacet[name] || {}) : [];
  return [...new Set([...facet.values, ...stored, ...(addedValues[name] || [])])];
}

// The guide's list is this same declaration read a second way. What a facet means is written once,
// so the guide a person reads and the panel they tick on cannot disagree about it.
function paintGuideFacets() {
  $("guide-facets").innerHTML = DECLARED_FACETS.map(facet =>
    `<div class="facet"><b>${esc(facet.name)}</b>`
    + `<span class="pick">${esc(PICK_SAID[facet.pick])}</span>`
    + (facet.values ? `<span class="values">${esc(facetValues(facet.name).join("  ·  "))}</span>` : "")
    + `<div class="note">${esc(facet.said)}</div></div>`).join("");
}

const tickInput = facet =>
  facet.pick === "yes"
    ? `<label class="inline"><input type="checkbox" name="f-${facet.name}"> yes</label>`
    : facetValues(facet.name).map(value =>
        `<label class="inline"><input type="${facet.pick === "one" ? "radio" : "checkbox"}"`
        + ` name="f-${facet.name}" value="${esc(value)}"> ${esc(value)}</label>`).join("");

// Nothing is pre-ticked where a value would be a claim nobody made: a default on `domain` is a
// facet filled in by the page, and a declared facet is exactly the kind nothing may fill in.
//
// `domain` is drawn on its own, because the box that adds one belongs beside the list it adds to.
function paintFacetTicks() {
  paintDomainTicks();
  $("facet-ticks").innerHTML = DECLARED_FACETS.filter(facet => facet.name !== "domain").map(facet =>
    `<div class="lab">${esc(facet.name)}</div>`
    + `<div class="tickbox">${tickInput(facet)}</div>`
    + `<div class="note">${esc(facet.said)}</div>`).join("");
}

// What was on the screen last time, so a repaint that would draw the same list draws nothing:
// rewriting the markup destroys the tick boxes, and the statistics landing under a reviewer who
// has just ticked a domain must not take the tick with them.
let domainsDrawn = null;

function paintDomainTicks() {
  const facet = DECLARED_FACETS.find(one => one.name === "domain");
  const values = facetValues("domain");
  const drawing = values.join("\u0000");
  if (drawing === domainsDrawn) return;
  domainsDrawn = drawing;
  const was = readTick("f-domain");
  $("domain-ticks").innerHTML = tickInput(facet);
  $("domain-said").textContent = facet.said;
  tickDomain(was);
}

// One radio, set by value. Written out rather than left to the browser's own grouping because
// this also has to put a tick back on a list that has just been rewritten under it.
function tickDomain(value) {
  for (const box of document.querySelectorAll('input[name="f-domain"]')) {
    box.checked = !!value && box.value === value;
  }
}

// A domain the declared list does not carry. Offered from here on, and permanent as soon as one
// sample is stored with it -- so it is worth typing carefully: **nothing on this page takes one
// away again**, and a typo that reaches a row is offered until somebody fixes that row.
function addDomain() {
  const said = $("domain-new").value.trim();
  if (!said) return say("domain-note", "type a domain first", "bad");
  if (facetValues("domain").includes(said)) {
    return say("domain-note", `${said} is already offered`, "bad");
  }
  addedValues.domain = [...(addedValues.domain || []), said];
  paintDomainTicks();
  tickDomain(said);
  $("domain-new").value = "";
  say("domain-note", `${said} added and ticked — it stays offered once a sample carries it`);
}

// What the record carries under `class`: the declared facets and nothing else. A facet nobody
// ticked is left out rather than sent as null -- the route names it by name, which reads as a
// facet to go and tick rather than as a column that refused a value.
function readDeclaredFacets() {
  const answered = { language: $("language").value };
  for (const facet of DECLARED_FACETS) {
    const boxes = [...document.querySelectorAll(`input[name="f-${facet.name}"]`)];
    if (facet.pick === "yes") answered[facet.name] = boxes[0].checked;
    else if (facet.pick === "any") answered[facet.name] = boxes.filter(box => box.checked).map(box => box.value);
    else {
      const one = boxes.find(box => box.checked);
      if (one) answered[facet.name] = one.value;
    }
  }
  return answered;
}

// --------------------------------------------------------------------------- the record

// The record this page assembles, and the only thing it composes. What arrived is kept and what
// ships sits beside it under `new_`: the human's edits, then every span they handed back replaced
// wherever its value occurs. The replacing is the service's -- the offsets index `review_text`,
// and `messages` and `label` are other strings, so the route runs the same rule by value over
// every field and answers the copy.
async function assemble() {
  if (!held.sample) return false;
  paintShipped();
  // No span handed back is no value to replace, which is what the route is told: the three `new_`
  // keys are then the edits with nothing redacted, because nothing was confirmed.
  const handed = held.handed ?? { review_text: "", claims: [], spans: [] };
  const body = { ...held.sample, ...held.edited, detected: handed };
  const answer = await call("/data-quality/personal-data/redact", body);
  if (!answer.ok) {
    sayRefusal("data-refusal", answer.detail);
    return false;
  }
  const redacted = answer.data;
  held.record = {
    ...held.sample,
    messages: held.sample.messages ?? [],
    tools: held.sample.tools ?? [],
    label: held.sample.label ?? null,
    new_messages: redacted.messages,
    // `null` where nothing made a new version of the catalog: a copy of it under a second key is
    // one more thing to keep in step. The human leaving it alone is not enough on its own --
    // `review_text` holds the catalog, so a confirmed value can sit in a tool's description and
    // the route rewrites it there. A redacted catalog *is* a new version.
    new_tools: same(held.edited.tools, held.sample.tools ?? [])
      && same(redacted.tools, held.sample.tools ?? []) ? null : redacted.tools,
    new_label: redacted.label,
    personal_data: held.handed ? { ...held.handed, ...held.replaced } : null,
    duplicate: null,
    abnormal: null,
    llm: held.review ? held.review.llm : null,
    sft: held.review ? held.review.sft : null,
    // The declared facets, and the thirteenth key. Nothing computes one and nothing can fill one
    // in afterwards, which is why they travel with the review rather than being asked for later.
    class: readDeclaredFacets()
  };
  show("record", held.record);
  return true;
}

// A refusal lands on the panel that owns it, which is the difference between *go and fix this* and
// *something went wrong somewhere*. The sentence is the service's own and is never paraphrased;
// only which panel it is put on is this page's decision.
function sayRefusal(id, detail) {
  $(id).hidden = false;
  $(id).textContent = detail;
}

// Which panel a refusal belongs to, read off the service's own words. The three refusals the spec
// names are the three this routes; anything else lands on the label panel, where the submit button
// was pressed, rather than being hidden on a panel nobody is looking at.
function whichPanel(detail) {
  const said = String(detail).toLowerCase();
  if (said.includes("personal") || said.includes("scan") || said.includes("redact")) return "data-refusal";
  return "label-refusal";
}

// **Submit** is the only thing on this page that keeps anything, and it opens the next sample in
// one motion: a reviewer who has to go and fetch the next one has been given a fourth decision.
// A refusal leaves every answer where it is and the reviewer on this sample. Nothing is retried,
// because a second post is a person pressing the button again.
async function submit() {
  if (!held.sample) return;
  frozen(true);
  hideRefusals();
  say("submit-note", "posting…");
  try {
    if (!await assemble()) return say("submit-note", "not posted", "bad");
    const where = held.key ? `/records?queue_key=${encodeURIComponent(held.key)}` : "/records";
    const answer = await call(where, held.record);
    if (!answer.ok) {
      sayRefusal(whichPanel(answer.detail), answer.detail);
      return say("submit-note", "refused — nothing was written", "bad");
    }
    // The two times are equal on a first post and apart on every one after it, which is the one
    // thing a reviewer wants to know: whether this sample had already been reviewed by somebody.
    say("submit-note", answer.data.created_time === answer.data.modified_time
      ? `stored as ${answer.data.id}`
      : `stored as ${answer.data.id} — replacing the review this sample carried before`);
    // A row was written, so the strip and the matrix are now one sample out of date. This and a
    // finished import are the only moments either of them moves.
    askStatistics();
    await askNext();
  } finally {
    // Not `frozen(false)`: this ends by opening the next sample, and the queue may have run out.
    // Unfreezing unconditionally would leave submit live over an empty screen.
    frozen(!held.sample);
  }
}

// Skipping is a state, not a deletion: the row stays, so a corpus can be asked what was passed
// over -- and a reviewer who skips is usually saying *not me, not now*, which is a fact about the
// sample and worth keeping.
async function skip() {
  if (!held.key) return;
  frozen(true);
  say("submit-note", "skipping…");
  try {
    const answer = await call(`/queue/${encodeURIComponent(held.key)}/skip`, undefined);
    if (!answer.ok) return say("submit-note", answer.detail, "bad");
    say("submit-note", "");
    left = answer.data;
    openSample(answer.data.sample, answer.data.key);
    paintStrip();
  } finally {
    frozen(!held.sample);
  }
}

// ----------------------------------------------------------------- pasting one sample straight in

// Every shape a person pastes: one object, an array of them, or one per line. Read here rather
// than sent to the import route, because **the first one is labelled without touching the queue**
// -- a queue is rows in a table, and the review has to work with the store turned off.
function readPasted(text) {
  const said = text.trim();
  if (!said) return { samples: [], broke: "nothing pasted" };
  try {
    const read = JSON.parse(said);
    if (Array.isArray(read)) {
      const bad = read.findIndex(one => !one || typeof one !== "object" || Array.isArray(one));
      if (bad !== -1) return { samples: [], broke: `item ${bad + 1} is not a sample object` };
      return { samples: read, broke: "" };
    }
    if (typeof read === "object" && read !== null) return { samples: [read], broke: "" };
    return { samples: [], broke: "that is JSON, but not a sample object" };
  } catch {
    // Not one JSON value, so try it as one per line -- which is what a few lines copied out of a
    // .jsonl file are, and the most likely thing after an object.
    const lines = said.split("\n").filter(line => line.trim());
    const samples = [];
    for (const [at, line] of lines.entries()) {
      try {
        const read = JSON.parse(line);
        if (!read || typeof read !== "object" || Array.isArray(read)) {
          return { samples: [], broke: `line ${at + 1} is not a sample object` };
        }
        samples.push(read);
      } catch (error) {
        return { samples: [], broke: `line ${at + 1} is not JSON: ${error.message}` };
      }
    }
    return { samples, broke: "" };
  }
}

// Labelled where it is, unqueued and unstored. It has no queue key, so submitting it writes the
// two tables and marks nothing done -- which is right: nothing was ever waiting.
//
// **Named first, by the service.** A raw line carries no `id` -- a corpus is `{messages, tools,
// label}` and nothing else -- and every route from here on reads a sample by name, the store's
// key most of all. The name is asked for rather than made up here: it is the content's, the same
// one an import gives, so pasting a sample the corpus already holds lands on that row instead of
// writing a second copy of it. A key computed in the browser would be a second definition of one.
//
// The naming route opens no database, which is what keeps this path working with the store off.
async function labelPasted() {
  const { samples, broke } = readPasted($("paste-text").value);
  if (broke) return say("paste-note", broke, "bad");
  say("paste-note", "reading…");
  const answer = await ask("/samples/named", {
    method: "POST",
    headers: { "Content-Type": "application/x-ndjson" },
    body: samples.map(one => JSON.stringify(one)).join("\n")
  });
  if (!answer.ok) return say("paste-note", answer.detail, "bad");
  const named = answer.data.samples || [];
  if (!named.length) return say("paste-note", "nothing in that was a sample", "bad");
  say("paste-note", named.length > 1
    ? `${named.length} read — opening the first; add them to the queue to walk the rest`
    : "read as one sample");
  walking = [];
  left = null;
  openSample(named[0], null);
  paintStrip();
  showPasting(false);
}

// The same lines the import route takes, so a paste and a file become rows the same way and the
// same key makes the same row: pasting a sample the queue already holds adds nothing.
async function queuePasted() {
  const { samples, broke } = readPasted($("paste-text").value);
  if (broke) return say("paste-note", broke, "bad");
  say("paste-note", "adding…");
  await sendLines(samples.map(one => JSON.stringify(one)).join("\n"), "paste-note");
}

// --------------------------------------------------------------------------- import

let chosen = null;

function tookFile(file) {
  chosen = file;
  $("drop-said").textContent = file ? `${file.name} — ${file.size} bytes` : "Drop a file here, or choose one";
  $("import-run").disabled = !file;
  say("import-note", "");
}

async function runImport() {
  if (!chosen) return;
  $("import-run").disabled = true;
  say("import-note", "reading…");
  try {
    await sendLines(await chosen.text(), "import-note");
  } finally {
    $("import-run").disabled = !chosen;
  }
}

// One JSON object per line, whether it came from a file or a textarea.
async function sendLines(text, noteId) {
  const answer = await ask("/queue/import", {
    method: "POST",
    headers: { "Content-Type": "application/x-ndjson" },
    body: text
  });
  if (!answer.ok) {
    say(noteId, answer.detail, "bad");
    return;
  }
  say(noteId, "");
  const came = answer.data;
  $("import-said").innerHTML = '<div class="figs">'
    + `<div><b>${esc(came.read)}</b> ${wordFor(came.read, "line", "lines")} read</div>`
    + `<div><b>${esc(came.imported)}</b> now waiting</div>`
    + `<div><b>${esc(came.already_held)}</b> already held</div></div>`
    + (came.unreadable.length
      ? `<p class="refusal">${esc(came.unreadable.length)} `
        + `${wordFor(came.unreadable.length, "line was", "lines were")} not a JSON object and `
        + `${wordFor(came.unreadable.length, "was", "were")} left out — `
        + `${wordFor(came.unreadable.length, "line", "lines")} ${esc(came.unreadable.join(", "))}. `
        + "Everything else imported.</p>"
      : "");
  askStatistics();
  // Only where the reviewer has nothing in front of them: adding while a sample is open must not
  // take that sample off the screen half-labelled.
  if (!held.sample) await askNext();
  else if (left) paintStrip();
}

// --------------------------------------------------------------- the list a reviewer picks from

// Which rows are ticked. Kept across a redraw of the list, because a reviewer who ticks twelve
// samples and then re-opens the sheet has not changed their mind.
const picked = new Set();
let listed = [];

const STATE_SAID = { waiting: "", done: "labelled", skipped: "skipped" };

async function askList() {
  const answer = await ask("/queue", {});
  if (!answer.ok) {
    listed = [];
    $("list-rows").innerHTML = `<div class="empty">${esc(answer.detail)}</div>`;
    return say("list-note", "");
  }
  listed = answer.data.samples || [];
  say("list-note", `${listed.length} of ${answer.data.waiting + answer.data.done + answer.data.skipped}`);
  paintList();
}

function paintList() {
  if (!listed.length) {
    $("list-rows").innerHTML = '<div class="empty">The queue is empty. Add a file or paste a sample.</div>';
    return pickedChanged();
  }
  $("list-rows").innerHTML = listed.map(row =>
    `<div class="row ${esc(row.state)}${row.key === held.key ? " here" : ""}">`
    + `<label class="tick"><input type="checkbox" data-pick="${esc(row.key)}"`
    + `${picked.has(row.key) ? " checked" : ""}></label>`
    + `<button class="open" data-open="${esc(row.key)}">`
    + `<span class="at">${esc(row.arrived)}</span>`
    + `<span class="said">${esc(row.said) || "<i>no turns</i>"}</span>`
    + `<span class="was">${esc(STATE_SAID[row.state] || row.state)}</span>`
    + "</button></div>").join("");
  pickedChanged();
}

function pickedChanged() {
  $("list-walk").disabled = picked.size === 0;
  $("list-none").disabled = picked.size === 0;
  $("list-walk").textContent = picked.size
    ? `Label the ${picked.size} selected`
    : "Label the selected";
}

// The ticked rows become the walk, in the order the list showed them — which is the order they
// arrived, not the order they were ticked: a reviewer picking rows out of a list is picking a
// subset, not an ordering.
async function walkPicked() {
  walking = listed.filter(row => picked.has(row.key)).map(row => row.key);
  if (!walking.length) return;
  shutSheet("sheet-list");
  say("submit-note", "");
  await askNext();
}

async function openPicked(key) {
  shutSheet("sheet-list");
  walking = [];
  const answer = await ask(`/queue/${encodeURIComponent(key)}`, {});
  if (!answer.ok) return say("submit-note", answer.detail, "bad");
  say("submit-note", "");
  left = answer.data;
  openSample(answer.data.sample, answer.data.key);
  paintStrip();
}

// --------------------------------------------------------------------------- the sheets

const openSheet = id => { $(id).hidden = false; };
const shutSheet = id => { $(id).hidden = true; };

// ------------------------------------------------------------- what the corpus already holds

// Asked on load, after a record is written and after an import. **Not on a timer**, because a
// distribution that moved while nobody was looking is a distribution nobody read.
let counted = null;

// Which database a record lands in. Asked once, on load: a deployment does not change its DSN
// while somebody is labelling, and a page that asked again every sample would be asking a question
// nothing had answered differently.
async function askStore() {
  const answer = await ask("/store", {});
  if (!answer.ok) {
    $("store").className = "store none";
    $("store").textContent = "";
    return;
  }
  const said = answer.data;
  // A 200 that is not this shape claims nothing. Better an indicator that is not there than one
  // saying `no database — set undefined`, which is a sentence about the page and not the store.
  if (!said || typeof said !== "object" || typeof said.attached !== "boolean") {
    $("store").className = "store";
    $("store").textContent = "";
    return;
  }
  $("store").className = said.attached ? "store" : "store none";
  $("store").textContent = said.attached
    ? said.describes
    : `no database — set ${said.variable}`;
  $("store").title = said.attached
    ? `records land in ${said.describes}`
    : "the review works with nothing attached; nothing will be stored";
}

async function askStatistics() {
  const answer = await ask("/records/stats", {});
  if (!answer.ok) return sayNoStatistics(answer.detail);
  // **A 200 is not on its own an answer.** A body that is not the shape this page reads would
  // throw half way through painting, and the strip, never written, would go on saying the request
  // is still in flight.
  counted = answer.data;
  try {
    // A domain the rows already carry is one this page offers, which is what makes *add a domain*
    // outlast the tab it was typed in.
    paintDomainTicks();
    paintStrip();
    paintStatistics();
  } catch (error) {
    sayNoStatistics(`the statistics came back unreadable: ${error}`);
  }
}

function sayNoStatistics(said) {
  counted = null;
  $("strip").className = "strip none";
  $("strip").textContent = said;
  $("stats").innerHTML = '<div class="lab">What the corpus holds</div>'
    + `<div class="note">${esc(said)}</div>`;
}

// The empty cells are counted over **the page's own tick lists**, not over the grid's axes: a cell
// is empty because nobody has labelled a sample of that kind, and a value nobody has used yet does
// not appear in the grid at all. Counting over what came back would report zero empty cells for a
// corpus of one sample.
function listEmptyCells(grid) {
  const empty = [];
  for (const domain of facetValues("domain")) {
    for (const trigger of facetValues("call_trigger")) {
      if (!((grid[domain] || {})[trigger])) empty.push([domain, trigger]);
    }
  }
  return empty;
}

const offList = (facet, value) => !facetValues(facet).includes(value);

// The matrix is drawn over the **union** of the two: the page's list, so a value nobody has used
// is a visible row of noughts, and the grid's own, so a value the corpus holds and this page no
// longer offers cannot go missing. An off-list one is struck through rather than dropped.
function buildMatrixTable(grid) {
  const rows = [...new Set([...facetValues("domain"), ...Object.keys(grid)])];
  const columns = [...new Set([
    ...facetValues("call_trigger"),
    ...Object.values(grid).flatMap(row => Object.keys(row))
  ])];
  const head = columns.map(column =>
    `<th class="axis${offList("call_trigger", column) ? " gone" : ""}">${esc(column)}</th>`).join("");
  const body = rows.map(row => {
    const cells = columns.map(column => {
      const number = (grid[row] || {})[column] || 0;
      return `<td class="cell${number ? "" : " zero"}">${esc(number)}</td>`;
    }).join("");
    return `<tr><th class="axis${offList("domain", row) ? " gone" : ""}">${esc(row)}</th>${cells}</tr>`;
  }).join("");
  return '<div class="tablewrap"><table class="matrix">'
    + `<thead><tr><th class="axis"></th>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

// Three numbers, read sideways while the reviewer is working on something else. The third is the
// one that changes what they do next: a total is a number to feel good about, and an empty cell is
// a job.
function paintStrip() {
  const bits = [];
  if (left) {
    bits.push(`<b>${esc(left.waiting)}</b> waiting`);
    if (left.done) bits.push(`<b>${esc(left.done)}</b> done`);
    if (left.skipped) bits.push(`<b>${esc(left.skipped)}</b> skipped`);
  }
  if (counted) {
    const totals = Object.values(counted.sample_totals || {});
    const stored = totals.length ? Math.min(...totals) : 0;
    bits.push(`<b>${esc(stored)}</b> ${wordFor(stored, "row", "rows")} stored`
      + (new Set(totals).size > 1 ? " — the two tables disagree" : ""));
    const grid = counted.counted_distribution_by_domain_and_call_trigger || {};
    const empty = listEmptyCells(grid).length;
    const cells = facetValues("domain").length * facetValues("call_trigger").length;
    bits.push(`<b>${esc(empty)}</b> of ${esc(cells)} cells still empty`);
  }
  $("strip").className = "strip";
  $("strip").innerHTML = bits.join("");
}

function paintStatistics() {
  const grid = counted.counted_distribution_by_domain_and_call_trigger || {};
  const label = counted.label_summary || {};
  const calls = counted.tool_call_counts || {};
  const groups = counted.duplicate_groups || {};
  const empty = listEmptyCells(grid);
  const byFacet = counted.counted_distribution_by_facet || {};
  $("stats").innerHTML = '<div class="lab">What the corpus holds</div>'
    + '<div class="lab">Domain against call trigger</div>'
    + buildMatrixTable(grid)
    + (empty.length
      ? `<p class="note">Still empty: ${esc(empty.map(([a, b]) => `${a} × ${b}`).join(", "))}.</p>`
      : '<p class="note">Every cell has at least one sample.</p>')
    + '<div class="lab">The labels</div>'
    + '<div class="figs">'
    + `<div><b>${esc(label.total ?? 0)}</b> ${wordFor(label.total ?? 0, "row", "rows")}</div>`
    + `<div><b>${esc(label.number_not_null_label ?? 0)}</b> answered with a call</div>`
    + `<div><b>${esc(label.number_diff_label ?? 0)}</b> distinct ${wordFor(label.number_diff_label ?? 0, "answer", "answers")}</div>`
    + `<div><b>${esc(counted.number_tools_offered ?? 0)}</b> ${wordFor(counted.number_tools_offered ?? 0, "tool", "tools")} the catalogs put in front of the model</div>`
    + '</div>'
    + '<div class="lab">Tools called</div>'
    + (Object.keys(calls).length
      ? '<div class="tablewrap"><table class="counts"><tbody>'
        + Object.entries(calls).map(([name, number]) =>
          `<tr><td>${esc(name)}</td><td>${esc(number)}</td></tr>`).join("")
        + '</tbody></table></div>'
      : '<p class="note">No stored sample calls a tool yet.</p>')
    + '<div class="lab">The same input twice</div>'
    + '<div class="figs">'
    + `<div><b>${esc((groups.same_label || []).length)}</b> ${wordFor((groups.same_label || []).length, "group", "groups")} agreeing</div>`
    + `<div><b>${esc((groups.diff_label || []).length)}</b> ${wordFor((groups.diff_label || []).length, "group", "groups")} disagreeing</div>`
    + '</div>'
    + Object.entries(byFacet).map(([facet, values]) =>
      `<div class="lab">${esc(facet)}</div>`
      + '<div class="tablewrap"><table class="counts"><tbody>'
      + (Object.keys(values).length
        ? Object.entries(values).map(([value, number]) =>
          `<tr><td>${esc(value)}</td><td>${esc(number)}</td></tr>`).join("")
        : '<tr><td class="note">nothing stored</td><td></td></tr>')
      + '</tbody></table></div>').join("");
}

// --------------------------------------------------------------------------- wiring

const typing = node => !!node && (node.isContentEditable
  || ["INPUT", "TEXTAREA", "SELECT"].includes(node.tagName));

// `Enter` submits while the focus is outside a field, and nothing else on the page is a shortcut.
// Inside a textarea it types a newline, which is what a person editing a label is doing with it.
function steer(event) {
  if (event.key === "Escape") {
    for (const id of SHEETS) shutSheet(id);
    return;
  }
  if (event.key !== "Enter") return;
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
  if (typing(event.target)) return;
  if ($("submit").disabled) return;
  event.preventDefault();
  submit();
}

paintGuideFacets();
paintFacetTicks();
paintChecks();

$("run-checks").onclick = runChecks;
$("submit").onclick = submit;
$("skip").onclick = skip;
$("span-check").onclick = checkSpans;
$("span-add").onclick = addSpan;
$("label-check").onclick = paintShipped;

const SHEETS = ["sheet-guide", "sheet-import", "sheet-list"];

$("open-guide").onclick = () => openSheet("sheet-guide");
$("open-import").onclick = () => openSheet("sheet-import");
$("open-list").onclick = () => { openSheet("sheet-list"); askList(); };
for (const button of document.querySelectorAll("[data-close]")) {
  button.onclick = () => shutSheet(button.dataset.close);
}
for (const id of SHEETS) {
  // The backdrop closes; the box does not, so a click that lands inside the sheet stays open.
  $(id).onclick = event => { if (event.target === $(id)) shutSheet(id); };
}

$("paste-open").onclick = () => showPasting($("pasting").hidden);
$("paste-cancel").onclick = () => showPasting(false);
$("paste-now").onclick = labelPasted;
$("paste-queue").onclick = queuePasted;
$("list-walk").onclick = walkPicked;
$("list-none").onclick = () => { picked.clear(); paintList(); };
$("list-rows").onclick = event => {
  const open = event.target.closest("[data-open]");
  if (open) openPicked(open.dataset.open);
};
$("list-rows").onchange = event => {
  const tick = event.target.closest("[data-pick]");
  if (!tick) return;
  if (tick.checked) picked.add(tick.dataset.pick);
  else picked.delete(tick.dataset.pick);
  pickedChanged();
};

$("file").onchange = event => tookFile(event.target.files[0]);
$("import-run").onclick = runImport;
$("drop").ondragover = event => { event.preventDefault(); $("drop").classList.add("over"); };
$("drop").ondragleave = () => $("drop").classList.remove("over");
$("drop").ondrop = event => {
  event.preventDefault();
  $("drop").classList.remove("over");
  tookFile(event.dataTransfer.files[0]);
};

$("language").onchange = () => { forgetEverything(); if (held.sample) fillEditors(); };

$("domain-add").onclick = addDomain;
$("domain-new").onkeydown = event => {
  // Enter here adds the domain. The page-wide Enter already leaves a field alone, so without this
  // a person who typed a name and pressed Enter would have nothing happen at all.
  if (event.key !== "Enter") return;
  event.preventDefault();
  addDomain();
};

for (const id of ["v-correct", "v-modify"]) {
  $(id).onchange = () => {
    $("label-editor").hidden = !$("v-modify").checked;
    paintShipped();
  };
}

for (const id of TICK_LISTS) {
  $(id).onchange = () => {
    ticked.verifier = readTick("verifier");
    ticked.jury = [...document.querySelectorAll('input[name="jury"]:checked')].map(box => box.value);
    ticked.sft = readTick("sft") || null;
  };
}

$("span-table").oninput = () => { paintValues(); copyLater(); };
$("keep-table").onchange = event => {
  const box = event.target.closest("[data-keep]");
  if (!box) return;
  held.keeps[Number(box.dataset.keep)] = box.checked;
  copyLater();
  paintKeepTable();
};
$("auto").onchange = () => { copyLater(); paintKeepTable(); };
for (const id of ["messages-text", "tools-text", "label-text"]) $(id).oninput = () => { held.record = null; };

document.addEventListener("keydown", steer);
// A model file added to `config/model/` while this page is open. Asked on focus and not on an
// interval: a directory nobody edited is a request answering the same thing over and over.
window.addEventListener("focus", paintTicks);

paintTicks();
askStore();
askStatistics();
askNext();
