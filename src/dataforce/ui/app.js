// wiring · the composition root: every handler, the keyboard, the first paints, and the
// page's reaction to a change. Draws nothing. Attaches handlers to controls other modules
// own and reads none of them. Owns the sheets and the action bar: sheet-guide, sheet-import,
// sheet-list, sheet-dataset, submit, submit-note.

import { call } from "./wire.js";
import {
  $, marked, onKey, onReturn, say, ticksNamed, wordFor
} from "./screen.js";
import {
  COPY_AFTER, DECLARED_FACETS, held
} from "./held.js";
import { forgetChecks, mark, paintActs, paintChecks } from "./checks.js";
import {
  importBusy, labelPasted, markDrop, pastingOpen, queuePasted, runImport, showPasting,
  tookFile
} from "./importing.js";
import {
  askList, forgetQueue, nextQueued, oneQueued, paintList, picked, pickedChanged,
  sayQueueName, skipQueued, waiting, walkThese
} from "./queue.js";
import {
  askDataset, askStatistics, askStore, openStored, paintDataset, paintStrip
} from "./corpus.js";
import { composeRecord, forgetRecord, paintRecord } from "./record.js";
import {
  addDomain, forgetDomainNote, paintFacetTicks, paintGuideFacets, readDeclaredFacets
} from "./facets.js";
import {
  addCall, checkLabel, droppedCall, forgetLabel, forgetVerdict, paintArrived, paintShipped,
  pickedTool, review, sayLabelRefusal, tookNoCall, tookVerdict, typedArgument
} from "./label.js";
import {
  addKind, addValue, askClasses, claimedWith, detect, forgetPersonalData, handedBack, keptWith,
  numbered, paintCard, paintReviewText, sayDataRefusal, sayPersonalData, unreplaced
} from "./personal-data.js";
import { TICK_LISTS, paintTicks, readTicked } from "./models.js";
import { paintCatalog, paintTurns, sayNoSample } from "./conversation.js";

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
  actsChanged();
  showPasting(true);
}

let busy = false;
let numbering = 0;

function whatIsInTheWay() {
  if (busy) return ["waiting for the last answer…", false];
  if (!held.sample) return ["open a sample first", false];
  if (!held.detected) return ["find the personal data first", false];
  if (numbering > 0) return ["numbering the values you left…", false];
  if (held.copyNote) return [held.copyNote, true];
  if (!held.shipped) return ["replacing the values you kept…", false];
  const left = unreplaced().length;
  if (left) {
    return [`the copy still holds ${left} ${wordFor(left, "value", "values")} you kept, so it is`
      + " not a text the reviewers may be shown", true];
  }
  return ["", false];
}

function actsChanged() {
  const off = busy || !held.sample;
  for (const id of ["skip", "submit"]) $(id).disabled = off;
  const [why, bad] = whatIsInTheWay();
  paintActs(!off, why, bad ? "bad" : "");
}

function openSample(sample, key) {
  held.key = key || null;
  held.sample = sample || null;
  forgetEverything();
  if (!sample) {
    return sayNoQueue("Nothing is waiting. Import a file, or come back when somebody adds one.");
  }
  sayQueueName(sample.id ? `#${sample.id}` : "");
  paintTurns();
  paintCatalog();
  paintArrived();
  paintShipped();
  askCatalog();
  for (const facet of DECLARED_FACETS) {
    for (const box of ticksNamed(`f-${facet.name}`)) box.checked = false;
  }
  forgetDomainNote();
}

function forgetEverything() {
  held.scanned = null;
  held.detected = null;
  held.claimed = new Map();
  held.keeps = new Map();
  held.review = null;
  held.record = null;
  held.written = null;
  held.handed = null;
  held.shipped = null;
  held.copyNote = null;
  held.settled = false;
  held.faults = null;
  clearTimeout(copySoon);
  copyAt += 1;
  forgetPersonalData();
  // With the draft on the form, because the draft is computed too — it is seeded from a panel
  // that answered in the language this may just have changed. Everything else `forgetEverything`
  // drops goes silently; this one has to go **visibly**, or the form keeps showing a call that no
  // longer ships.
  forgetVerdict();
  forgetLabel();
  forgetChecks();
  forgetRecord();
  hideRefusals();
  actsChanged();
}

function hideRefusals() {
  sayDataRefusal("");
  sayLabelRefusal("");
}

async function findData() {
  if (!held.sample) return false;
  busy = true;
  actsChanged();
  hideRefusals();
  try {
    return await detect() && await refreshCopy();
  } finally {
    busy = false;
    actsChanged();
  }
}

