// Thin client: all content is inserted with textContent / text nodes (never innerHTML),
// because prior-recommendation text and uploaded documents are external data.

const $ = (id) => document.getElementById(id);

// "scope" is shown as "topic" so the UI uses one term; the API dimension name is unchanged.
const DIMENSION_LABELS = { scope: "topic" };
const pretty = (s) => String(s).replaceAll("_", " ");
const dimLabel = (d) => DIMENSION_LABELS[d] || pretty(d);
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
const MAX_DRAFT_CHARS = 20000;
const CONCURRENCY = 3;
const REQUEST_TIMEOUT_MS = 60000;

const LIST_EXAMPLE = [
  "1. The Lebanese authorities should strengthen judicial independence.",
  "2. Parliament should adopt legislation protecting judges from political interference.",
  "3. The government must ensure the investigation is completed without interference.",
].join("\n");

const EXAMPLES = [
  { label: "One recommendation", text: "The Lebanese authorities should strengthen judicial independence." },
  { label: "List of three", text: LIST_EXAMPLE },
];

// One item per input recommendation: status is pending | loading | done | error.
const state = { items: [], filter: null, running: false, nextId: 1 };

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = text;
  return e;
}

function icon(path, size = 16) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  const p = document.createElementNS(ns, "path");
  p.setAttribute("d", path);
  svg.append(p);
  return svg;
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

// Build text with <mark> around each quote that literally occurs in `text`.
function highlighted(text, quotes) {
  const frag = document.createDocumentFragment();
  const spans = [];
  quotes.filter(Boolean).forEach((q) => {
    const i = text.indexOf(q);
    if (i >= 0) spans.push([i, i + q.length]);
  });
  spans.sort((a, b) => a[0] - b[0]);
  let pos = 0;
  spans.forEach(([s, e]) => {
    if (s < pos) return; // overlapping: skip
    frag.append(document.createTextNode(text.slice(pos, s)));
    frag.append(el("mark", null, text.slice(s, e)));
    pos = e;
  });
  frag.append(document.createTextNode(text.slice(pos)));
  return frag;
}

// --- Precedent cards -------------------------------------------------------

function quoteBox(kind, label, text) {
  const box = el("div", `q ${kind}`);
  box.append(el("span", "q-label", label), el("span", "q-text", `“${text}”`));
  return box;
}

function renderDifference(d) {
  const li = el("li", "diff");
  const head = el("div", "diff-head");
  head.append(
    el("span", "diff-dim", dimLabel(d.dimension)),
    el("span", "diff-method", d.method === "deterministic" ? "Computed by code" : "Judged by model"),
  );
  li.append(head, el("p", null, d.observation));
  if (d.draft_quote || d.prior_quote) {
    const cmp = el("div", "compare");
    if (d.draft_quote) cmp.append(quoteBox("draft", "Your draft", d.draft_quote));
    if (d.prior_quote) cmp.append(quoteBox("prior", "Prior HRW wording", d.prior_quote));
    li.append(cmp);
    li.append(el(
      "div",
      `verify ${d.quotes_verified ? "" : "bad"}`,
      d.quotes_verified ? "Quotes verified against the text" : "⚠ Quotes NOT verified against the text",
    ));
  }
  return li;
}

function citation(r) {
  return [
    `"${r.recommendation_text}"`,
    `${r.document_title}${r.document_type ? ` (${pretty(r.document_type)})` : ""}`,
    r.publication_date ? formatDate(r.publication_date) : null,
    r.source_url || null,
  ].filter(Boolean).join(", ");
}

function copyButton(r) {
  const b = el("button", "btn ghost small", "Copy citation");
  b.type = "button";
  b.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(citation(r));
      b.textContent = "Copied";
    } catch {
      b.textContent = "Copy failed";
    }
    setTimeout(() => { b.textContent = "Copy citation"; }, 1500);
  });
  return b;
}

function metaItem(dl, k, v, sub) {
  if (!v) return;
  const dd = el("dd", null, v);
  if (sub) dd.append(el("span", "sub", sub));
  const wrap = el("div");
  wrap.append(el("dt", null, k), dd);
  dl.append(wrap);
}

