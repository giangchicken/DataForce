// adapter · card 1: the values the reviewer keeps, the ones they add, and the copy that
// ships. **Not** where a value stands in the text — that is answered. Owns keep-table,
// value-new, value-class, value-add, value-note, keep-note, kind-new, kind-add, kind-note,
// review-text, text-which,
// data-verdict, data-refusal.

import { asking, cannotAsk, mark } from "./checks.js";
import { saidLanguage } from "./conversation.js";
import { held, ticked } from "./held.js";
import { $, chars, esc, say, sayVerdict, wordFor } from "./screen.js";
import { ask, call } from "./wire.js";

let classes = [];

let addedKinds = [];

let numberedAt = 0;

let confirmed = new Map();

export async function askClasses() {
  const answer = await ask("/data-quality/personal-data/classes");
  classes = answer.ok && Array.isArray(answer.data) ? answer.data : [];
  paintKinds();
}

const offeredKinds = () =>
  [...new Set([...classes, ...held.claimed.values(), ...addedKinds])];

function paintKinds(pick = $("value-class").value) {
  const kinds = offeredKinds();
  $("value-class").innerHTML = kinds.map(one =>
    `<option value="${esc(one)}"${one === pick ? " selected" : ""}>${esc(one)}</option>`).join("");
  $("value-class").value = kinds.includes(pick) ? pick : (kinds[0] || "");
}

const namedKind = said => String(said ?? "").trim().toUpperCase().replace(/\s+/g, "_");

export function addKind() {
  const said = namedKind($("kind-new").value);
  if (!said) return refuseKind("type a kind first");
  if (offeredKinds().includes(said)) return refuseKind(`${said} is already offered`);
  addedKinds = [...addedKinds, said];
  paintKinds(said);
  if (held.detected) paintCard();
  $("kind-new").value = "";
  say("kind-note", `${said} offered, and picked — a value added now is filed as one`);
  return true;
}

function refuseKind(why) {
  say("kind-note", why, "bad");
  return false;
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
  held.keeps = new Map();
  confirmed = whyConfirmed(scanned);
  held.scanned = scanned;
  held.detected = scanned;
  held.handed = null;
  held.shipped = null;
  held.record = null;
  await numbered(held.claimed);
  paintCard();
  paintReviewText();
  const found = held.claimed.size;
  sayVerdict("data-verdict", found ? `${found} to confirm` : "nothing found",
    found ? "bad" : "ok");
  return true;
}

export async function numbered(claimed) {
  if (!held.sample) return false;
  const mine = (numberedAt += 1);
  const answer = await call("/data-quality/personal-data/spans", {
    ...held.sample,
    claimed: [...claimed].map(([value, named]) => [named, value])
  });
  if (mine !== numberedAt) return false;
  if (!answer.ok) {
    say("value-note", `the spans could not be numbered: ${answer.detail}`, "bad");
    return false;
  }
  held.claimed = claimed;
  held.detected = answer.data;
  return true;
}

export const claimedWith = (value, named) => new Map(held.claimed).set(value, named);
export const keptWith = (span, on) => new Map(held.keeps).set(spanKey(span), on);

const spanKey = span => JSON.stringify([span.path || [], span.start, span.end]);

// A span names the field it is in and the offsets inside **that** string, so this walks the
// record rather than slicing the text on the screen. Code points, because the service counts
// them and a browser counts UTF-16 units -- two different strings from the same two numbers.
const readsIn = (record, span) => {
  let node = record;
  for (const step of span.path || []) node = node == null ? node : node[step];
  return typeof node === "string" ? chars(node).slice(span.start, span.end).join("") : "";
};

const valuesIn = found => (held.sample ? found.spans.map(span => readsIn(held.sample, span)) : []);

function whyConfirmed(found) {
  const why = new Map();
  valuesIn(found).forEach((value, at) => {
    const { reason } = found.spans[at];
    if (reason && !why.has(value)) why.set(value, reason);
  });
  return why;
}

const kept = span => held.keeps.get(spanKey(span)) !== false;

const STANDS_FOR = /^<([A-Z][A-Z0-9_]*)_\d+>$/;

export const standsFor = span => {
  const typed = held.stands.get(spanKey(span));
  const named = typed ? STANDS_FOR.exec(typed) : null;
  return named && named[1] === span.personal_data_class ? typed : span.placeholder;
};

