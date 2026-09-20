// wiring · the composition root.

import { ask, call } from "./wire.js";
import {
  $, chars, esc, json, marked, onKey, onReturn, readTick, same, say, show, sliced, ticksNamed,
  wordFor
} from "./screen.js";
import {
  CHECKS, COPY_AFTER, DATASET_PAGE, DECLARED_FACETS, PICK_SAID, STATE_SAID, checked, held, ticked
} from "./held.js";
import { TICK_LISTS, paintTicks, readTicked } from "./models.js";
import { drawCalls, drawTurns, paintCalls, paintCatalog, paintTurns } from "./conversation.js";

function mark(step, state, text) {
  checked[step] = { state, text };
  paintChecks();
}

function paintChecks() {
  for (const { step, said } of CHECKS) {
    const at = checked[step] || { state: "", text: "not run" };
    const kind = { answered: "ok", bad: "bad", unasked: "bad", wait: "busy", edited: "ok" }[at.state] || "";
    const cell = $(said);
    cell.className = `said${kind ? ` ${kind}` : ""}`;
    cell.textContent = at.text || "not run";
  }
}

function cannotAsk(step, why) {
  mark(step, "unasked", why);
  return false;
}

async function asking(step, body, path) {
  mark(step, "wait", "asking…");
  const answer = await call(path, body);
  if (!answer.ok) mark(step, "bad", answer.detail);
  return answer;
}

let left = null;

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
  showPasting(true);
}

function showPasting(open) {
  $("pasting").hidden = !open;
  if (open) $("paste-text").focus();
}

function frozen(off) {
  for (const id of ["run-checks", "skip", "submit"]) $(id).disabled = off;
}

function openSample(sample, key) {
  held.key = key || null;
  held.sample = sample || null;
  forgetEverything();
  if (!sample) {
    return sayNoQueue("Nothing is waiting. Import a file, or come back when somebody adds one.");
  }
  frozen(false);
  $("sample-name").textContent = sample.id ? `#${sample.id}` : "";
  paintTurns();
  paintCatalog();
  paintCalls($("v-modify").checked);
  fillEditor();
  $("v-correct").checked = false;
  $("v-modify").checked = false;
  $("label-editor").hidden = true;
  checkLabel();
  for (const facet of DECLARED_FACETS) {
    for (const box of ticksNamed(`f-${facet.name}`)) box.checked = false;
  }
  say("domain-note", "");
}

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
  $("scan-raw").open = found > 0;
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

function addSpan() {
  if (!held.detected) return say("span-note", "the scan has not answered: there is no text for a span to index", "bad");
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

function handedBack() {
  if (!held.detected) return { review_text: "", claims: [], spans: [] };
  const rows = editedSpans().filter(row => !row.broke);
  return {
    review_text: held.detected.review_text,
    claims: held.detected.claims,
    spans: rows.filter(row => !dropped(row, rows)).map(({ i, value, ...span }) => span)
  };
}

function shippingBody() {
  paintShipped();
  return { ...held.sample, ...held.edited, detected: handedBack() };
}

let copySoon = null;
let copyAt = 0;

function copyLater() {
  held.handed = null;
  held.shipped = null;
  held.copyNote = null;
  paintShipped();
  sayPersonalData();
  paintReviewText();
  clearTimeout(copySoon);
  copyAt += 1;
  copySoon = setTimeout(refreshBoth, COPY_AFTER);
}

function refreshBoth() {
  checkLabel();
  return refreshCopy();
}

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
  paintCalls($("v-modify").checked);
  composeRecord();
  return true;
}

function copyBroke(why) {
  mark(2, "bad", why);
  held.copyNote = why;
  paintReviewText();
  return false;
}

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

function sayAgreement(reviewed) {
  const agreed = ((reviewed || {}).llm || {}).label_agreement;
  if (typeof agreed !== "number") return "reviewed";
  return `${Math.round(agreed * 100)}% agreement with the label`;
}

function fillEditor() {
  if (!held.sample) return;
  $("label-text").value = json(held.sample.label ?? null);
  paintShipped();
}

function typedLabel() {
  const arrived = held.sample.label ?? null;
  if (!$("v-modify").checked) return arrived;
  try { return JSON.parse($("label-text").value); } catch { return { unparsed: $("label-text").value }; }
}

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
  paintCalls($("v-modify").checked);
}

let faultAt = 0;

async function checkLabel() {
  if (!held.sample) return false;
  const mine = (faultAt += 1);
  const answer = await call("/data-quality/label", { ...held.sample, ...(held.edited || {}) });
  if (mine !== faultAt) return false;
  held.faults = answer.ok ? answer.data : null;
  if (!answer.ok) return sayNoCheck(answer.detail);
  paintFaults();
  return true;
}

function sayNoCheck(why) {
  const said = $("label-fault");
  said.hidden = false;
  said.textContent = `the label could not be checked against the catalog: ${why}`;
  return false;
}

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

function paintConsensus() {
  const offered = agreedLabel() !== "";
  $("consensus-line").hidden = !offered;
  if (offered) say("consensus-note", "the one label the panel agreed on, into the box below");
}

const agreedLabel = () => {
  const agreed = ((held.review || {}).llm || {}).consensus;
  return typeof agreed === "string" ? agreed.trim() : "";
};

