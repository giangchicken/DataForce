// adapter · the two checks, and the row each one reports on. Owns said-2, said-6.

import { $ } from "./screen.js";
import { call } from "./wire.js";

export const CHECKS = [
  { step: 2, what: "Personal data", said: "said-2" },
  { step: 6, what: "Label", said: "said-6" }
];

export const checked = {};

export function mark(step, state, text) {
  checked[step] = { state, text };
  paintChecks();
}

export function paintChecks() {
  for (const { step, said } of CHECKS) {
    const at = checked[step] || { state: "", text: "not run" };
    const kind = { answered: "ok", bad: "bad", unasked: "bad", wait: "busy", edited: "ok" }[at.state] || "";
    const cell = $(said);
    cell.className = `said${kind ? ` ${kind}` : ""}`;
    cell.textContent = at.text || "not run";
  }
}

export function cannotAsk(step, why) {
  mark(step, "unasked", why);
  return false;
}

export async function asking(step, body, path) {
  mark(step, "wait", "asking…");
  const answer = await call(path, body);
  if (!answer.ok) mark(step, "bad", answer.detail);
  return answer;
}
