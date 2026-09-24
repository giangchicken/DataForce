// A DOM small enough to run `ui/app.js` in node, and no smaller.
//
// The repository installs no browser and no `jsdom`, and a page whose behaviour nothing runs is a
// page nobody has checked. So this is the smallest thing app.js will start against: elements that
// remember what was written to them, and a `querySelector` that hands back one stub per selector.
//
// **`innerHTML` is kept as the string it was given, never parsed.** What the checks read is the
// markup the page wrote -- which is the answer under test -- and a parser here would be a second
// definition of HTML to get wrong. The one exception is the tick boxes: `querySelectorAll` has to
// answer with the inputs the page drew, so those are read back out of the markup the page itself
// wrote rather than listed here. A list here would be this file's idea of the facets, and the
// check that the ticks reach the record would pass against a page that draws different ones.
const fs = require("fs");
const path = require("path");
const vm = require("vm");

// `<script type="module">`, as far as node goes without a browser.
//
// A module is not a script. `vm.runInContext` compiles the classic goal, which answers an
// `import` with a syntax error, so each file is compiled on its own here and the specifiers are
// resolved between them: **against the file that wrote one**, which is the rule a browser
// follows, and **cached by the path it resolves to**, so a module two others import is evaluated
// once and what it holds is one state rather than two.
//
// Loading is asynchronous where running a script was not, which is why `build` is awaited. Nothing
// is caught: a module that throws while it is evaluated rejects out of this function and
// takes the run with it, rather than leaving an empty page for every check to pass against.
async function load(entry, context) {
  const made = new Map();
  const compile = identifier => {
    if (!made.has(identifier)) {
      made.set(identifier, new vm.SourceTextModule(fs.readFileSync(identifier, "utf8"), {
        identifier,
        context
      }));
    }
    return made.get(identifier);
  };
  const page = compile(path.resolve(entry));
  await page.link((specifier, from) => {
    // **A browser resolves a relative reference and nothing else.** `import { ask } from
    // "wire.js"` is a bare specifier: a browser refuses it outright, and path resolution would
    // find the file sitting next door and load it. That is a page green here and blank in a
    // browser, with one console line nobody's suite reads. This stands in for a browser, so it
    // refuses what a browser refuses.
    if (!/^\.{0,2}\//.test(specifier)) {
      throw new Error(
        `${path.basename(from.identifier)} imports "${specifier}": a module specifier a browser`
        + ` will resolve starts with "/", "./" or "../"`
      );
    }
    return compile(path.resolve(path.dirname(from.identifier), specifier));
  });
  await page.evaluate();
}