function takeConsensus() {
  const agreed = agreedLabel();
  if (!agreed) return false;
  let laid = agreed;
  try { laid = json(JSON.parse(agreed)); } catch { laid = agreed; }
  $("label-text").value = laid;
  $("v-modify").checked = true;
  $("v-correct").checked = false;
  $("label-editor").hidden = false;
  held.settled = true;
  copyLater();
  return true;
}

const addedValues = {};

function facetValues(name) {
  const facet = DECLARED_FACETS.find(one => one.name === name);
  if (!facet || !facet.values) return [];
  const byFacet = (counted || {}).counted_distribution_by_facet || {};
  const stored = facet.pick === "one" ? Object.keys(byFacet[name] || {}) : [];
  return [...new Set([...facet.values, ...stored, ...(addedValues[name] || [])])];
}

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

function paintFacetTicks() {
  paintDomainTicks();
  $("facet-ticks").innerHTML = DECLARED_FACETS.filter(facet => facet.name !== "domain").map(facet =>
    `<div class="lab">${esc(facet.name)}</div>`
    + `<div class="tickbox">${tickInput(facet)}</div>`
    + `<div class="note">${esc(facet.said)}</div>`).join("");
}

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

function tickDomain(value) {
  for (const box of ticksNamed("f-domain")) {
    box.checked = !!value && box.value === value;
  }
}

function addDomain() {
  const said = $("domain-new").value.trim();
  if (!said) return say("domain-note", "type a domain first", "bad");
  if (facetValues("domain").includes(said)) {
    return say("domain-note", `${said} is already offered`, "bad");
  }
  addedValues.domain = [...(addedValues.domain || []), said];
  paintDomainTicks();
  tickDomain(said);

  composeRecord();
  $("domain-new").value = "";
  say("domain-note", `${said} added and ticked — it stays offered once a sample carries it`);
}

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

function composeRecord() {
  if (!held.sample || !held.shipped) return;
  const redacted = held.shipped.sample;
  held.record = {
    ...held.sample,
    messages: held.sample.messages ?? [],
    tools: held.sample.tools ?? [],
    label: held.sample.label ?? null,
    new_messages: redacted.messages,
    new_tools: same(redacted.tools, held.sample.tools ?? []) ? null : redacted.tools,
    new_label: redacted.label,
    personal_data: held.detected ? { ...held.handed, outcome: held.shipped.outcome } : null,
    duplicate: null,
    abnormal: null,
    llm: held.review ? held.review.llm : null,
    sft: held.review ? held.review.sft : null,
    class: readDeclaredFacets()
  };
  show("record", held.record);
}

async function assemble() {
  if (!held.sample) return false;

  clearTimeout(copySoon);
  paintShipped();
  checkLabel();
  if (!await refreshCopy()) {
    sayRefusal("data-refusal", held.copyNote || "the copy that ships could not be made");
    return false;
  }
  return held.record !== null;
}

function sayRefusal(id, detail) {
  $(id).hidden = false;
  $(id).textContent = detail;
}

function whichPanel(detail) {
  const said = String(detail).toLowerCase();
  if (said.includes("personal") || said.includes("scan") || said.includes("redact")) return "data-refusal";
  return "label-refusal";
}

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

    say("submit-note", answer.data.created_time === answer.data.modified_time
      ? `stored as ${answer.data.id}`
      : `stored as ${answer.data.id} — replacing the review this sample carried before`);

    askStatistics();
    await askNext();
  } finally {
    frozen(!held.sample);
  }
}

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

async function queuePasted() {
  const { samples, broke } = readPasted($("paste-text").value);
  if (broke) return say("paste-note", broke, "bad");
  say("paste-note", "adding…");
  await sendLines(samples.map(one => JSON.stringify(one)).join("\n"), "paste-note");
}

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
  if (!held.sample) await askNext();
  else if (left) paintStrip();
}

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

const openSheet = id => { $(id).hidden = false; };
const shutSheet = id => { $(id).hidden = true; };

let counted = null;

async function askStore() {
  const answer = await ask("/store", {});
  if (!answer.ok) {
    $("store").className = "store none";
    $("store").textContent = "";
    return;
  }
  const said = answer.data;
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
  counted = answer.data;
  try {
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

const typing = node => !!node && (node.isContentEditable
  || ["INPUT", "TEXTAREA", "SELECT"].includes(node.tagName));

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
  if (event.key !== "Enter") return;
  event.preventDefault();
  addDomain();
};

for (const id of ["v-correct", "v-modify"]) {
  $(id).onchange = () => {
    $("label-editor").hidden = !$("v-modify").checked;
    held.settled = $("v-correct").checked || $("v-modify").checked;
    paintShipped();
    copyLater();
  };
}

for (const id of TICK_LISTS) $(id).onchange = readTicked;

$("span-table").oninput = () => { paintValues(); copyLater(); };
$("keep-table").onchange = event => {
  const box = event.target.closest("[data-keep]");
  if (!box) return;
  held.keeps[Number(box.dataset.keep)] = box.checked;
  copyLater();
  paintKeepTable();
};
$("auto").onchange = () => { copyLater(); paintKeepTable(); };
for (const id of ["facet-ticks", "domain-ticks"]) $(id).onchange = composeRecord;
$("label-text").oninput = copyLater;
$("take-consensus").onclick = takeConsensus;

onKey(steer);
onReturn(paintTicks);

paintTicks();
askStore();
askStatistics();
askNext();
