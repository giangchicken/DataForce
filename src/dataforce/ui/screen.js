// adapter · that the page is a DOM at all. Owns no id.

export const $ = id => document.getElementById(id);
export const json = v => JSON.stringify(v, null, 2);

export const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
export const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
export const wordFor = (number, one, more) => (number === 1 ? one : more);
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

export function sayVerdict(id, said, kind) {
  $(id).className = `verdict${kind ? ` ${kind}` : ""}`;
  $(id).textContent = said;
}

export const tickBox = (name, value) =>
  `<label class="inline"><input type="${name === "jury" ? "checkbox" : "radio"}" name="${name}"`
  + ` value="${esc(value)}"> ${esc(value)}</label>`;

export const ticksNamed = name => [...document.querySelectorAll(`input[name="${name}"]`)];

export const readTick = name => (document.querySelector(`input[name="${name}"]:checked`) || {}).value || "";

export const sayInTicks = (ids, said) => ids.forEach(id => {
  $(id).innerHTML = `<span class="none">${esc(said)}</span>`;
});

export const marked = name => [...document.querySelectorAll(`[data-${name}]`)];

export const onKey = handler => document.addEventListener("keydown", handler);
export const onReturn = handler => window.addEventListener("focus", handler);
