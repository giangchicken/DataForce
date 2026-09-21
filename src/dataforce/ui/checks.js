// adapter · the two checks, the button that spends each one, and the row it reports on.
// Owns run-detect, run-review, run-note, said-2, said-6.

import { $, say, sayVerdict } from "./screen.js";
import { call } from "./wire.js";

const CHECKS = [
  { step: 2, what: "Personal data", said: "said-2" },
  { step: 6, what: "Label", said: "said-6" }
];

const checked = {};

export function mark(step, state, text) {
  checked[step] = { state, text };
  paintChecks();
}

export function paintChecks() {
  for (const { step, said } of CHECKS) {
    const at = checked[step] || { state: "", text: "not run" };
    const kind = { answered: "ok", bad: "bad", unasked: "bad", wait: "busy", edited: "ok" }[at.state] || "";
    sayVerdict(said, at.text || "not run", kind);
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

export function askable(can, why, kind = "") {
  $("run-review").disabled = !can;
  say("run-note", why, kind);
}

export function forgetChecks() {
  for (const step of CHECKS.map(one => one.step)) delete checked[step];
  paintChecks();
}