function renderPrecedent(p, index) {
  const r = p.recommendation;
  const card = el("article", "card");

  const pct = Math.round(p.relevance * 100);
  const rank = el("div", "rank");
  const meter = el("div", "meter");
  meter.setAttribute("role", "img");
  meter.setAttribute("aria-label", `Retrieval relevance ${pct} percent`);
  const bar = el("i");
  bar.style.width = `${pct}%`;
  meter.append(bar);
  rank.append(el("span", "rank-num", `#${index + 1}`), meter, el("span", "rel-text", `${pct}% relevance`));

  // Source text: verbatim, visually separate from model interpretation below.
  const source = el("div");
  const block = el("div", "source-block");
  const quote = el("blockquote");
  quote.append(highlighted(r.recommendation_text, p.differences.map((d) => d.prior_quote)));
  const cite = el("div", "cite");
  cite.append(el("span", "doc", r.document_title));
  const dimline = [r.document_type && pretty(r.document_type), formatDate(r.publication_date)].filter(Boolean).join(" · ");
  if (dimline) cite.append(el("span", "dim", dimline));
  cite.append(el("span", "spacer"));
  cite.append(copyButton(r));
  if (r.source_url) {
    cite.append(Object.assign(el("a", "src", "Open original publication ↗"), {
      href: r.source_url, target: "_blank", rel: "noopener noreferrer",
    }));
  } else {
    cite.append(el("span", "src disabled", "No source link (placeholder record)"));
  }
  block.append(quote, cite);
  source.append(el("div", "section-label", "Verbatim HRW wording"), block);

  const meta = el("dl", "meta");
  metaItem(meta, "Target actor", r.target_actor || r.target_actor_raw,
    r.target_actor_raw && r.target_actor && r.target_actor_raw !== r.target_actor ? `As written: ${r.target_actor_raw}` : null);
  metaItem(meta, "Requested action", r.action_requested);
  metaItem(meta, "Topic", (r.topic || []).join(", "));
  metaItem(meta, "Geography", (r.geography || []).join(", "));

  const parts = [rank, source, meta];

  if (p.differences.length) {
    const sec = el("div", "diff-section");
    const l = el("div", "section-label", `Model interpretation: possible differences from your draft (${p.differences.length})`);
    const ul = el("ul", "diffs");
    p.differences.forEach((d) => ul.append(renderDifference(d)));
    sec.append(l, ul);
    parts.push(sec);
  }

  card.append(...parts);
  return card;
}

// --- Filter and sort (global) ----------------------------------------------

function visiblePrecedents(item) {
  const list = item.data.precedents.filter((p) =>
    !state.filter || p.differences.some((d) => d.dimension === state.filter));
  const by = $("sort").value;
  const date = (p) => p.recommendation.publication_date || "";
  const sorters = {
    relevance: (a, b) => b.relevance - a.relevance,
    newest: (a, b) => date(b).localeCompare(date(a)),
    oldest: (a, b) => date(a).localeCompare(date(b)),
    differences: (a, b) => b.differences.length - a.differences.length,
  };
  return [...list].sort(sorters[by]);
}

function renderFilters() {
  const dims = [...new Set(state.items
    .filter((i) => i.status === "done")
    .flatMap((i) => i.data.precedents.flatMap((p) => p.differences.map((d) => d.dimension))))];
  if (state.filter && !dims.includes(state.filter)) state.filter = null;
  const box = $("filters");
  box.replaceChildren();
  if (dims.length < 2) return;
  [null, ...dims].forEach((dim) => {
    const b = el("button", "chip", dim ? dimLabel(dim) : "All");
    b.type = "button";
    b.setAttribute("aria-pressed", String(state.filter === dim));
    b.addEventListener("click", () => { state.filter = dim; renderFilters(); updateAll(); });
    box.append(b);
  });
}

// --- Recommendation sections -----------------------------------------------

function itemIndex(item) { return state.items.indexOf(item) + 1; }

function renderHead(item) {
  const head = item.head;
  head.replaceChildren();

  const chevron = icon("M9 6l6 6-6 6", 18);
  chevron.setAttribute("class", "chevron");
  const num = el("span", "item-num", String(itemIndex(item)));
  const main = el("div", "item-main");
  main.append(el("div", "item-title", item.text));

  const meta = el("div", "item-meta");
  if (item.status === "pending") {
    meta.append(el("span", "item-state", "Waiting"));
  } else if (item.status === "loading") {
    meta.append(el("span", "spinner small"), el("span", "item-state", "Checking…"));
  } else if (item.status === "error") {
    meta.append(el("span", "item-state bad", "Could not be checked"));
  } else {
    const all = item.data.precedents;
    const vis = visiblePrecedents(item);
    const diffs = vis.reduce((n, p) => n + p.differences.length, 0);
    meta.append(el("span", "item-state", vis.length === all.length
      ? plural(all.length, "prior recommendation", "prior recommendations")
      : `${vis.length} of ${plural(all.length, "prior recommendation", "prior recommendations")}`));
    if (diffs) {
      meta.append(el("span", "item-state strong", plural(diffs, "possible difference", "possible differences")));
      const dims = [...new Set(vis.flatMap((p) => p.differences.map((d) => d.dimension)))];
      dims.slice(0, 4).forEach((d) => meta.append(el("span", "tag", dimLabel(d))));
      if (dims.length > 4) meta.append(el("span", "tag", `+${dims.length - 4}`));
    } else if (all.length) {
      meta.append(el("span", "item-state", "No differences noted"));
    }
  }
  main.append(meta);
  head.append(chevron, num, main);
}

