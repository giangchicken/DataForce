// adapter · one call to the service, and one reading of what came back.
//
// Two decisions live here and nowhere else: what a route answers, and what a refusal reads as.
// Everything that draws calls through `ask` or `call`, so no panel holds a second idea of either
// -- and a refusal is the service's own sentence, never paraphrased and never retried, because a
// second call is a person pressing the button again.
//
// This module owns no id. It never touches the page.

const API = "/text2text/tool-decision";

// One call, and one reading of what came back.
export async function ask(path, how) {
  let resp;
  try {
    resp = await fetch(API + path, how);
  } catch (error) {
    return { ok: false, detail: `no answer from the service: ${error}` };
  }
  const text = await resp.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (resp.ok) return { ok: true, data };
  const detail = data && data.detail !== undefined ? data.detail : data;
  return { ok: false, detail: `${resp.status} — ${sayDetail(detail)}` };
}

// What a refusal reads as. A sentence is the service's own and is passed through untouched.
//
// **A body the service could not read is not a sentence.** FastAPI answers one with a list of
// `{loc, msg, input}`, and `input` is *the whole sample echoed back* -- so dumping it prints the
// entire conversation into a cell and buries the one thing a person can act on. Which field, and
// what was wrong with it, is the whole of what they need.
//
// Kept here rather than exported: reading a refusal is what `ask` does, and a panel that read one
// for itself would be a second answer to a question this module already answers.
function sayDetail(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length && detail.every(one => one && one.msg)) {
    return detail.map(one =>
      `${(one.loc || []).filter(at => at !== "body").join(".") || "the body"}: ${one.msg}`).join("; ");
  }
  return JSON.stringify(detail, null, 2);
}

export const call = (path, body) => ask(path, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body)
});
