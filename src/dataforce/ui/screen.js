// adapter · that the page is a DOM at all.
//
// Every reach into the document goes through here, so the rest of `ui/` is written against
// elements by id and tick boxes by name rather than against a browser. That is what makes the
// other modules readable on their own: a panel says what it draws, not how a page is found.
//
// It also holds what markup needs and the page does not compute -- escaping, a plural, and the
// code-point slicing the offsets depend on.
//
// This module owns no id. Every id it touches is handed to it by the module that owns one.

export const $ = id => document.getElementById(id);
export const json = v => JSON.stringify(v, null, 2);

// Every interpolation into markup goes through this. What a span reads is a value out of the
// sample, and a corpus that says `<b>` is a corpus, not an instruction.
export const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
export const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
export const wordFor = (number, one, more) => (number === 1 ? one : more);

// Offsets are code points, because that is what slicing `review_text` in Python counts. A browser
// indexes UTF-16 units, so `text.slice(start, end)` reads a different string from the same two
// numbers the moment something outside the BMP is in the text.
export const chars = text => Array.from(text);
export const sliced = (text, start, end) => chars(text).slice(start, end).join("");

export function show(id, value, kind = "") {
  const el = $(id);
  el.className = kind;
  el.textContent = value === undefined ? "" : json(value);
}

export function say(id, said, kind = "") {
  const el = $(id);
  el.className = kind ? `${el.dataset.base || "note"} ${kind}` : (el.dataset.base || "note");
  el.textContent = said;
}

// ------------------------------------------------------------------------------- the tick boxes

export const tickBox = (name, value) =>
  `<label class="inline"><input type="${name === "jury" ? "checkbox" : "radio"}" name="${name}"`
  + ` value="${esc(value)}"> ${esc(value)}</label>`;

// Every box in one group, as an array. Named rather than reached by container, because a group is
// what a browser makes of a shared `name` and not of where the boxes were drawn.
export const ticksNamed = name => [...document.querySelectorAll(`input[name="${name}"]`)];

// The one value ticked in a group, or the empty string. A group nobody has ticked reads the same
// as a group that is not on the page, which is what every caller of this wants.
export const readTick = name => (document.querySelector(`input[name="${name}"]:checked`) || {}).value || "";

// One sentence in place of what these lists would have held. The ids are the caller's, because
// which lists there are is a fact about the panel that draws them.
export const sayInTicks = (ids, said) => ids.forEach(id => {
  $(id).innerHTML = `<span class="none">${esc(said)}</span>`;
});

// --------------------------------------------------------------- what the page as a whole hears

// Every element carrying this `data-` attribute, whatever it is and wherever it is drawn.
export const marked = name => [...document.querySelectorAll(`[data-${name}]`)];

export const onKey = handler => document.addEventListener("keydown", handler);

// Coming back to the tab. What is worth asking again when a person returns is the caller's to say.
export const onReturn = handler => window.addEventListener("focus", handler);