const splitList = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);

function field(label, input, hint) {
  const wrap = el("label", "field");
  const span = el("span", null, label);
  if (hint) span.append(" ", el("em", null, hint));
  wrap.append(span, input);
  return wrap;
}

function textInput(value) {
  const i = el("input");
  i.type = "text";
  i.value = value;
  i.autocomplete = "off";
  return i;
}

function renderRefine(item) {
  const d = item.data.draft;
  const actorOrig = d.target_actor || "";
  const topicOrig = (d.topic || []).join(", ");
  const geoOrig = (d.geography || []).join(", ");

  const box = el("div", "refine");
  const head = el("div", "refine-head");
  head.append(
    el("span", "section-label", "How the system understood this recommendation"),
    el("span", "hint", "Model-generated. Correct anything that is wrong."),
  );

  const wording = el("textarea");
  wording.rows = 2;
  wording.value = item.text;
  wording.maxLength = 4000;
  const actor = textInput(actorOrig);
  const topic = textInput(topicOrig);
  const geo = textInput(geoOrig);

  const rerun = el("button", "btn outline small", "Re-run with my edits");
  rerun.type = "button";
  rerun.addEventListener("click", () => {
    const text = wording.value.trim();
    if (!text) { wording.focus(); return; }
    // Only send fields the user actually changed, so an edited wording is re-parsed fresh.
    const overrides = {};
    if (actor.value.trim() !== actorOrig) overrides.target_actor = actor.value.trim() || null;
    if (topic.value.trim() !== topicOrig) overrides.topic = splitList(topic.value);
    if (geo.value.trim() !== geoOrig) overrides.geography = splitList(geo.value);
    item.text = text;
    item.overrides = overrides;
    checkItem(item);
  });
  const remove = removeButton(item);
  const actions = el("div", "refine-actions");
  actions.append(remove, rerun);

  const grid = el("div", "parse-grid");
  grid.append(field("Target actor", actor), field("Topic", topic, "(comma separated)"), field("Geography", geo, "(comma separated)"));
  box.append(head, field("Wording", wording), grid, actions);
  return box;
}

function removeButton(item) {
  const b = el("button", "btn ghost small", "Remove from review");
  b.type = "button";
  b.addEventListener("click", () => {
    state.items = state.items.filter((i) => i !== item);
    renderItems();
  });
  return b;
}

function renderBody(item) {
  const body = item.body;
  body.replaceChildren();

  if (item.status === "pending" || item.status === "loading") {
    const s = el("div", "skeleton");
    s.setAttribute("aria-hidden", "true");
    ["40%", "100%", "92%", "70%"].forEach((w) => { const b = el("div", "sk"); b.style.width = w; s.append(b); });
    body.append(s);
    return;
  }

  if (item.status === "error") {
    const err = el("div", "status error");
    err.append(el("span", null, `Request failed: ${item.error}.`));
    const retry = el("button", "btn outline small", "Try again");
    retry.type = "button";
    retry.addEventListener("click", () => checkItem(item));
    err.append(retry);
    body.append(err, el("div", "refine-actions solo"));
    body.lastChild.append(removeButton(item));
    return;
  }

  body.append(renderRefine(item));
  item.resultsNode = el("div", "results");
  fillResults(item);
  body.append(item.resultsNode);
}

function fillResults(item) {
  const list = visiblePrecedents(item);
  const results = item.resultsNode;
  results.replaceChildren();
  if (!list.length) {
    results.append(el("p", "status info", item.data.precedents.length
      ? "No precedents match the current filter."
      : "No relevant prior recommendations were found."));
    return;
  }
  list.forEach((p, i) => results.append(renderPrecedent(p, i)));
}

function updateItem(item) {
  if (!item.node) return;
  renderHead(item);
  renderBody(item);
}

