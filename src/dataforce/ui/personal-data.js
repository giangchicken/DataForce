// adapter · card 1: the values the reviewer keeps, the ones they add, and the copy that ships.
// Owns panel-data, span-table, span-add, span-check, span-note, keep-table, auto, scan-raw,
// review-text, text-which, data-verdict, data-refusal.

import { asking, cannotAsk, mark } from "./checks.js";
import { saidLanguage } from "./conversation.js";
import { held, ticked } from "./held.js";
import { $, chars, esc, same, say, sayVerdict, sliced, wordFor } from "./screen.js";

export async function detect() {
  if (!held.sample) return cannotAsk(2, "no sample");
  if (!ticked.verifier) return cannotAsk(2, "tick a verifier first");
  const answer = await asking(2, {
    ...held.sample, language: saidLanguage(), verifier_model: ticked.verifier
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
  return true;
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

export function editedSpans() {
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

export function paintValues() {
  for (const row of editedSpans()) {
    const cell = $("span-table").querySelector(`[data-value="${row.i}"]`);
    cell.className = row.broke ? "value bad" : "value";
    cell.textContent = row.broke || row.value;
  }
}

const comparable = spans => spans.map(({ start, end, personal_data_class, placeholder }) =>
  ({ start, end, personal_data_class, placeholder }));

export function checkSpans() {
  const rows = editedSpans();
  paintValues();
  const broke = rows.filter(row => row.broke);
  say("span-note", broke.length
    ? `${broke.map(row => row.broke).join("; ")} — nothing was called`
    : "every row re-sliced", broke.length ? "bad" : "");
  const edited = !broke.length && !same(comparable(rows), comparable(held.detected.spans));
  if (!broke.length) {
    held.rows = rows.map(({ i, value, ...span }) => span);
    paintKeepTable();
  }
  return edited;
}

export function addSpan() {
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
  say("span-note", "a row added: type its offsets, then re-read");
  return true;
}

const inside = (span, spans) => spans.some(other =>
  !other.broke && held.keeps[other.i] !== false
  && other.start <= span.start && span.end <= other.end
  && other.end - other.start > span.end - span.start);

const dropped = (row, rows) => held.keeps[row.i] === false || ($("auto").checked && inside(row, rows));

export function paintKeepTable() {
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

export function handedBack() {
  if (!held.detected) return { review_text: "", claims: [], spans: [] };
  const rows = editedSpans().filter(row => !row.broke);
  return {
    review_text: held.detected.review_text,
    claims: held.detected.claims,
    spans: rows.filter(row => !dropped(row, rows)).map(({ i, value, ...span }) => span)
  };
}

export function sayPersonalData() {
  if (!held.detected) return;
  const found = held.rows.length;
  const scan = found ? `${found} ${wordFor(found, "span", "spans")} found` : "nothing found";
  if (!held.shipped) return mark(2, "wait", `${scan} · replacing…`);
  const kept = held.handed.spans.length;
  mark(2, "answered", `${scan} · ${kept
    ? `${kept} ${wordFor(kept, "value", "values")} replaced`
    : "nothing to replace"}`);
}

export function paintReviewText() {
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

export function forgetPersonalData() {
  paintReviewText();
  for (const id of ["span-table", "keep-table"]) $(id).querySelector("tbody").innerHTML = "";
  say("span-note", "");
  sayVerdict("data-verdict", "no scan yet", "");
}

export function hideDataRefusal() {
  $("data-refusal").hidden = true;
  $("data-refusal").textContent = "";
}
