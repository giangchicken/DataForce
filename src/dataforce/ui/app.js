// The labelling UI: one fetch per route, and no rule of its own.
//
// Every rectangle shows what a route answered. The spans, the copy, the outcome, the votes, the
// consensus and the redaction are fields read off a response -- nothing here computes one, because
// a client that disagreed with the service about what a span or a vote is would be a second
// definition of it. The one thing this page composes is the record at step 8, because nothing else
// composes one.

const API = "/text2text/tool-decision";

// --------------------------------------------------------------------------- plumbing

const $ = id => document.getElementById(id);
const json = v => JSON.stringify(v, null, 2);
// Every interpolation into markup goes through this. What a span reads is a value out of the
// sample, and a corpus that says `<b>` is a corpus, not an instruction.
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

// Offsets are code points, because that is what slicing `review_text` in Python counts. A browser
// indexes UTF-16 units, so `text.slice(start, end)` reads a different string from the same two
// numbers the moment something outside the BMP is in the text.
const chars = text => Array.from(text);
const sliced = (text, start, end) => chars(text).slice(start, end).join("");

// One POST, and one reading of what came back. A refusal is the service's own `detail`, never
// paraphrased and never retried: a second call is a person pressing the button again.
async function call(path, body) {
  let resp;
  try {
    resp = await fetch(API + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  } catch (error) {
    return { ok: false, detail: `no answer from the service: ${error}` };
  }
  const text = await resp.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (resp.ok) return { ok: true, data };
  const detail = data && data.detail !== undefined ? data.detail : data;
  return { ok: false, detail: `${resp.status} — ${typeof detail === "string" ? detail : json(detail)}` };
}

// The four states a rectangle can be in. `answered` carries no colour: a page mid-flow should read
// as what is left to do.
function mark(step, state, text) {
  const el = document.querySelector(`[data-state="${step}"]`);
  el.className = `state${state === "answered" ? "" : ` ${state}`}`;
  el.textContent = text;
  // Answering the rectangle you were sent back to is the end of the return. The marker is a
  // standing instruction to make the correction here, and one left on a step that has since
  // answered points at nothing.
  if (held.returned === step) {
    held.returned = null;
    paintReturn();
  }
}

function show(id, value, kind = "") {
  const el = $(id);
  el.className = `big${kind ? ` ${kind}` : ""}`;
  el.textContent = value === undefined ? "" : json(value);
}

// A rectangle that asked and was refused: the service's sentence, where it happened, and every
// answer this page already holds left standing.
function refused(step, id, detail) {
  mark(step, "bad", "refused");
  $(id).className = "big bad";
  $(id).textContent = detail;
}

// And a rectangle that could not ask at all, which is not the same thing and does not read like
// one: nothing was called, so nothing refused anything, and someone sent looking for a refusal
// would be reading a service log for a request it never received.
function cannotAsk(step, id, why) {
  mark(step, "unasked", "not asked");
  $(id).className = "big unasked";
  $(id).textContent = why;
}

// What this step was handed, written down before it is sent: the request body itself, so what a
// rectangle shows as its input is what went over the wire.
async function asking(step, body, path) {
  show(`in-${step}`, body);
  mark(step, "wait", "waiting");
  const answer = await call(path, body);
  if (!answer.ok) refused(step, `out-${step}`, answer.detail);
  return answer;
}

// --------------------------------------------------------------------------- what the page holds

const EXAMPLE = {
  id: "s4471",
  messages: [
    { role: "user", content: "Chào em, anh Trần Văn Minh, số 0912345678, mail minh0912345678@vd.vn, mở phiếu vì app lỗi." },
    { role: "assistant", content: "Dạ em mở phiếu hỗ trợ cho mình ngay ạ." }
  ],
  tools: [{
    type: "function",
    function: {
      name: "OpenTicket",
      description: "Mở phiếu hỗ trợ cho khách hàng.",
      parameters: {
        type: "object",
        required: ["ma_khach", "noi_dung"],
        properties: {
          ma_khach: { type: "string" },
          noi_dung: { type: "object", properties: { tieu_de: { type: "string" } }, required: ["tieu_de"] }
        }
      }
    }
  }],
  label: [{ name: "OpenTicket", arguments: { ma_khach: "0912345678", noi_dung: { tieu_de: "App lỗi" } } }]
};

const held = {
  sample: null,     // step 1, as `check` parsed it
  detected: null,   // step 2's answer, with the spans as they came back
  rows: [],         // the span rows as the human is editing them, added ones included
  keeps: {},        // step 5: which rows the human is handing back
  handed: null,     // step 5: the detect shape with the spans as they left it
  replaced: null,   // step 5's second answer
  review: null,     // step 6
  edited: null,     // step 7: the three, as they ship before redaction
  record: null,     // step 8
  asked: {},        // which steps answered at all, so `null` at 200 is not `not asked`
  returned: null    // which rectangle a **back to** sent the reviewer to, if any
};

const ticked = { verifier: null, jury: [], sft: null };

// --------------------------------------------------------------------------- which models answer

// The lists are `GET /models`' answer. A UI that wrote the names down would be a second
// declaration of what this deployment serves, which is what that endpoint exists to end.
const TICK_LISTS = ["verifier-ticks", "jury-ticks", "sft-ticks"];

// The list this page last drew. `config/model/` is a directory a deployment edits while the
// service is up, and `GET /models` reads it per call -- so the answer can change under a page
// that is already open, and the ticks are re-asked for rather than read once. On opening, and
// again whenever the window is focused: you add a file in an editor, come back to the tab, and
// the name is there. No interval, because polling picks a number nobody chose.
let drawn = null;

async function paintTicks() {
  let served;
  try {
    served = await (await fetch(`${API}/models`)).json();
    if (!Array.isArray(served)) throw new Error(`answered ${json(served)}`);
  } catch (error) {
    drawn = null;
    return sayInTicks(`no list of models from ${API}/models: ${esc(error)}`);
  }
  if (same(served, drawn)) return;
  drawn = served;
  if (!served.length) {
    return sayInTicks("this deployment serves no model: <b>config/model/</b> holds no file, so there is nothing to tick");
  }
  $("verifier-ticks").innerHTML = served.map(name =>
    `<label class="mode"><input type="radio" name="verifier" value="${esc(name)}"> ${esc(name)}</label>`).join("");
  $("jury-ticks").innerHTML = served.map(name =>
    `<label class="mode"><input type="checkbox" name="jury" value="${esc(name)}"> ${esc(name)}</label>`).join("");
  $("sft-ticks").innerHTML = '<label class="mode"><input type="radio" name="sft" value="" checked> none</label>'
    + served.map(name => `<label class="mode"><input type="radio" name="sft" value="${esc(name)}"> ${esc(name)}</label>`).join("");

  $("verifier-ticks").onchange = () => { ticked.verifier = readTick("verifier") || null; };
  $("sft-ticks").onchange = () => { ticked.sft = readTick("sft") || null; };
  $("jury-ticks").onchange = () => {
    ticked.jury = [...document.querySelectorAll('input[name="jury"]:checked')].map(box => box.value);
  };
  retick(served);
}

// A redrawn list must not cost the reviewer their ticks: the directory changing is news about the
// deployment, not an instruction to un-tick what they chose. A name that is no longer served is
// the one exception -- it cannot be asked for, so the tick goes and the box says which name went.
function retick(served) {
  const gone = [
    ...(ticked.verifier && !served.includes(ticked.verifier) ? [ticked.verifier] : []),
    ...(ticked.sft && !served.includes(ticked.sft) ? [ticked.sft] : []),
    ...ticked.jury.filter(name => !served.includes(name))
  ];
  if (ticked.verifier && !served.includes(ticked.verifier)) ticked.verifier = null;
  if (ticked.sft && !served.includes(ticked.sft)) ticked.sft = null;
  ticked.jury = ticked.jury.filter(name => served.includes(name));
  for (const [name, value] of [["verifier", ticked.verifier], ["sft", ticked.sft]]) {
    if (value) tickBox(name, value).checked = true;
  }
  for (const name of ticked.jury) tickBox("jury", name).checked = true;
  if (gone.length) {
    const said = `<span class="none">no longer served, so unticked: ${esc([...new Set(gone)].join(", "))}</span>`;
    TICK_LISTS.forEach(id => $(id).insertAdjacentHTML("beforeend", said));
  }
}

const tickBox = (name, value) =>
  [...document.querySelectorAll(`input[name="${name}"]`)].find(box => box.value === value);
const sayInTicks = said => TICK_LISTS.forEach(id => { $(id).innerHTML = `<span class="none">${said}</span>`; });
const readTick = name => (document.querySelector(`input[name="${name}"]:checked`) || {}).value || "";

// --------------------------------------------------------------------------- 1 · input

function checkSample() {
  const said = unreadable();
  $("sample-note").className = said ? "note bad" : "note";
  if (said) {
    held.sample = null;
    $("sample-note").textContent = said;
    mark(1, "bad", "unreadable");
    return show("out-1", undefined);
  }
  const parsed = JSON.parse($("sample-text").value);
  const fresh = !same(parsed, held.sample);
  held.sample = parsed;
  $("sample-note").textContent = `read as one sample: ${Object.keys(parsed).join(", ")}`;
  mark(1, "answered", "read");
  show("out-1", parsed);
  // A different sample makes every other rectangle's answer an answer about something else, so
  // they are cleared rather than left to be assembled into a record they are not about. The same
  // sample checked twice keeps everything, the label editor included: re-reading the box is not
  // an instruction to throw away what was typed in step 7.
  if (fresh) {
    forgetAnswers();
    fillEditors();
  }
}

function unreadable() {
  let parsed;
  try {
    parsed = JSON.parse($("sample-text").value);
  } catch (error) {
    return `that is not JSON: ${error.message}`;
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return "one sample, as an object: {id, messages, tools, label}";
  }
  return "";
}

// An answer is an answer about what it was asked with. Change that, and it is not an answer about
// what this page now holds -- so it is dropped rather than carried into a record it is not about.
// The edit rule read strictly: what the human edited is what the next call is made with,
// which means a call made before the edit is not that call.
function forget(...steps) {
  for (const step of steps) {
    delete held.asked[step];
    mark(step, "untouched", "");
    show(`in-${step}`, undefined);
    show(step === 8 ? "record" : `out-${step}`, undefined);
  }
  if (steps.includes(8)) {
    held.record = null;
    for (const id of ["assemble", "approve"]) $(id).disabled = false;
    $("approve-note").className = "note";
    $("approve-note").textContent = "";
  }
}

// The spans moved, so the copy made over the old ones is not the copy of these. Pressing
// **replace** again is what makes it one, and until then step 5 has not answered.
function forgetTheCopy() {
  held.handed = null;
  held.replaced = null;
  forget(5, 8);
}

// The sample or the language changed, so both model steps were asked about something else.
function forgetTheAnswers() {
  held.detected = null;
  held.rows = [];
  held.keeps = {};
  held.review = null;
  for (const id of ["span-table", "keep-table"]) $(id).querySelector("tbody").innerHTML = "";
  $("span-note").textContent = "";
  forget(2, 6);
  forgetTheCopy();
}

function forgetAnswers() {
  forgetTheAnswers();
  forget(3, 4);
}

// --------------------------------------------------------------------------- 2 · personal data

async function detect() {
  if (!held.sample) return cannotAsk(2, "out-2", "check the sample first: step 2 is asked about it");
  if (!ticked.verifier) return cannotAsk(2, "out-2", "tick a verifier: one model confirms each span the detectors claim");
  const answer = await asking(2, {
    ...held.sample, language: $("language").value, verifier_model: ticked.verifier
  }, "/data-quality/personal-data");
  if (!answer.ok) return;
  held.detected = answer.data;
  held.rows = answer.data.spans.map(span => ({ ...span }));
  held.keeps = {};
  forgetTheCopy();
  held.asked[2] = true;
  mark(2, "answered", "detected");
  show("out-2", answer.data);
  paintSpanTable();
  paintKeepTable();
}

function paintSpanTable() {
  $("span-table").querySelector("tbody").innerHTML = held.rows.map((span, i) => `
    <tr>
      <td>${span.id}</td>
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
      if (!/^\d+$/.test(value.trim())) return { i, broke: `row ${i + 1}: ${field} is not a whole number` };
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
  $("span-note").className = broke.length ? "note bad" : "note";
  $("span-note").textContent = broke.length
    ? `${broke.map(row => row.broke).join("; ")} — nothing was called`
    : "every row re-sliced";
  const edited = !broke.length && !same(comparable(rows), comparable(held.detected.spans));
  if (broke.length) mark(2, "bad", "unreadable");
  else mark(2, edited ? "edited" : "answered", edited ? "edited" : "detected");
  if (!broke.length) {
    held.rows = rows.map(({ i, value, ...span }) => span);
    if (edited) forgetTheCopy();
    paintKeepTable();
  }
}

// A row the reviewer added. Numbered after the last, because `id` is 1-based in span order and is
// what the confirmation was asked about -- and nothing asks it again about a span it never saw.
function addSpan() {
  if (!held.detected) return cannotAsk(2, "out-2", "step 2 has not answered: there is no text for a span to index");
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
  $("span-note").className = "note";
  $("span-note").textContent = "a row added: type its offsets, then check";
}

// --------------------------------------------------------------------------- 3, 4 · null at 200

async function reportNothing(step, path) {
  if (!held.sample) return cannotAsk(step, `out-${step}`, "check the sample first: this step is asked about it");
  const answer = await asking(step, held.sample, path);
  if (!answer.ok) return;
  held.asked[step] = true;
  mark(step, "answered", "asked");
  // `null` at 200 is *nothing to report*, not a step that failed: nothing declares what either of
  // these reports, so there is no shape for one to come back in.
  $(`out-${step}`).className = "big nul";
  $(`out-${step}`).textContent = `${json(answer.data)} — nothing to report`;
}

// --------------------------------------------------------------- 5 · human check · data quality

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
  show("in-5", handedBack());
}

// The spans as the human left them: what step 5 hands back, and the only spans anything replaces.
function handedBack() {
  const rows = editedSpans().filter(row => !row.broke);
  return {
    review_text: held.detected.review_text,
    claims: held.detected.claims,
    spans: rows.filter(row => !dropped(row, rows)).map(({ i, value, ...span }) => span)
  };
}

async function replace() {
  if (!held.detected) return cannotAsk(5, "out-5", "step 2 has not answered: there are no spans to hand back");
  if (editedSpans().some(row => row.broke)) {
    return cannotAsk(5, "out-5", "a span row is unreadable — fix it in step 2 and check");
  }
  const handed = handedBack();
  const answer = await asking(5, handed, "/data-quality/personal-data/replace");
  if (!answer.ok) return;
  held.handed = handed;
  held.replaced = answer.data;
  held.asked[5] = true;
  const unchanged = same(comparable(handed.spans), comparable(held.detected.spans));
  mark(5, unchanged ? "answered" : "edited", unchanged ? "unchanged" : "modified");
  show("out-5", answer.data);
}

// --------------------------------------------------------------------------- 6 · ai review

async function review() {
  if (!held.sample) return cannotAsk(6, "out-6", "check the sample first: the panel is asked about it");
  const answer = await asking(6, {
    ...held.sample,
    language: $("language").value,
    jury_models: ticked.jury,
    sft_model: ticked.sft
  }, "/ai-review");
  if (!answer.ok) return;
  held.review = answer.data;
  held.asked[6] = true;
  mark(6, "answered", "reviewed");
  show("out-6", answer.data);
}

// --------------------------------------------------------------------------- 7 · human check

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
  $("label-note").className = unparsed.length ? "note bad" : "note";
  $("label-note").textContent = unparsed.length
    ? `${unparsed.join(", ")}: not JSON, carried as {unparsed: …}`
    : "all three re-parsed";
  const modified = !same(held.edited, arrived);
  mark(7, modified ? "edited" : "answered", modified ? "modified" : "as it arrived");
  show("out-7", held.edited);
}

// Step 7 answers without calling anything, so its **check** is the whole of the human step -- and
// a record assembled before it was pressed is a record assembled out of the other three.
function checkLabel() {
  paintShipped();
  forget(8);
}

// ------------------------------------------------------------------ 7 · the facets a person ticks

// **This page's own list, and the only one there is.** A tickable value is a thing a person
// chooses, and the store has no use for one until a sample carries it -- so a read of the store
// answers what the rows hold, never what they were allowed to hold, and nothing below the edge
// keeps a copy of this. The cost, stated: a facet the profile declares and this list never draws
// is a column that is always null, and nothing but somebody reading both catches it.
//
// `language` is not in it. Step 1 declares it for the scan and the jury, and it rides to the row
// from there -- asking again would be one sample described in two places.
const DECLARED_FACETS = [
  { name: "domain", pick: "one",
    values: ["debt_collection", "telesale", "bill_reminder", "customer_care"],
    said: "what the bot does, not the customer's industry. A column, so a sample without it is refused" },
  { name: "call_trigger", pick: "any",
    values: ["condition_met", "user_utterance", "every_turn"],
    said: "one per call, so tick every way this sample fires. Nothing ticked is a sample that calls nothing" },
  { name: "direction", pick: "one", values: ["inbound", "outbound"],
    said: "who placed the call. Goes to notes, because not every corpus this table holds is a call bot" },
  { name: "ambiguous", pick: "yes",
    said: "genuinely arguable — two annotators differing here is signal, not a mistake by either" },
  { name: "have_conversation_flow", pick: "yes",
    said: "a step in a scripted flow, where reaching it is what obliges the call. Goes to notes" }
];

const tickInput = facet =>
  facet.pick === "yes"
    ? `<label class="mode"><input type="checkbox" name="f-${facet.name}"> yes</label>`
    : facet.values.map(value =>
        `<label class="mode"><input type="${facet.pick === "one" ? "radio" : "checkbox"}"`
        + ` name="f-${facet.name}" value="${esc(value)}"> ${esc(value)}</label>`).join("");

// Nothing is pre-ticked where a value would be a claim nobody made: a default on `domain` is a
// facet filled in by the page, and a declared facet is exactly the kind nothing may fill in.
function paintFacetTicks() {
  $("facet-ticks").innerHTML = DECLARED_FACETS.map(facet =>
    `<div class="lab">${esc(facet.name)}</div>`
    + `<div class="bar">${tickInput(facet)}<span class="note">${esc(facet.said)}</span></div>`).join("");
}

// What the record carries under `class`: the declared facets and nothing else. A facet nobody
// ticked is left out rather than sent as null -- the route names it by name, which reads as a
// facet to go and tick rather than as a column that refused a value.
function readDeclaredFacets() {
  const ticked = { language: $("language").value };
  for (const facet of DECLARED_FACETS) {
    const boxes = [...document.querySelectorAll(`input[name="f-${facet.name}"]`)];
    if (facet.pick === "yes") ticked[facet.name] = boxes[0].checked;
    else if (facet.pick === "any") ticked[facet.name] = boxes.filter(box => box.checked).map(box => box.value);
    else {
      const one = boxes.find(box => box.checked);
      if (one) ticked[facet.name] = one.value;
    }
  }
  return ticked;
}

// --------------------------------------------------------------------------- 8 · the record

// The record this page assembles, and the only thing it composes. What arrived is kept and what
// ships sits beside it under `new_`: the human's edits, then every span they handed back replaced
// wherever its value occurs. The replacing is the service's -- the offsets index `review_text`,
// and `messages` and `label` are other strings, so the route runs the same rule by value over
// every field and answers the copy.
async function assemble() {
  if (!held.sample) return cannotAsk(8, "record", "check the sample first: there is nothing to assemble");
  paintShipped();
  // No span handed back is no value to replace, which is what the route is told: the three `new_`
  // keys are then the edits with nothing redacted, because nothing was confirmed.
  const handed = held.handed ?? { review_text: "", claims: [], spans: [] };
  const body = { ...held.sample, ...held.edited, detected: handed };
  show("in-8", body);
  mark(8, "wait", "waiting");
  const answer = await call("/data-quality/personal-data/redact", body);
  if (!answer.ok) return refused(8, "record", answer.detail);
  const redacted = answer.data;
  held.record = {
    ...held.sample,
    messages: held.sample.messages ?? [],
    tools: held.sample.tools ?? [],
    label: held.sample.label ?? null,
    new_messages: redacted.messages,
    // `null` where nothing made a new version of the catalog: a copy of it under a second key is
    // one more thing to keep in step. The human leaving it alone is not enough on its own --
    // `review_text` holds the catalog, so a confirmed value can sit in a tool's
    // description and the route rewrites it there. A redacted catalog *is* a new version.
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
  mark(8, "answered", "assembled");
  show("record", held.record);
  const missing = [[2, "personal data"], [3, "duplicate"], [4, "abnormal"], [5, "replace"], [6, "ai review"]]
    .filter(([step]) => !held.asked[step]).map(([, named]) => named);
  $("approve-note").className = missing.length ? "note bad" : "note";
  $("approve-note").textContent = missing.length
    ? `not asked yet: ${missing.join(", ")} — the record carries what answered and nothing for the rest`
    : "every step answered";
}

// **approve** is the only thing on this page that keeps anything. A refusal leaves every answer
// where it is and the reviewer on this card: the service names the step that did not run, and
// **back to** is what goes there. Nothing is retried, because a second post is a person pressing
// the button again.
async function approve() {
  if (!held.record) return cannotAsk(8, "record", "assemble the record first: there is nothing to approve");
  $("approve-note").className = "note";
  $("approve-note").textContent = "posting…";
  const answer = await call("/records", held.record);
  if (!answer.ok) {
    $("approve-note").className = "note bad";
    $("approve-note").textContent = answer.detail;
    return;
  }
  for (const id of ["assemble", "approve"]) $(id).disabled = true;
  $("record").className = "big frozen";
  mark(8, "answered", "approved");
  $("approve-note").className = "note";
  // The two times are equal on a first post and apart on every one after it, which is the one
  // thing a reviewer wants to know: whether this sample had already been reviewed by somebody.
  $("approve-note").textContent = answer.data.created_time === answer.data.modified_time
    ? `stored as ${answer.data.id}`
    : `stored as ${answer.data.id} — replacing the review this sample carried before`;
}

// --------------------------------------------------------------------------- back to a step

// A correction is made where the part was made. Every rectangle names the ones above it that hold
// something to change, and **back to** goes there: the edit plus that step's own button again is
// how the answer is replaced, which is the same human step as everywhere else -- there is no
// second editor at the end, and nothing is re-called on the reviewer's behalf.
//
// What pressing it drops is the record and nothing more. Step 8 was assembled out of an answer
// you have just called wrong, so it stops reading as assembled; every other answer stands until
// the step it came from is actually edited, which is the rule each edit above already runs.
const RETURNABLE = [1, 2, 5, 6, 7];

function back(to, from) {
  forget(8);
  held.returned = to;
  paintReturn();
  $(`s${to}`).scrollIntoView({ behavior: "smooth", block: "center" });
  $("approve-note").className = "note";
  $("approve-note").textContent = `sent back to step ${to} from step ${from}: change it there, then press that step's own button again`;
}

// One return at a time: two rectangles both saying they are where the correction goes is two
// places to make it.
function paintReturn() {
  for (const step of RETURNABLE) {
    const here = held.returned === step;
    $(`back-${step}`).textContent = here ? "← make the correction here" : "";
    $(`s${step}`).classList.toggle("returned", here);
  }
}

// --------------------------------------------------------------------------- wiring

paintFacetTicks();
$("sample-text").value = json(EXAMPLE);
$("sample-check").onclick = checkSample;
$("detect").onclick = detect;
$("span-check").onclick = checkSpans;
$("span-add").onclick = addSpan;
$("duplicate-run").onclick = () => reportNothing(3, "/data-quality/duplicate");
$("abnormal-run").onclick = () => reportNothing(4, "/data-quality/abnormal");
$("auto").onchange = () => {
  forgetTheCopy();
  paintKeepTable();
};
$("keep-table").onchange = event => {
  const box = event.target.closest("[data-keep]");
  if (box) {
    held.keeps[box.dataset.keep] = box.checked;
    forgetTheCopy();
    paintKeepTable();
  }
};
// The language is a declaration about the sample, so an answer given in the other one was an
// answer about something else.
$("language").onchange = forgetTheAnswers;
$("replace-run").onclick = replace;
$("review-run").onclick = review;
for (const id of ["v-correct", "v-modify"]) {
  $(id).onchange = () => {
    $("label-editor").classList.toggle("hidden", !$("v-modify").checked);
    checkLabel();
  };
}
$("label-check").onclick = checkLabel;
// A tick is part of the record, so changing one after it was assembled makes it a record about a
// different claim. Same rule as every edit above, and the same answer: step 8 stops reading as
// assembled until **assemble** is pressed again.
$("facet-ticks").onchange = () => forget(8);
$("assemble").onclick = assemble;
$("approve").onclick = approve;
for (const button of document.querySelectorAll("button.back")) {
  button.onclick = () =>
    back(Number(button.dataset.back), Number(button.closest(".step").id.slice(1)));
}

// Re-asked on focus, not on a timer: the directory is edited by a person, and coming back to the
// tab is when they want to see what they edited.
window.addEventListener("focus", paintTicks);

paintTicks();
checkSample();