// Sort and filter changes refresh headers and precedent lists only, so text the user has
// typed into a section's edit fields is not lost.
function updateAll() {
  state.items.forEach((item) => {
    if (item.status === "done" && item.resultsNode) {
      renderHead(item);
      fillResults(item);
    } else {
      updateItem(item);
    }
  });
}

function buildItem(item) {
  const d = el("details", "item");
  d.open = item.open;
  d.addEventListener("toggle", () => { item.open = d.open; });
  item.head = el("summary", "item-head");
  item.body = el("div", "item-body");
  d.append(item.head, item.body);
  item.node = d;
  updateItem(item);
  return d;
}

function renderItems() {
  const box = $("items");
  box.replaceChildren(...state.items.map(buildItem));
  $("results-wrap").hidden = state.items.length === 0;
  $("empty").hidden = state.items.length > 0;
  $("results-count").textContent = state.items.length ? String(state.items.length) : "";
  renderFilters();
}

function refreshGlobals() {
  const done = state.items.filter((i) => i.status === "done");
  $("mock-banner").hidden = !done.some((i) => i.data.is_mock);
  const notice = done.map((i) => i.data.notice).find(Boolean);
  $("notice").hidden = !notice;
  $("notice-text").textContent = notice || "";
  renderFilters();
}

// --- Requests ---------------------------------------------------------------

function setStatus(kind, text, retry) {
  const s = $("status");
  s.className = `status ${kind || ""}`;
  s.replaceChildren();
  if (!text) return;
  s.append(el("span", null, text));
  if (retry) {
    const b = el("button", "btn outline small", "Try again");
    b.type = "button";
    b.addEventListener("click", retry);
    s.append(b);
  }
}

function setBusy(busy) {
  state.running = busy;
  $("check").disabled = busy;
  const label = $("check").querySelector(".btn-label");
  const old = $("check").querySelector(".spinner");
  if (busy && !old) $("check").prepend(el("span", "spinner"));
  if (!busy && old) old.remove();
  label.textContent = busy ? "Checking…" : "Check against previous HRW recommendations";
}

async function checkItem(item) {
  item.status = "loading";
  item.error = null;
  updateItem(item);
  try {
    const res = await fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft_text: item.text, ...item.overrides }),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
    if (!res.ok) throw new Error(`The server responded with HTTP ${res.status}`);
    item.data = await res.json();
    item.status = "done";
  } catch (err) {
    item.status = "error";
    item.error = err.name === "TimeoutError" ? "The request timed out" : err.message;
  }
  if (!state.items.includes(item)) return; // removed while the request was running
  updateItem(item);
  refreshGlobals();
  // Header counts of other items depend on the filter set, which may have changed.
  state.items.forEach((i) => { if (i !== item && i.status === "done") renderHead(i); });
}

async function runPool(items) {
  const queue = [...items];
  const worker = async () => {
    while (queue.length) {
      const item = queue.shift();
      if (state.items.includes(item)) await checkItem(item);
    }
  };
  await Promise.all(Array.from({ length: Math.min(CONCURRENCY, queue.length) }, worker));
}

