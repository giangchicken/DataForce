// wiring · the composition root: every handler, the keyboard, the first paints, and the
// page's reaction to a change. Owns the frame and the action bar: pane-sample, pane-review,
// open-list, open-dataset, open-import, open-guide, sheet-guide, run-checks, skip, submit,
// submit-note. It attaches handlers to elements other modules own and reads none of them.

import { call } from "./wire.js";
import {
  $, marked, onKey, onReturn, say, show, ticksNamed
} from "./screen.js";
import {
  COPY_AFTER, DECLARED_FACETS, held
} from "./held.js";
import {
  CHECKS, forgetChecks, mark, paintChecks, sayChecking, sayChecksVerdict
} from "./checks.js";
import {
  labelPasted, markDrop, pastingOpen, queuePasted, runImport, showPasting, tookFile
} from "./importing.js";
import {
  askList, forgetQueue, nextQueued, oneQueued, paintList, picked, pickedChanged,
  sayQueueName, skipQueued, waiting, walkThese
} from "./queue.js";
import {
  askDataset, askStatistics, askStore, openStored, paintDataset, paintStrip
} from "./corpus.js";
import { composeRecord } from "./record.js";
import {
  addDomain, paintFacetTicks, paintGuideFacets, readDeclaredFacets
} from "./facets.js";
import {
  checkLabel, fillEditor, forgetLabel, forgetVerdict, hideLabelRefusal, paintShipped, review,
  rewriting, takeConsensus, tookVerdict
} from "./label.js";
import {
  addSpan, checkSpans, detect, editedSpans, forgetPersonalData, handedBack, hideDataRefusal,
  paintKeepTable, paintReviewText, paintValues, sayPersonalData
} from "./personal-data.js";
import { TICK_LISTS, paintTicks, readTicked } from "./models.js";
import { paintCalls, paintCatalog, paintTurns, sayNoSample } from "./conversation.js";

async function askNext() {
  const { answer, gone } = await nextQueued();
  for (const said of gone) say("submit-note", said, "bad");
  if (!answer.ok) return sayNoQueue(answer.detail);
  openSample(answer.data.sample, answer.data.key);
  paintStrip();
}

async function walkPicked() {
  if (!walkThese()) return;
  shutSheet("sheet-list");
  say("submit-note", "");
  await askNext();
}

async function openPicked(key) {
  shutSheet("sheet-list");
  const answer = await oneQueued(key);
  if (!answer.ok) return say("submit-note", answer.detail, "bad");
  say("submit-note", "");
  openSample(answer.data.sample, answer.data.key);
  paintStrip();
}

async function importLanded() {
  askStatistics();
  if (!held.sample) await askNext();
  else if (waiting()) paintStrip();
}

function sayNoQueue(said) {
  held.key = null;
  held.sample = null;
  sayNoSample(said);
  sayQueueName("");
  paintStrip();
  frozen(true);
  showPasting(true);
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
  sayQueueName(sample.id ? `#${sample.id}` : "");
  paintTurns();
  paintCatalog();
  paintCalls(rewriting());
  fillEditor();
  forgetVerdict();
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
  forgetPersonalData();
  forgetLabel();
  forgetChecks();
  show("record", undefined);
  hideRefusals();
}

function hideRefusals() {
  hideDataRefusal();
  hideLabelRefusal();
}

const RUNS = { 2: async () => await detect() && refreshCopy(), 6: review };

async function runChecks() {
  if (!held.sample) return;
  frozen(true);
  sayChecksVerdict("running…", "busy");
  hideRefusals();
  try {
    for (const { step, what } of CHECKS) {
      sayChecking(`Asking: ${what.toLowerCase()}…`);
      if (!await RUNS[step]()) {
        sayChecksVerdict(`stopped at ${what.toLowerCase()}`, "bad");
        sayChecking(`${what} did not answer, so the steps after it were not asked.`, "bad");
        return;
      }
    }
    sayChecksVerdict("both answered", "ok");
    sayChecking("Every machine step answered. What is left is yours.");
  } finally {
    frozen(!held.sample);
  }
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
  paintCalls(rewriting());
  composeRecord(readDeclaredFacets());
  return true;
}

function copyBroke(why) {
  mark(2, "bad", why);
  held.copyNote = why;
  paintReviewText();
  return false;
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
    const answer = await skipQueued(held.key);
    if (!answer.ok) return say("submit-note", answer.detail, "bad");
    say("submit-note", "");
    openSample(answer.data.sample, answer.data.key);
    paintStrip();
  } finally {
    frozen(!held.sample);
  }
}

const openSheet = id => { $(id).hidden = false; };
const shutSheet = id => { $(id).hidden = true; };

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
$("span-check").onclick = () => { if (checkSpans()) copyLater(); };
$("span-add").onclick = () => { if (addSpan()) copyLater(); };
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

$("paste-open").onclick = () => showPasting(pastingOpen());
$("paste-cancel").onclick = () => showPasting(false);
$("paste-now").onclick = async () => {
  const one = await labelPasted();
  if (!one) return;
  forgetQueue();
  openSample(one, null);
  paintStrip();
};
$("paste-queue").onclick = async () => { if (await queuePasted()) await importLanded(); };
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
$("import-run").onclick = async () => { if (await runImport()) await importLanded(); };
$("drop").ondragover = event => { event.preventDefault(); markDrop(true); };
$("drop").ondragleave = () => markDrop(false);
$("drop").ondrop = event => {
  event.preventDefault();
  markDrop(false);
  tookFile(event.dataTransfer.files[0]);
};

$("language").onchange = () => { forgetEverything(); if (held.sample) fillEditor(); };

$("domain-add").onclick = () => { addDomain(); composeRecord(readDeclaredFacets()); };
$("domain-new").onkeydown = event => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  addDomain();
  composeRecord(readDeclaredFacets());
};

for (const id of ["v-correct", "v-modify"]) {
  $(id).onchange = () => {
    tookVerdict();
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
for (const id of ["facet-ticks", "domain-ticks"]) {
  $(id).onchange = () => composeRecord(readDeclaredFacets());
}
$("label-text").oninput = copyLater;
$("take-consensus").onclick = () => { if (takeConsensus()) copyLater(); };

onKey(steer);
onReturn(paintTicks);

paintTicks();
askStore();
askStatistics();
askNext();
