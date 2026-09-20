// The labelling UI: one fetch per route, and no rule of its own.//
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

import { ask, call } from "./wire.js";
import {
  $, chars, esc, json, marked, onKey, onReturn, readTick, same, say, sayInTicks, show, sliced,
  tickBox, ticksNamed, wordFor
} from "./screen.js";
import {
  CHECKS, COPY_AFTER, DATASET_PAGE, DECLARED_FACETS, NO_CALL, PICK_SAID, STATE_SAID, TICK_LISTS,
  checked, held, ticked
} from "./held.js";

// ---------------------------------------------------------------------------- the machine steps

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
  fillEditor();
  // Neither, because *correct* is something a person says. A page that ticks it for them has
  // answered the one question on this panel nothing else can answer.
  $("v-correct").checked = false;
  $("v-modify").checked = false;
  $("label-editor").hidden = true;
  // Asked on open and not on a tick: the warning has to be up *before* the question it is about.
  checkLabel();
  // By name, over the declaration: `domain` is drawn in its own block now, and a sweep of one
  // container would leave the previous sample's domain ticked on this one.
  for (const facet of DECLARED_FACETS) {
    for (const box of ticksNamed(`f-${facet.name}`)) box.checked = false;
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
  $("turns").innerHTML = drawTurns(turns);
}

// One conversation, drawn. Its own function because two places draw one now: the pane a reviewer
// judges a sample in, and a stored row opened out of the corpus. Two spellings would let the two
// disagree about what a turn looks like, and nothing would say so.
const drawTurns = turns => turns.map(turn => {
  const who = String(turn.role ?? "?");
  const said = typeof turn.content === "string" ? turn.content
    : turn.content == null ? "" : json(turn.content);
  const calls = turn.tool_calls ? `<div class="calls">${drawCalls(turn.tool_calls)}</div>` : "";
  return `<div class="turn ${esc(who)}"><div class="who">${esc(who)}</div>`
    + `<div class="said">${esc(said)}${calls}</div></div>`;
}).join("");

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

// **The label as it stands, drawn again whenever it changes.** It used to be painted once, when
// the sample opened, and never after -- so a reviewer who took the panel's answer, or typed a call
// into the box below, went on reading the bare name that arrived while the label about to be
// confirmed was something else entirely. A panel showing one label above a tick that confirms
// another is a panel lying about what the tick does.
//
// Three versions, and which is up is said above it: what arrived, what they are rewriting it to,
// and what ships once the redacted copy exists -- which is the one that becomes `new_label`.
function paintCalls() {
  if (!held.sample) return;
  const ships = held.settled && held.shipped;
  const label = ships
    ? held.shipped.sample.label
    : (held.edited ? held.edited.label : held.sample.label);
  $("calls-which").textContent = ships
    ? "The label as it ships — this is what is stored"
    : $("v-modify").checked
      ? "The label as you are rewriting it"
      : "The label as it arrived";
  $("calls").innerHTML = drawLabel(label);
}

// One label as the block reads it. A label is a list of calls; anything else in that box is
// something the reviewer is still typing, and saying so beats drawing `(unnamed)` at them.
function drawLabel(label) {
  if (label === null || label === undefined) return NO_CALL;
  if (!Array.isArray(label)) return '<div class="nocall">Not JSON yet — the box below says what is wrong.</div>';
  return label.length ? drawCalls(label) : NO_CALL;
}

// --------------------------------------------------------------------------- which models answer

let drawn = null;

