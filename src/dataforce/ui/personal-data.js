// adapter · card 1: the values the reviewer keeps, the ones they add, and the copy that
// ships. **Not** where a value stands in the text — that is answered. Owns keep-table,
// value-new, value-class, value-add, value-note, scan-raw, review-text, text-which,
// data-verdict, data-refusal.

import { asking, cannotAsk, mark } from "./checks.js";
import { saidLanguage } from "./conversation.js";
import { held, ticked } from "./held.js";
import { $, chars, esc, say, sayVerdict, wordFor } from "./screen.js";
import { ask, call } from "./wire.js";

let classes = [];

let numberedAt = 0;

let confirmed = new Map();

export async function askClasses() {
  const answer = await ask("/data-quality/personal-data/classes");
  classes = answer.ok && Array.isArray(answer.data) ? answer.data : [];
  $("value-class").innerHTML = classes
    .map(one => `<option value="${esc(one)}">${esc(one)}</option>`).join("");
}

export async function detect() {
  if (!held.sample) return cannotAsk(2, "no sample");
  if (!ticked.verifier) return cannotAsk(2, "tick a verifier first");
  if (!classes.length) await askClasses();
  const answer = await asking(2, {
    ...held.sample, language: saidLanguage(), verifier_model: ticked.verifier
  }, "/data-quality/personal-data");
  if (!answer.ok) return false;
  const scanned = answer.data;
  held.claimed = new Map(scanned.claims.map(([named, value]) => [value, named]));
  const confirmedValues = new Set(valuesIn(scanned));
  held.keeps = new Map(scanned.claims.map(([, value]) => [value, confirmedValues.has(value)]));
  confirmed = whyConfirmed(scanned);
  held.scanned = scanned;
  held.detected = scanned;
  held.handed = null;
  held.shipped = null;
  held.record = null;
  await numbered(held.claimed, held.keeps);
  paintCard();
  paintReviewText();
  const found = held.claimed.size;
  sayVerdict("data-verdict", found ? `${found} to confirm` : "nothing found",
    found ? "bad" : "ok");
  $("scan-raw").open = found > 0;
  return true;
}

export async function numbered(claimed, keeps) {
  if (!held.sample) return false;
  const mine = (numberedAt += 1);
  const answer = await call("/data-quality/personal-data/spans", {
    ...held.sample,
    claimed: [...claimed]
      .filter(([value]) => keeps.get(value) !== false)
      .map(([value, named]) => [named, value])
  });
  if (mine !== numberedAt) return false;
  if (!answer.ok) {
    say("value-note", `the spans could not be numbered: ${answer.detail}`, "bad");
    return false;
  }
  held.claimed = claimed;
  held.keeps = keeps;
  held.detected = answer.data;
  return true;
}

export const claimedWith = (value, named) => new Map(held.claimed).set(value, named);
export const keptWith = (value, on) => new Map(held.keeps).set(value, on);

const readsIn = (letters, span) => letters.slice(span.start, span.end).join("");
const valuesIn = found => {
  const letters = chars(found.review_text);
  return found.spans.map(span => readsIn(letters, span));
};

function whyConfirmed(found) {
  const why = new Map();
  valuesIn(found).forEach((value, at) => {
    const { reason } = found.spans[at];
    if (reason && !why.has(value)) why.set(value, reason);
  });
  return why;
}

function occurrences(found) {
  const seen = new Map();
  for (const value of valuesIn(found)) seen.set(value, (seen.get(value) || 0) + 1);
  return seen;
}

const kept = value => held.keeps.get(value) !== false;

export const unreplaced = () => (!held.detected || !held.shipped ? []
  : [...held.claimed.keys()].filter(value =>
    kept(value) && (held.shipped.review_text || "").includes(value)));
const placed = value => held.detected.claims.some(([, said]) => said === value);

const pickClass = (value, named) => `<select data-class="${esc(value)}">${
  [...new Set([...classes, ...held.claimed.values()])].map(one =>
    `<option value="${esc(one)}"${one === named ? " selected" : ""}>${esc(one)}</option>`).join("")
}</select>`;