class El {
  constructor(tag = "div", id = "") {
    this.tagName = tag.toUpperCase();
    this.id = id;
    this.className = "";
    this.textContent = "";
    this.html = "";
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.hidden = false;
    this.dataset = {};
    this.parent = null;
    this.children = new Map();
    this.style = { setProperty: (name, value) => { this.style[name] = value; } };
    this.open = false;
    this.files = [];
    this.classList = {
      has: name => this.className.split(/\s+/).includes(name),
      add: name => { if (!this.classList.has(name)) this.className = `${this.className} ${name}`.trim(); },
      remove: name => { this.className = this.className.split(/\s+/).filter(one => one !== name).join(" "); },
      toggle: (name, on) => (on ? this.classList.add(name) : this.classList.remove(name)),
      contains: name => this.classList.has(name)
    };
  }
  // Rewriting markup destroys the elements that were in it, focus included. Modelled, because the
  // page's whole reason for putting focus back is that a browser takes it away here -- and because
  // a stub that kept the old children would answer a lookup with a field the page has replaced.
  set innerHTML(said) {
    this.html = said;
    if (El.focused && [...this.children.values()].includes(El.focused)) El.focused = null;
    this.children.clear();
    const options = this.tagName === "SELECT"
      ? [...said.matchAll(/<option value="([^"]*)"([^>]*)>/g)] : [];
    if (options.length) {
      const picked = options.find(one => one[2].includes("selected")) || options[0];
      this.value = unescaped(picked[1]);
    }
  }
  get innerHTML() { return this.html; }
  focus() { El.focused = this; }
  // One stub per selector, carrying whatever the selector asked for -- and **the value the page
  // wrote into that tag**. A field the page filled in and a stub that hands it back empty is a
  // stub disagreeing with the page about what is on the screen, which fails checks the page passes.
  querySelector(selector) {
    if (!this.children.has(selector)) {
      const child = new El("span");
      child.parent = this;
      const wanted = {};
      for (const asked of selector.matchAll(/\[data-([a-z]+)="([^"]*)"\]/g)) {
        child.dataset[asked[1]] = asked[2];
        wanted[asked[1]] = asked[2];
      }
      const written = findTag(this.markup(), wanted);
      if (written !== null) child.value = written;
      this.children.set(selector, child);
    }
    return this.children.get(selector);
  }
  // Everything written anywhere under this element. The page sets a table's rows on its `tbody`
  // and then looks a cell up from the table, so a search of one element's own markup finds nothing.
  markup() {
    return this.html + [...this.children.values()].map(child => child.markup()).join("");
  }
  querySelectorAll() { return []; }
  // Up the chain this stub actually has: a child made by `querySelector` knows who made it, which
  // is the only `closest` the page asks for.
  closest(selector) {
    const attribute = selector.match(/^\[data-([a-z]+)\]$/);
    const wanted = selector.replace(/^[.#]/, "").toLowerCase();
    for (let at = this; at; at = at.parent) {
      if (attribute) {
        if (at.dataset[attribute[1]] !== undefined) return at;
      } else if (at.tagName.toLowerCase() === wanted || at.classList.has(wanted)) {
        return at;
      }
    }
    return null;
  }
  insertAdjacentHTML(_, said) { this.innerHTML = this.innerHTML + said; }
  scrollIntoView() {}
}

// **What a browser hands back out of an attribute it parsed.** The page escapes everything it
// interpolates into markup -- it has to, a corpus that says `<b>` is a corpus -- and a browser
// reverses that when it reads `.value` back. A stub that returns the raw attribute text hands the
// page `&lt;EMAIL_1&gt;` where the browser hands it `<EMAIL_1>`, and every value that goes out
// through the markup and comes back through a field is a string no browser would produce.
const unescaped = text => text
  .replace(/&lt;/g, "<").replace(/&gt;/g, ">")
  .replace(/&quot;/g, '"').replace(/&amp;/g, "&");

// The `value` of the one tag in this markup carrying every `data-` attribute asked for. `null`
// where there is no such tag, which is not the same as one whose value is the empty string.
function findTag(markup, wanted) {
  const names = Object.keys(wanted);
  if (!names.length) return null;
  for (const tag of markup.matchAll(/<input[^>]*>/g)) {
    const text = tag[0];
    if (!names.every(name => text.includes(`data-${name}="${wanted[name]}"`))) continue;
    const value = text.match(/ value="([^"]*)"/);
    return value ? unescaped(value[1]) : "";
  }
  return null;
}

// A tick box the page drew, read back out of the markup it wrote.
function readTicks(markup) {
  const found = [];
  const pattern = /<input type="(radio|checkbox)" name="([^"]+)"(?: value="([^"]*)")?/g;
  for (let match = pattern.exec(markup); match; match = pattern.exec(markup)) {
    const box = new El("input");
    box.dataset.name = match[2];
    box.name = match[2];
    box.value = match[3] === undefined ? "" : unescaped(match[3]);
    found.push(box);
  }
  return found;
}

// Every id the real page declares. A stub that invents an element for any id it is handed cannot
// tell a live control from a dead one: the page asks for `#paste-now`, the stub hands back a fresh
// object, the handler is attached to nothing, and every check passes against a button that does
// not exist. So the ids come from `index.html`, and asking for one it does not declare throws.
//
// The same file also says which elements *start* hidden. A stub whose every element begins visible
// disagrees with the page about the opening screen, and a check reading `hidden` would be reading
// the stub's default rather than the markup's attribute.
function readPageIds(app) {
  const page = path.join(path.dirname(app), "index.html");
  const html = fs.readFileSync(page, "utf8");
  const declared = new Map();
  for (const tag of html.matchAll(/<([a-z][a-z0-9]*)[^>]*>/gi)) {
    const named = tag[0].match(/ id="([^"]+)"/);
    if (named) {
      declared.set(named[1],
        { tag: tag[1], hidden: / hidden(?=[ >])/.test(tag[0]), value: "" });
    }
  }
  // **A `<select>` answers its first option before anybody picks one.** A stub whose selects start
  // empty disagrees with the markup about the opening screen, and the page reads that value the
  // moment a route is called: `language: ""` to a service that knows only `vi` and `en` is a 422
  // no browser would ever produce, and nothing here would have said so.
  for (const box of html.matchAll(/<select[^>]* id="([^"]+)"[^>]*>([\s\S]*?)<\/select>/g)) {
    const first = box[2].match(/<option value="([^"]*)"/);
    if (first && declared.has(box[1])) declared.get(box[1]).value = first[1];
  }
  return declared;
}