async function askReviewers() {
  const [why] = whatIsInTheWay();
  if (why) return false;
  busy = true;
  actsChanged();
  try {
    return await review(held.shipped.sample);
  } finally {
    busy = false;
    actsChanged();
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
  actsChanged();
}

function refreshBoth() {
  askCatalog();
  return refreshCopy();
}

// The catalog's answer is what the record table's `schema_valid` row reads, and it lands on its
// own clock: the check and the copy go out together and the copy usually wins, so the row would go
// on saying what the last check said while the warning above it said the opposite.
function askCatalog() {
  return checkLabel().then(paintRecord);
}

async function refreshCopy() {
  if (!held.sample) return false;
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
  paintArrived();
  composeRecord(readDeclaredFacets());
  actsChanged();
  return true;
}

function copyBroke(why) {
  mark(2, "bad", why);
  held.copyNote = why;
  paintReviewText();
  actsChanged();
  return false;
}

async function assemble() {
  if (!held.sample) return false;

  clearTimeout(copySoon);
  paintShipped();
  askCatalog();
  if (!await refreshCopy()) {
    sayDataRefusal(held.copyNote || "the copy that ships could not be made");
    return false;
  }
  return held.record !== null;
}



function sayOnItsPanel(detail) {
  const said = String(detail).toLowerCase();
  const data = said.includes("personal") || said.includes("scan") || said.includes("redact");
  if (data) sayDataRefusal(detail);
  else sayLabelRefusal(detail);
}

async function submit() {
  if (!held.sample) return;
  busy = true;
  actsChanged();
  hideRefusals();
  say("submit-note", "posting…");
  try {
    if (!await assemble()) return say("submit-note", "not posted", "bad");
    const where = held.key ? `/records?queue_key=${encodeURIComponent(held.key)}` : "/records";
    const answer = await call(where, held.record);
    if (!answer.ok) {
      sayOnItsPanel(answer.detail);
      return say("submit-note", "refused — nothing was written", "bad");
    }

    say("submit-note", answer.data.created_time === answer.data.modified_time
      ? `stored as ${answer.data.id}`
      : `stored as ${answer.data.id} — replacing the review this sample carried before`);

    askStatistics();
    await askNext();
  } finally {
    busy = false;
    actsChanged();
  }
}

async function skip() {
  if (!held.key) return;
  busy = true;
  actsChanged();
  say("submit-note", "skipping…");
  try {
    const answer = await skipQueued(held.key);
    if (!answer.ok) return say("submit-note", answer.detail, "bad");
    say("submit-note", "");
    openSample(answer.data.sample, answer.data.key);
    paintStrip();
  } finally {
    busy = false;
    actsChanged();
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
actsChanged();

$("run-detect").onclick = findData;
$("run-review").onclick = askReviewers;
$("submit").onclick = submit;
$("skip").onclick = skip;

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
$("import-run").onclick = async () => {
  try {
    if (await runImport()) await importLanded();
  } finally {
    importBusy(false);
  }
};
$("drop").ondragover = event => { event.preventDefault(); markDrop(true); };
$("drop").ondragleave = () => markDrop(false);
$("drop").ondrop = event => {
  event.preventDefault();
  markDrop(false);
  tookFile(event.dataTransfer.files[0]);
};

$("language").onchange = () => { forgetEverything(); if (held.sample) paintShipped(); };

$("domain-add").onclick = () => { if (addDomain()) composeRecord(readDeclaredFacets()); };
$("domain-new").onkeydown = event => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  if (addDomain()) composeRecord(readDeclaredFacets());
};

for (const id of ["v-take", "v-keep", "v-write"]) {
  $(id).onchange = () => {
    tookVerdict();
    paintShipped();
    copyLater();
  };
}

for (const id of TICK_LISTS) $(id).onchange = readTicked;

$("call-form").onchange = event => { if (pickedTool(event)) copyLater(); };
$("call-form").oninput = event => { if (typedArgument(event)) copyLater(); };
$("call-form").onclick = event => { if (droppedCall(event)) copyLater(); };
$("call-add").onclick = () => { if (addCall()) copyLater(); };
$("call-none").onchange = () => { tookNoCall(); copyLater(); };

async function valuesChanged(pending) {
  numbering += 1;
  actsChanged();
  try {
    if (await pending) copyLater();
  } finally {
    numbering -= 1;
    actsChanged();
  }
  paintCard();
}

$("value-add").onclick = () => valuesChanged(addValue());
$("value-new").onkeydown = event => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  valuesChanged(addValue());
};
$("kind-add").onclick = () => addKind();
$("kind-new").onkeydown = event => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  addKind();
};
$("keep-table").onchange = event => {
  const said = event.target.closest("[data-class]");
  if (said) {
    if (!held.claimed.has(said.dataset.class)) return paintCard();
    return valuesChanged(numbered(claimedWith(said.dataset.class, said.value)));
  }
  const box = event.target.closest("[data-keep]");
  if (!box) return;
  const span = (held.detected || { spans: [] }).spans[Number(box.dataset.keep)];
  if (!span) return paintCard();
  held.keeps = keptWith(span, box.checked);
  paintCard();
  return copyLater();
};
for (const id of ["facet-ticks", "domain-ticks"]) {
  $(id).onchange = () => composeRecord(readDeclaredFacets());
}

onKey(steer);
onReturn(paintTicks);

paintTicks();
askClasses();
askStore();
askStatistics();
askNext();