async function paintTicks() {
  const answer = await ask("/models", {});
  if (!answer.ok) return sayInTicks(TICK_LISTS, answer.detail);
  // **The route answers a bare array of names.** Reading a `models` key off it finds `undefined`
  // on every deployment, every list draws empty, and the run stops on `tick a verifier first`
  // with nothing to tick -- which is exactly what it did. Anything else claims nothing.
  const served = Array.isArray(answer.data) ? answer.data : [];
  if (!served.length) {
    // And forgotten, so a directory that fills up again is drawn rather than matching what was
    // last drawn and being skipped.
    drawn = null;
    return sayInTicks(TICK_LISTS,
      "no model is configured: config/model/ holds none this deployment can serve");
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
  for (const box of ticksNamed("verifier")) {
    box.checked = box.value === ticked.verifier;
  }
  for (const box of ticksNamed("jury")) {
    box.checked = ticked.jury.includes(box.value);
  }
  for (const box of ticksNamed("sft")) {
    box.checked = box.value === (ticked.sft || "");
  }
}

// --------------------------------------------------------------------------- forgetting

function forgetEverything() {
  held.detected = null;
  held.rows = [];
  held.keeps = {};
  held.review = null;
  held.record = null;
  held.handed = null;
  held.shipped = null;
  held.copyNote = null;
  held.settled = false;
  held.faults = null;
  clearTimeout(copySoon);
  copyAt += 1;
  faultAt += 1;
  paintReviewText();
  paintFaults();
  paintConsensus();
  for (const id of ["span-table", "keep-table"]) $(id).querySelector("tbody").innerHTML = "";
  for (const id of ["out-6", "record"]) show(id, undefined);
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
  held.shipped = null;
  held.record = null;
  const found = held.rows.length;
  paintReviewText();
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
// replaces. The empty shape where no scan has run, because that is a real state the route takes:
// nothing was confirmed, so nothing is replaced and the record comes back as it arrived.
function handedBack() {
  if (!held.detected) return { review_text: "", claims: [], spans: [] };
  const rows = editedSpans().filter(row => !row.broke);
  return {
    review_text: held.detected.review_text,
    claims: held.detected.claims,
    spans: rows.filter(row => !dropped(row, rows)).map(({ i, value, ...span }) => span)
  };
}

// The body the copy is made from: the edits as they stand, with those spans beside them. One
// builder, because the copy on the screen and the record that is posted have to be one answer.
function shippingBody() {
  paintShipped();
  return { ...held.sample, ...held.edited, detected: handedBack() };
}

let copySoon = null;
// Which copy is the newest. An answer to an older one landing after it is dropped rather than
// painted: it is the copy of spans, or of a label, that are no longer on the screen.
let copyAt = 0;

// **Nothing here is asked for.** A span the reviewer keeps is a value that has to come out, so
// unticking one, dragging an offset, adding a row or typing in the label makes the copy wrong the
// moment it happens -- and a copy that is wrong until somebody presses a button is a copy that
// ships wrong.
function copyLater() {
  held.handed = null;
  held.shipped = null;
  held.copyNote = null;
  // **The boxes, read now and not when the timer fires.** What the label block draws has to be the
  // label on the screen this instant: a block still showing the copy that shipped before the
  // keystroke is the same lie as one still showing the name that arrived. It clears the record too.
  paintShipped();
  sayPersonalData();
  paintReviewText();
  clearTimeout(copySoon);
  copyAt += 1;
  copySoon = setTimeout(refreshBoth, COPY_AFTER);
}

// The two things a changed label makes wrong, asked on the one pause. The copy is wrong because
// the label is rendered into the text it is made of; the check is wrong because it is a check of
// that label. Neither waits on the other -- a catalog the label cannot be called against is still
// worth saying while the redaction is in flight.
function refreshBoth() {
  checkLabel();
  return refreshCopy();
}

// One call, and it answers both halves: the record with every confirmed value replaced in every
// field, and that record rendered back as one text. **There is no second route.** There was, and
// it rewrote the scan's own text instead of the record -- a copy nothing read, and an outcome
// about a text rather than about what ships.
async function refreshCopy() {
  if (!held.sample) return false;
  if (held.detected && editedSpans().some(row => row.broke)) {
    return copyBroke("a span row is unreadable, so nothing was replaced");
  }
  const body = shippingBody();
  const mine = (copyAt += 1);
  const answer = await call("/data-quality/personal-data/redact", body);
  if (mine !== copyAt) return false;
  if (!answer.ok) return copyBroke(answer.detail);
  held.handed = body.detected;
  held.shipped = answer.data;
  held.copyNote = null;
  sayPersonalData();
  paintReviewText();
  paintCalls();
  composeRecord();
  return true;
}

// A copy that could not be made, said in the two places a reviewer might be looking: the scan's
// own row, and the text itself where the copy that ships was waiting to appear.
function copyBroke(why) {
  mark(2, "bad", why);
  held.copyNote = why;
  paintReviewText();
  return false;
}

// One line for the scan and the copy together, because they are one act. What the scan found is a
// number the reviewer is about to change, and what came out is the consequence of their ticking.
function sayPersonalData() {
  if (!held.detected) return;
  const found = held.rows.length;
  const scan = found ? `${found} ${wordFor(found, "span", "spans")} found` : "nothing found";
  if (!held.shipped) return mark(2, "wait", `${scan} · replacing…`);
  const kept = held.handed.spans.length;
  mark(2, "answered", `${scan} · ${kept
    ? `${kept} ${wordFor(kept, "value", "values")} replaced`
    : "nothing to replace"}`);
}

// ------------------------------------------------------------------ the text, as a text

// The sample as one string, which is the only thing on this panel a person reads rather than
// operates. Not JSON: what a route answered is keyed, escaped and wrapped in an envelope, and a
// conversation shown that way is one the reviewer has to decode before they can judge it. Its own
// line breaks are line breaks here.
//
// Two versions, and which is up is the whole of the state:
//
//   *the text the scan reads* — what the offsets index, until the label is settled;
//   *the text as it ships*    — the record after redaction, rendered again.
//
// The copy is *made* as the reviewer ticks, because the scan's own row reports on it. It is not
// *shown* until they have said what the label is, and cannot be: **the label is rendered into this
// text**, so a copy put up while they are still deciding is a copy of a label about to change.
// Once they have said, it answers the question the panel above asks — the number in the turn and
// the number in the call carry the same placeholder, one screen apart.
function paintReviewText() {
  const which = $("text-which");
  const shown = $("review-text");
  if (held.settled && held.shipped) {
    which.textContent = "The text as it ships — every value you kept replaced, the label with it";
    shown.textContent = held.shipped.review_text;
  } else if (held.settled && held.copyNote) {
    which.textContent = "The text as it ships";
    shown.textContent = held.copyNote;
  } else if (held.settled) {
    which.textContent = "The text as it ships";
    shown.textContent = "replacing…";
  } else if (held.detected) {
    which.textContent = "The text the scan read";
    shown.textContent = held.detected.review_text;
  } else {
    which.textContent = "The text the scan reads";
    shown.textContent = "Nothing has been read for personal data yet.";
  }
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
  paintConsensus();
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

function fillEditor() {
  if (!held.sample) return;
  $("label-text").value = json(held.sample.label ?? null);
  paintShipped();
}

// A box the human did not open reads back what was in it, so `correct` and an untouched editor
// agree. Something that is not JSON is carried as `{unparsed: <text>}` -- never dropped, never
// guessed at.
function typedLabel() {
  const arrived = held.sample.label ?? null;
  if (!$("v-modify").checked) return arrived;
  try { return JSON.parse($("label-text").value); } catch { return { unparsed: $("label-text").value }; }
}

// **The three as they ship before redaction -- but only one of them is the reviewer's.** The
// turns are what a customer said and the catalog is what the assistant was offered; a page that
// let either be retyped is a page that can make the sample agree with the label instead of the
// other way round. They still ship under `new_`, because redaction rewrites them, and a value
// coming out is not a reviewer rewriting one.
function paintShipped() {
  if (!held.sample) return;
  held.edited = {
    messages: held.sample.messages ?? [],
    tools: held.sample.tools ?? [],
    label: typedLabel()
  };
  const unparsed = held.edited.label && held.edited.label.unparsed !== undefined;
  say("label-note", unparsed
    ? "not JSON, carried as {unparsed: …}"
    : "re-parsed as a label", unparsed ? "bad" : "");
  held.record = null;
  paintCalls();
}

// ------------------------------------------------------- is the label one the catalog can take

// **The store's own rule, asked before the row is written rather than read off one afterwards.**
// `schema_valid` is computed at write time from the label and the catalog, so a label naming a
// tool without calling it -- `["VerifyEmail_15d"]`, which is a name and not a call -- was found
// days later by somebody reading the corpus, and the person who ticked *correct* on it was never
// told a thing. This is that same function over those same two fields, asked while they are still
// looking at the sample.
//
// A warning and never a gate. What the label ought to be is the reviewer's to say, and a page
// that refused to submit would be deciding it for them; it says what is wrong and leaves the
// button alone.

let faultAt = 0;

async function checkLabel() {
  if (!held.sample) return false;
  const mine = (faultAt += 1);
  // The label as it stands this instant: what the editor holds where they are rewriting it, and
  // what arrived where they are not. `held.edited` is `paintShipped`'s, so the label checked and
  // the label redacted are one label.
  const answer = await call("/data-quality/label", { ...held.sample, ...(held.edited || {}) });
  if (mine !== faultAt) return false;
  held.faults = answer.ok ? answer.data : null;
  if (!answer.ok) return sayNoCheck(answer.detail);
  paintFaults();
  return true;
}

// A check that could not be made is not a label that passed. Said where the faults would have
// been, because that is where somebody is looking for them.
function sayNoCheck(why) {
  const said = $("label-fault");
  said.hidden = false;
  said.textContent = `the label could not be checked against the catalog: ${why}`;
  return false;
}

// The service's own sentences, one per broken call, never reworded here: a page that put the
// fault in its own words would be a second opinion about what a callable label is.
function paintFaults() {
  const said = $("label-fault");
  const broken = held.faults && !held.faults.schema_valid;
  said.hidden = !broken;
  said.innerHTML = broken
    ? "<b>Nothing here can validate this label against the catalog.</b><ul>"
      + held.faults.faults.map(one => `<li>${esc(one)}</li>`).join("")
      + "</ul>"
    : "";
}

// ------------------------------------------------------------------ what the panel would write

// The jury's answer was on the screen already, as JSON in a disclosure. A reviewer who agreed
// with it had to retype the whole call by hand into the box below -- which is how a label that
// two models had spelled out in full shipped as a bare name.
function paintConsensus() {
  const offered = agreedLabel() !== "";
  $("consensus-line").hidden = !offered;
  if (offered) say("consensus-note", "the one label the panel agreed on, into the box below");
}

// What the panel came to, or `""` where there is nothing to take. Read in one place, because the
// line that offers it and the button that takes it have to agree about whether there is one. A
// panel nobody agreed with still answered something somebody can start from, so the only question
// asked here is whether there is text.
const agreedLabel = () => {
  const agreed = ((held.review || {}).llm || {}).consensus;
  return typeof agreed === "string" ? agreed.trim() : "";
};

// Taken verbatim, and laid out only if it parses: it is the text a juror wrote, and this page
// re-spelling a call would be the page deciding what a call looks like. Text that will not parse
// goes in as it stands and *Check it is JSON* says so -- the same thing that happens to anything
// else typed in there.
function takeConsensus() {
  const agreed = agreedLabel();
  if (!agreed) return false;
  let laid = agreed;
  try { laid = json(JSON.parse(agreed)); } catch { laid = agreed; }
  $("label-text").value = laid;
  // Pressing this *is* saying the label is being rewritten, so it ticks and opens for them: a
  // button that filled a hidden box would have done nothing anybody could see.
  $("v-modify").checked = true;
  $("v-correct").checked = false;
  $("label-editor").hidden = false;
  held.settled = true;
  copyLater();
  return true;
}

// ------------------------------------------------------------------ the facets a person ticks

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
  for (const box of ticksNamed("f-domain")) {
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
  // Ticked in code, which fires no `change`: the record would otherwise still say the facet is
  // unanswered while the screen shows it ticked.
  composeRecord();
  $("domain-new").value = "";
  say("domain-note", `${said} added and ticked — it stays offered once a sample carries it`);
}

// What the record carries under `class`: the declared facets and nothing else. A facet nobody
// ticked is left out rather than sent as null -- the route names it by name, which reads as a
// facet to go and tick rather than as a column that refused a value.
function readDeclaredFacets() {
  const answered = { language: $("language").value };
  for (const facet of DECLARED_FACETS) {
    const boxes = ticksNamed(`f-${facet.name}`);
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
//
// **Composed as the reviewer works, not at the moment of posting.** The box below it says *the
// record this page will post*, and it held nothing until the post had been made -- after which
// the next sample opened and wiped it, so the one thing it promised to show was the one thing it
// never showed. Nothing made that necessary: the copy it is built from is already remade on every
// tick, so this is remade with it.
function composeRecord() {
  if (!held.sample || !held.shipped) return;
  const redacted = held.shipped.sample;
  held.record = {
    ...held.sample,
    messages: held.sample.messages ?? [],
    tools: held.sample.tools ?? [],
    label: held.sample.label ?? null,
    new_messages: redacted.messages,
    // `null` where nothing made a new version of the catalog: a copy of it under a second key is
    // one more thing to keep in step. Nobody can retype the catalog here, so redaction is the
    // only thing that ever makes a new version of it -- `review_text` holds the catalog, a
    // confirmed value can sit in a tool's description, and the route rewrites it there.
    new_tools: same(redacted.tools, held.sample.tools ?? []) ? null : redacted.tools,
    new_label: redacted.label,
    // `null` is nobody having scanned it, which is the first refusal the store names. The
    // outcome rides with the spans because it is the one thing about the rewrite the spans do
    // not say -- and it is measured over what ships, not over a second copy of the scan's text.
    personal_data: held.detected ? { ...held.handed, outcome: held.shipped.outcome } : null,
    duplicate: null,
    abnormal: null,
    llm: held.review ? held.review.llm : null,
    sft: held.review ? held.review.sft : null,
    // The declared facets, and the thirteenth key. Nothing computes one and nothing can fill one
    // in afterwards, which is why they travel with the review rather than being asked for later.
    class: readDeclaredFacets()
  };
  show("record", held.record);
}

async function assemble() {
  if (!held.sample) return false;
  // The copy, made once more and now rather than on a timer: what is posted has to be the record
  // as it reads this instant, not as it read before the last keystroke.
  clearTimeout(copySoon);
  paintShipped();
  checkLabel();
  if (!await refreshCopy()) {
    sayRefusal("data-refusal", held.copyNote || "the copy that ships could not be made");
    return false;
  }
  return held.record !== null;
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

// ------------------------------------------------------------------ what is already stored

// The corpus read back, which is the one thing this page could not do: the queue says what is
// *waiting*, the statistics say what the whole comes to, and between them a row somebody wrote
// was not readable anywhere. A sample pasted straight in never had a queue row at all, so it was
// invisible the moment it was stored.
//
// **The redacted table, because that is the route's own answer.** Nothing here chooses that --
// `/records` serves `tool_decision_dataset` and there is no route to the other one.
let stored = [];
let storedTotal = 0;
let storedShown = 0;

async function askDataset(more) {
  storedShown = more ? storedShown + DATASET_PAGE : 0;
  if (!more) stored = [];
  say("dataset-note", "reading…");
  const answer = await ask(`/records?limit=${DATASET_PAGE}&offset=${storedShown}`);
  if (!answer.ok) return say("dataset-note", answer.detail, "bad");
  stored = [...stored, ...(answer.data.samples || [])];
  storedTotal = answer.data.total || 0;
  $("dataset-one").innerHTML = "";
  paintDataset();
}

function paintDataset() {
  const only = $("dataset-bad").checked;
  const rows = only ? stored.filter(row => !row.schema_valid) : stored;
  say("dataset-note", `${rows.length} of ${storedTotal} ${wordFor(storedTotal, "row", "rows")}`);
  $("dataset-more").disabled = stored.length >= storedTotal;
  const body = $("dataset-rows").querySelector("tbody");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="8" class="empty">${
      only ? "Every stored row validates against its catalog." : "Nothing is stored yet."
    }</td></tr>`;
    return;
  }
  body.innerHTML = rows.map(row => `<tr class="${row.schema_valid ? "" : "dropped"}">
    <td><button class="open" data-stored="${esc(row.key)}">${esc(row.said) || "<i>no turns</i>"}</button></td>
    <td>${esc(row.domain)}</td>
    <td>${esc(row.ambiguous)}</td>
    <td>${esc(row.number_turns)}</td>
    <td>${esc(row.number_label_tools)}</td>
    <td>${esc(row.number_provided_tools)}</td>
    <td>${esc((row.personal_data || []).join(", ")) || "—"}</td>
    <td class="${row.schema_valid ? "ok" : "bad"}">${row.schema_valid ? "yes" : "no"}</td>
  </tr>`).join("");
}

// One row opened. The label is drawn as calls rather than as JSON for the same reason the sample
// pane draws the conversation: what somebody is checking is whether the calls fit the turns.
async function openStored(key) {
  say("dataset-note", "reading…");
  const answer = await ask(`/records/${encodeURIComponent(key)}`);
  if (!answer.ok) return say("dataset-note", answer.detail, "bad");
  const one = answer.data;
  const valid = one.facets.schema_valid;
  say("dataset-note", `#${key}`);
  $("dataset-one").innerHTML = `<div class="storedone">`
    + `<div class="lab">Label as it ships</div>`
    + `<div class="calls">${drawCalls(one.label || [])}</div>`
    + (valid ? "" : `<p class="refusal">Nothing could validate this label against the catalog`
      + ` — a call names a tool that was never offered, or leaves out an argument it requires.</p>`)
    + `<div class="lab">The conversation</div>`
    + `<div class="turns">${drawTurns(one.input.messages || [])}</div>`
    + `</div>`;
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

const SHEETS = ["sheet-guide", "sheet-import", "sheet-list", "sheet-dataset"];

$("open-guide").onclick = () => openSheet("sheet-guide");
$("open-import").onclick = () => openSheet("sheet-import");
$("open-list").onclick = () => { openSheet("sheet-list"); askList(); };
$("open-dataset").onclick = () => { openSheet("sheet-dataset"); askDataset(false); };
$("dataset-more").onclick = () => askDataset(true);
$("dataset-bad").onchange = paintDataset;
$("dataset-rows").onclick = event => {
  const open = event.target.closest("[data-stored]");
  if (open) openStored(open.dataset.stored);
};
for (const button of marked("close")) {
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

$("language").onchange = () => { forgetEverything(); if (held.sample) fillEditor(); };

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
    // Saying what the label is, is what makes the shipping copy possible: the label is rendered
    // into the text, so there is nothing to redact until it is settled.
    held.settled = $("v-correct").checked || $("v-modify").checked;
    paintShipped();
    // Not a new call on its own: the copy already follows the ticking. What saying this changes
    // is that the reviewer may now *see* it, and that the label it is made from is settled.
    copyLater();
  };
}

for (const id of TICK_LISTS) {
  $(id).onchange = () => {
    ticked.verifier = readTick("verifier");
    ticked.jury = ticksNamed("jury").filter(box => box.checked).map(box => box.value);
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
// A facet is the one part of the record nothing computes, so ticking one is the only edit that
// reaches it without going through the copy. `change` on the container, because the boxes inside
// are redrawn whenever the corpus answers with a value nobody had offered yet.
for (const id of ["facet-ticks", "domain-ticks"]) $(id).onchange = composeRecord;
// Typing in a label the reviewer is rewriting makes the copy wrong the moment it happens, the
// same way moving a span does. So it goes, and comes back once they stop.
$("label-text").oninput = copyLater;
$("take-consensus").onclick = takeConsensus;

onKey(steer);
// A model file added to `config/model/` while this page is open. Asked on focus and not on an
// interval: a directory nobody edited is a request answering the same thing over and over.
onReturn(paintTicks);

paintTicks();
askStore();
askStatistics();
askNext();