async function build(answers, app) {
  const declared = readPageIds(app);
  El.focused = null;
  const byId = new Map();
  const bySelector = new Map();
  const ticks = new Map();
  const keys = [];
  const asked = [];

  // The tick boxes one element has drawn. Kept while that element's markup is unchanged, so a
  // tick set in a check is still set when the page reads it back -- and **rebuilt the moment it
  // changes**, which is what a browser does to a group of radios whose container is rewritten.
  //
  // Per element and not over the page as a whole, for the same reason: rewriting one container
  // leaves every other container's ticks where they were, and a cache over the joined markup
  // would throw away a model the reviewer picked because a list somewhere else was redrawn.
  const inputsIn = el => {
    const cached = ticks.get(el.id);
    if (!cached || cached.drew !== el.innerHTML) {
      ticks.set(el.id, { drew: el.innerHTML, boxes: readTicks(el.innerHTML) });
    }
    return ticks.get(el.id).boxes;
  };

  const inputsNamed = name =>
    [...byId.values()].flatMap(inputsIn).filter(box => box.name === name);

  const document = {
    getElementById(id) {
      if (!declared.has(id)) {
        throw new Error(
          `index.html declares no #${id}, so this handler would be attached to nothing`
        );
      }
      if (!byId.has(id)) {
        const made = new El(declared.get(id).tag, id);
        made.hidden = declared.get(id).hidden;
        made.value = declared.get(id).value;
        byId.set(id, made);
      }
      return byId.get(id);
    },
    querySelector(selector) {
      const named = selector.match(/^input\[name="([^"]+)"\](:checked)?$/);
      if (named) {
        const boxes = inputsNamed(named[1]);
        return (named[2] ? boxes.find(box => box.checked) : boxes[0]) || null;
      }
      if (!bySelector.has(selector)) bySelector.set(selector, new El("span"));
      return bySelector.get(selector);
    },
    querySelectorAll(selector) {
      const named = selector.match(/^input\[name="([^"]+)"\](:checked)?$/);
      if (named) {
        const boxes = inputsNamed(named[1]);
        return named[2] ? boxes.filter(box => box.checked) : boxes;
      }
      if (selector === "#facet-ticks input") return inputsIn(document.getElementById("facet-ticks"));
      if (selector === "[data-close]") return [];
      return [];
    },
    addEventListener(kind, handler) { keys.push({ kind, handler }); },
    get activeElement() { return El.focused; }
  };

  // What the page asked the *window* for, which is a different thing from what it asked the
  // document for: the window is where coming back to the tab is heard.
  const woken = [];

  // How long a route takes to answer, one delay per call, so a test can make an earlier request
  // land *after* a later one. Nothing else can check that a stale answer is dropped: with every
  // route answering instantly, the order calls are made in is the order they come back in.
  const delays = {};
  const taking = named => {
    delays[named] = delays[named] || [...((answers.slow || {})[named] || [])];
    return delays[named].shift() || 0;
  };

  // Answers handed out one per call, where a test named a list, so two calls to one route can be
  // told apart. A single value answers every call, which is what most checks want.
  const turns = {};
  const answering = (named, said) => {
    if (!Array.isArray(said)) return said;
    turns[named] = (turns[named] || 0) + 1;
    return said[Math.min(turns[named], said.length) - 1];
  };

  // Every route the page can reach, answered from `answers` and recorded in order. A test that
  // wants a route to refuse names it in `answers.refuse`.
  async function fetch(url, how = {}) {
    const path = url.replace("/text2text/tool-decision", "");
    asked.push({ path, method: (how.method || "GET"), body: how.body, headers: how.headers });
    // Chosen now and handed back later, so a route told to be slow answers the call it was *made*
    // for. Picking it after the wait would hand the newest request the oldest answer, which is
    // the very thing the page is being checked for noticing.
    const waiting = taking(path.split("?")[0]);
    const refusal = (answers.refuse || {})[path.split("?")[0]];
    if (refusal) {
      if (waiting) await new Promise(resolve => setTimeout(resolve, waiting));
      return { ok: false, status: refusal.status || 422, text: async () => JSON.stringify({ detail: refusal.detail }) };
    }
    // `/queue/<key>` only. `next` and `import` are the route's own names, not keys -- the same
    // reason the real router declares them before the one that takes a `{key}`.
    const NAMED = ["next", "import"];
    const asKey = path.match(/^\/queue\/([^/]+)$/);
    if (asKey && !NAMED.includes(asKey[1]) && oneQueued(asKey[1]) === null) {
      return { ok: false, status: 404, text: async () => JSON.stringify({ detail: `no queued sample under ${asKey[1]}` }) };
    }
    const named = path.split("?")[0];
    const body = named === "/models" ? answers.models
      : named === "/store" ? (answers.store === undefined
        ? { describes: "store.sqlite3" }
        : answers.store)
      : named === "/records/stats" ? answering(named, answers.statistics)
      : named === "/queue" ? listQueued()
      : named === "/queue/next" ? nextQueued()
      : named === "/queue/import" ? answers.imported
      // Named the way the service names one, not the way the page would: the id comes back in the
      // answer, so a page that made up its own would be caught rather than agreed with.
      : named === "/samples/named" ? (answers.named || nameLines(how.body))
      : asKey && !NAMED.includes(asKey[1]) ? oneQueued(asKey[1])
      // `/records` is two routes on one path: the page posts a record to it and reads the stored
      // corpus back off it, so the method is what tells them apart here as it does in the router.
      : named === "/records" && (how.method || "GET") === "GET"
        ? (answers.dataset || { samples: [], total: 0 })
      // The third thing on one path: the sheet deletes the rows a reviewer ticked. No body comes
      // back from it, so there is nothing here to answer with -- what the page sent is what a
      // check reads, off `asked`.
      : named === "/records" && (how.method || "GET") === "DELETE"
        ? null
      : named === "/records" ? (answers.stored || { id: "r1", created_time: "t", modified_time: "t" })
      : named.startsWith("/records/") ? (answers.datasetOne || null)
      : named.startsWith("/queue/") && named.endsWith("/skip") ? nextQueued()
      : named === "/data-quality/personal-data" ? answers.detected
      : named === "/data-quality/personal-data/classes"
        ? (answers.classes || ["EMAIL", "PHONE", "OTP", "NAME"])
      : named === "/data-quality/personal-data/spans"
        ? answering(named, answers.numbered || answers.detected)
      // Canned, and on purpose: what a callable label is belongs to `label_statistics.py`, and a
      // second reading of that rule here would let this file and the service disagree about the
      // fixture while every check stayed green. What is under test is what the page does with
      // the answer, so a check wanting a broken label sets one.
      : named === "/data-quality/label"
        ? (answers.labelChecked || { schema_valid: true, faults: [] })
      : named === "/data-quality/personal-data/redact" ? answering(named, answers.redacted)
      : named === "/ai-review" ? answers.reviewed
      : null;
    if (waiting) await new Promise(resolve => setTimeout(resolve, waiting));
    return { ok: true, status: 200, text: async () => JSON.stringify(body) };
  }

  // What the naming route answers: every line back, each carrying an `id`. A line that named
  // itself keeps its name, which is the service's rule too.
  const nameLines = (body = "") => {
    const lines = String(body).split("\n").filter(line => line.trim());
    return {
      read: lines.length,
      samples: lines.map((line, at) => {
        const one = JSON.parse(line);
        return { id: `named-by-the-service-${at + 1}`, ...one };
      }),
      unreadable: []
    };
  };

  // The queue hands each sample over once, so *submit opens the next one* is a claim a check can
  // actually make: a queue that answered the same sample every time would pass either way.
  let at = 0;
  const queue = answers.queue || [];
  const keyOf = one => one.id || `k${queue.indexOf(one) + 1}`;
  const counts = () => ({
    waiting: Math.max(0, queue.length - at),
    done: answers.done || 0,
    skipped: answers.skipped || 0
  });
  function nextQueued() {
    const one = queue[at] || null;
    at += 1;
    return { sample: one, key: one ? keyOf(one) : null, ...counts() };
  }
  // One named row, which is how a reviewer opens something they picked out of the list.
  function oneQueued(key) {
    const one = queue.find(each => keyOf(each) === key) || null;
    return one === null ? null : { sample: one, key, ...counts() };
  }
  function listQueued() {
    return {
      samples: queue.map((one, n) => ({
        key: keyOf(one),
        state: (answers.states || {})[keyOf(one)] || "waiting",
        walk_position: n + 1,
        said: ((one.messages || [])[0] || {}).content || ""
      })),
      ...counts()
    };
  }

  const context = {
    document,
    window: { addEventListener: (kind, handler) => woken.push({ kind, handler }) },
    console,
    setTimeout,
    clearTimeout,
    encodeURIComponent,
    fetch
  };
  vm.createContext(context);
  await load(app, context);
  // **A module keeps its own declarations.** A classic script put them in the context's global
  // lexical scope and a check could call one by name; nothing outside a module can, and a browser
  // cannot either -- so a check reaches the page the way a person does, through an element.
  //
  // `byId` holds only what the page has touched. `el` is the same lookup the page makes, so a
  // check can reach a field the page has not needed yet -- a textarea nobody has typed in.
  const el = id => document.getElementById(id);
  // `answers` is handed back so a check can change what a route says part way through a run: a
  // deployment's model directory is edited while the page is open, which is the whole reason the
  // page asks again.
  return { context, byId, bySelector, keys, woken, asked, answers, document, inputsNamed, el };
}

const settled = () => new Promise(resolve => setImmediate(resolve));

// Real time, for the one thing on the page that waits on it: the replacement made while somebody
// is typing an offset. Faking the clock here would be this file deciding what a debounce is.
const waited = ms => new Promise(resolve => setTimeout(resolve, ms));

module.exports = { build, El, settled, waited };