export function standInWith(span, typed) {
  const said = typed.trim();
  if (!said || said === span.placeholder) {
    const stands = new Map(held.stands);
    stands.delete(spanKey(span));
    return { ok: true, stands };
  }
  const named = STANDS_FOR.exec(said);
  if (!named) {
    return { ok: false, why: `${said} is not a placeholder — one reads <CLASS_1>.` };
  }
  if (named[1] !== span.personal_data_class) {
    return {
      ok: false,
      why: `${said} stands in for ${named[1]}, and this value is filed as ${span.personal_data_class}.`
    };
  }
  return { ok: true, stands: new Map(held.stands).set(spanKey(span), said) };
}

const placesOf = (value, values) => held.detected.spans
  .map((span, at) => [span, at])
  .filter(([, at]) => values[at] === value);

const fieldName = span => (span.path || []).reduce((said, step) =>
  (typeof step === "number" ? `${said}[${step}]` : said ? `${said}.${step}` : String(step)), "");

export const unreplaced = () => {
  if (!held.detected || !held.shipped) return [];
  const values = valuesIn(held.detected);
  return [...held.claimed.keys()].filter(value =>
    placesOf(value, values).every(([span]) => kept(span))
    && (held.shipped.review_text || "").includes(value));
};
const placed = value => held.detected.claims.some(([, said]) => said === value);

const pickClass = (value, named) => `<select data-class="${esc(value)}">${
  offeredKinds().map(one =>
    `<option value="${esc(one)}"${one === named ? " selected" : ""}>${esc(one)}</option>`).join("")
}</select>`;

// One table, because there is one decision on it. A value and the places it stands are not two
// tables: `×3` says a value occurs three times and nothing about *which* three, and `Nam` inside
// `nam` inside a longer word is the case the containment rule exists for.
//
// **The tick sits on each place rather than spanning them.** A span names the field it stands in
// and is replaced on its own, so `Nam` the given name and `Nam` in *miền Nam* are two decisions
// and the reviewer makes both. The value and its kind are one decision and are drawn on every row
// rather than merged down the group: a cell of its own height reads as rows with columns missing,
// and the three pickers are one control -- they carry the same value, so moving any of them moves
// the kind and all three redraw alike.
export function paintCard() {
  if (!held.detected) return;
  const values = valuesIn(held.detected);
  $("keep-table").querySelector("tbody").innerHTML = [...held.claimed].map(([value, named]) => {
    const said = `<td>${pickClass(value, named)}</td><td class="value">${esc(value)}</td>`;
    const places = placesOf(value, values);
    if (!places.length) {
      return `<tr><td></td>${said}<td class="note" colspan="4">${
        placed(value) ? "inside something longer" : "not in the text"}</td></tr>`;
    }
    return places.map(([span, at]) => `<tr class="${kept(span) ? "" : "out"}">`
      + `<td><input type="checkbox" data-keep="${at}"${kept(span) ? " checked" : ""}></td>`
      + said
      + `<td class="standsfor"><input data-standsfor="${at}" value="${esc(standsFor(span))}"`
      + ` title="${esc(standsFor(span))}" spellcheck="false"></td>`
      + `<td class="field">${esc(fieldName(span))}</td>`
      + `<td class="at">${esc(span.start)}</td>`
      + `<td class="at">${esc(span.end)}</td></tr>`).join("");
  }).join("");
  paintKinds();
}

export async function addValue() {
  const value = $("value-new").value.trim();
  const named = $("value-class").value;
  if (!held.detected) return refuseValue("nothing has been read for personal data yet");
  if (!value) return refuseValue("type the value first");
  if (held.claimed.has(value)) return refuseValue("that value is already on the table");
  if (!named) return refuseValue("say what kind it is");
  if (!await numbered(claimedWith(value, named))) return false;
  $("value-new").value = "";
  paintKinds(named);
  say("value-note", `added as ${named} — every occurrence is found for you`);
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
    spans: held.detected.spans
      .map((span, at) => ({
        ...span,
        placeholder: standsFor(span),
        reason: span.reason || confirmed.get(values[at]) || null
      }))
      .filter(kept)
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
  say("value-note", "");
  sayVerdict("data-verdict", "no scan yet", "");
}

export function sayDataRefusal(detail) {
  $("data-refusal").hidden = detail === "";
  $("data-refusal").textContent = detail;
}