async function run() {
  const text = $("draft").value.trim();
  if (!text) {
    setStatus("error", "Enter at least one recommendation first.");
    $("draft").focus();
    return;
  }
  setStatus("info", "");
  setBusy(true);
  try {
    const res = await fetch("/api/split", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error(`The server responded with HTTP ${res.status}`);
    const { recommendations, truncated } = await res.json();
    state.filter = null;
    state.items = recommendations.map((t) => ({
      id: state.nextId++, text: t, status: "pending", data: null, error: null, overrides: {},
      open: recommendations.length === 1,
    }));
    renderItems();
    $("results-wrap").scrollIntoView({ behavior: "smooth", block: "start" });
    if (truncated) setStatus("info", `Only the first ${recommendations.length} recommendations are checked.`);
    await runPool(state.items);
  } catch (err) {
    setStatus("error", `Request failed: ${err.message}.`, run);
  } finally {
    setBusy(false);
  }
}

// --- Composer ---------------------------------------------------------------

function syncComposer() {
  const n = $("draft").value.length;
  $("count").textContent = n > 2000 ? `${n.toLocaleString("en-GB")} / ${MAX_DRAFT_CHARS.toLocaleString("en-GB")}` : "";
  $("clear").hidden = n === 0;
}

function setDraft(text) {
  const clipped = text.length > MAX_DRAFT_CHARS;
  $("draft").value = clipped ? text.slice(0, MAX_DRAFT_CHARS) : text;
  syncComposer();
  $("draft").focus();
  return clipped;
}

// --- File upload --------------------------------------------------------------
// The file is posted as a raw body; the server returns its paragraphs and stores nothing.

function setUploadStatus(kind, text) {
  const s = $("upload-status");
  s.hidden = !text;
  s.className = `upload-status ${kind || ""}`;
  s.textContent = text || "";
}

function loaded(name, count, clipped) {
  if (clipped) setUploadStatus("error", `Loaded from ${name}, but the text exceeded ${MAX_DRAFT_CHARS.toLocaleString("en-GB")} characters and was shortened. Please check it.`);
  else setUploadStatus("", `Loaded ${plural(count, "paragraph", "paragraphs")} from ${name}.`);
}

function closePicker() {
  $("picker").hidden = true;
  $("picker-list").replaceChildren();
}

function pickerBoxes() { return [...$("picker-list").querySelectorAll("input[type=checkbox]")]; }

function syncPicker() {
  const boxes = pickerBoxes();
  const n = boxes.filter((b) => b.checked).length;
  $("picker-add").disabled = n === 0;
  $("picker-add").textContent = n ? `Add selected (${n})` : "Add selected";
  $("picker-all").textContent = n === boxes.length ? "Select none" : "Select all";
}

function showPicker(name, paragraphs) {
  $("picker").dataset.name = name;
  $("picker-title").textContent = `${paragraphs.length} paragraphs found in ${name}. Select the recommendations to check.`;
  const list = $("picker-list");
  list.replaceChildren();
  paragraphs.forEach((text) => {
    const label = el("label", "picker-item");
    const box = el("input");
    box.type = "checkbox";
    box.value = text;
    box.addEventListener("change", syncPicker);
    label.append(box, el("span", null, text));
    const li = el("li");
    li.append(label);
    list.append(li);
  });
  syncPicker();
  $("picker").hidden = false;
}

async function handleFile(file) {
  closePicker();
  if (!file) return;
  if (!/\.(docx|pptx|pdf|txt)$/i.test(file.name)) {
    setUploadStatus("error", "Supported file types are .docx, .pptx, .pdf and .txt. Older .doc and .ppt files can be re-saved in the newer format.");
    return;
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    setUploadStatus("error", "The file is larger than 5 MB.");
    return;
  }
  setUploadStatus("", "Reading document…");
  $("upload").disabled = true;
  try {
    const res = await fetch(`/api/extract?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: file,
    });
    if (!res.ok) {
      let detail = `The server responded with HTTP ${res.status}`;
      try { detail = (await res.json()).detail || detail; } catch { /* keep default */ }
      throw new Error(detail);
    }
    const { paragraphs, truncated } = await res.json();
    if (paragraphs.length === 1) {
      loaded(file.name, 1, setDraft(paragraphs[0]));
    } else {
      setUploadStatus("", truncated ? `Only the first ${paragraphs.length} paragraphs are listed.` : "");
      showPicker(file.name, paragraphs);
    }
  } catch (err) {
    setUploadStatus("error", `Could not read the document: ${err.message}`);
  } finally {
    $("upload").disabled = false;
    $("file").value = "";
  }
}

// --- Wiring -----------------------------------------------------------------

EXAMPLES.forEach(({ label, text }) => {
  const b = el("button", "example", label);
  b.type = "button";
  b.title = text;
  b.addEventListener("click", () => { setDraft(text); });
  $("examples").append(b);
});

$("check").addEventListener("click", run);
$("clear").addEventListener("click", () => { setDraft(""); });
$("draft").addEventListener("input", syncComposer);
$("draft").addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); if (!state.running) run(); }
});
$("sort").addEventListener("change", updateAll);
$("expand-all").addEventListener("click", () => state.items.forEach((i) => { i.open = true; i.node.open = true; }));
$("collapse-all").addEventListener("click", () => state.items.forEach((i) => { i.open = false; i.node.open = false; }));
$("upload").addEventListener("click", () => $("file").click());
$("file").addEventListener("change", (e) => handleFile(e.target.files[0]));
$("picker-close").addEventListener("click", closePicker);
$("picker-all").addEventListener("click", () => {
  const boxes = pickerBoxes();
  const all = boxes.every((b) => b.checked);
  boxes.forEach((b) => { b.checked = !all; });
  syncPicker();
});
$("picker-add").addEventListener("click", () => {
  const picked = pickerBoxes().filter((b) => b.checked).map((b) => b.value);
  const name = $("picker").dataset.name;
  const text = picked.length === 1 ? picked[0] : picked.map((t, i) => `${i + 1}. ${t}`).join("\n");
  closePicker();
  loaded(name, picked.length, setDraft(text));
});
syncComposer();