export function paintCard() {
  if (!held.detected) return;
  const counted = occurrences(held.detected);
  const values = valuesIn(held.detected);
  $("keep-table").querySelector("tbody").innerHTML = [...held.claimed].map(([value, named]) => {
    const occurs = counted.get(value) || 0;
    return `<tr class="${kept(value) ? "" : "out"}">
      <td><input type="checkbox" data-keep="${esc(value)}"${kept(value) ? " checked" : ""}></td>
      <td>${pickClass(value, named)}</td>
      <td class="value">${esc(value)}</td>
      <td class="note">${!kept(value) ? "left in the text"
        : occurs ? `×${occurs}`
        : placed(value) ? "inside something longer" : "not in the text"}</td>
    </tr>`;
  }).join("");
  $("scan-raw").querySelector("tbody").innerHTML = held.detected.spans.map((span, at) => `
    <tr>
      <td>${esc(span.id)}</td>
      <td>${esc(span.personal_data_class)}</td>
      <td>${esc(span.placeholder)}</td>
      <td class="value">${esc(values[at])}</td>
    </tr>`).join("");
}

export async function addValue() {
  const value = $("value-new").value.trim();
  const named = $("value-class").value;
  if (!held.detected) return refuseValue("nothing has been read for personal data yet");
  if (!value) return refuseValue("type the value first");
  if (held.claimed.has(value)) return refuseValue("that value is already on the table");
  if (!classes.length) {
    return refuseValue("nothing said what a value may be, so there is no kind to add it as");
  }
  if (!named) return refuseValue("say what kind it is");
  if (!await numbered(claimedWith(value, named), held.keeps)) return false;
  $("value-new").value = "";
  say("value-note", "added — every occurrence is found for you");
  return true;
}

function refuseValue(why) {
  say("value-note", why, "bad");
  return false;
}

export function handedBack() {
  if (!held.detected) return { review_text: "", claims: [], spans: [] };
  const values = valuesIn(held.detected);
  return {
    review_text: held.detected.review_text,
    claims: held.scanned.claims,
    spans: held.detected.spans.map((span, at) =>
      span.reason ? span : { ...span, reason: confirmed.get(values[at]) ?? null })
  };
}

export function sayPersonalData() {
  if (!held.detected) return;
  const found = held.claimed.size;
  const scan = found ? `${found} ${wordFor(found, "value", "values")} found` : "nothing found";
  if (!held.shipped) return mark(2, "wait", `${scan} · replacing…`);
  const left = unreplaced().length;
  if (left) {
    return mark(2, "bad",
      `${scan} · the copy still holds ${left} ${wordFor(left, "value", "values")} you kept`);
  }
  const replaced = new Set(valuesIn(held.handed)).size;
  mark(2, "answered", `${scan} · ${replaced
    ? `${replaced} ${wordFor(replaced, "value", "values")} replaced`
    : "nothing to replace"}`);
}

export function paintReviewText() {
  const which = $("text-which");
  const shown = $("review-text");
  if (!held.detected) {
    which.textContent = "The text the scan reads";
    shown.textContent = "Nothing has been read for personal data yet.";
    return;
  }
  which.textContent = held.settled
    ? "The text as it ships — every value you kept replaced, the label with it"
    : "The conversation the reviewers will be handed — every value you kept replaced";
  if (held.shipped) shown.textContent = held.shipped.review_text;
  else shown.textContent = held.copyNote || "replacing…";
}

export function forgetPersonalData() {
  numberedAt += 1;
  confirmed = new Map();
  paintReviewText();
  $("keep-table").querySelector("tbody").innerHTML = "";
  $("scan-raw").querySelector("tbody").innerHTML = "";
  say("value-note", "");
  sayVerdict("data-verdict", "no scan yet", "");
}

export function sayDataRefusal(detail) {
  $("data-refusal").hidden = detail === "";
  $("data-refusal").textContent = detail;
}
