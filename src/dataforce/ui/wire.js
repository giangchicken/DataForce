// adapter · one call to the service, and one reading of what came back. Owns no id.

const API = "/text2text/tool-decision";

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
