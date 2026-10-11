// Thin client: all content is inserted with textContent / text nodes (never innerHTML),
// because prior-recommendation text is external data.

const $ = (id) => document.getElementById(id);

const LABELS = {
  source_text: ["Source text", "source"],
  model_synthesis: ["Model interpretation", "synth"],
  for_human_review: ["Inference: for human review", "review"],
};

const EXAMPLES = [
  "The Lebanese authorities should strengthen judicial independence.",
  "Parliament should adopt legislation protecting judges from political interference.",
  "The government must ensure the investigation is completed without interference.",
];

const state = { data: null, filter: null, controller: null, lastOverrides: {} };

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = text;
  return e;
}

const pretty = (s) => String(s).replaceAll("_", " ");

function tag(provenance) {
  const [label, cls] = LABELS[provenance] || [pretty(provenance), "synth"];
  return el("span", `tag ${cls}`, label);
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

function quoteBox(kind, label, text) {
  const box = el("div", `q ${kind}`);
  box.append(el("span", "q-label", label), el("span", "q-text", `“${text}”`));
  return box;
}

function renderDifference(d) {
  const li = el("li", d.method === "llm" ? "diff" : "diff model");
  const head = el("div", "diff-head");
  head.append(
    el("span", "diff-dim", pretty(d.dimension)),
    tag(d.provenance),
    el("span", "tag method", d.method === "deterministic" ? "Computed by code" : "Judged by model"),
  );
  li.append(head, el("p", null, d.observation));
  if (d.draft_quote || d.prior_quote) {
    const cmp = el("div", "compare");
    if (d.draft_quote) cmp.append(quoteBox("draft", "Your draft", d.draft_quote));
    if (d.prior_quote) cmp.append(quoteBox("prior", "Prior HRW wording", d.prior_quote));
    li.append(cmp);
    li.append(el(
      "div",
      `verify ${d.quotes_verified ? "ok" : "bad"}`,
      d.quotes_verified ? "✓ Quotes verified against the text" : "⚠ Quotes NOT verified against the text",
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
  card.style.animationDelay = `${Math.min(index, 6) * 50}ms`;

  const pct = Math.round(p.relevance * 100);
  const rank = el("div", "rank");
  const meter = el("div", "meter");
  meter.setAttribute("role", "img");
  meter.setAttribute("aria-label", `Retrieval relevance ${pct} percent`);
  const bar = el("i");
  bar.style.width = `${pct}%`;
  meter.append(bar);
  rank.append(el("span", "rank-num", `#${index + 1}`), meter, el("span", "rel-text", `${pct}% relevance`));

  const matched = el("div", "matched", p.matched_dimensions.length ? "Matched on" : "");
  p.matched_dimensions.forEach((m) => matched.append(el("span", "tag plain", pretty(m))));

  const top = el("div", "card-top");
  top.append(rank, matched);

  const body = el("div", "card-body");

  // Source text: verbatim, visually separate from model interpretation below.
  const source = el("div");
  const label = el("div", "section-label");
  label.append(tag("source_text"), document.createTextNode("Verbatim HRW wording"));
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
  source.append(label, block);

  const meta = el("dl", "meta");
  metaItem(meta, "Target actor", r.target_actor || r.target_actor_raw,
    r.target_actor_raw && r.target_actor && r.target_actor_raw !== r.target_actor ? `As written: ${r.target_actor_raw}` : null);
  metaItem(meta, "Requested action", r.action_requested);
  metaItem(meta, "Topic", (r.topic || []).join(", "));
  metaItem(meta, "Geography", (r.geography || []).join(", "));

  body.append(source, meta);

  if (r.source_context) {
    const ctx = el("details", "context");
    ctx.append(el("summary", null, "Source context"), el("p", null, r.source_context));
    body.append(ctx);
  }

  if (p.differences.length) {
    const sec = el("div", "diff-section");
    const l = el("div", "section-label");
    l.append(tag("model_synthesis"), document.createTextNode(`Possible differences from your draft (${p.differences.length})`));
    const ul = el("ul", "diffs");
    p.differences.forEach((d) => ul.append(renderDifference(d)));
    sec.append(l, ul);
    body.append(sec);
  }

  card.append(top, body);
  return card;
}

function visiblePrecedents() {
  const list = state.data.precedents.filter((p) =>
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
  const dims = [...new Set(state.data.precedents.flatMap((p) => p.differences.map((d) => d.dimension)))];
  const box = $("filters");
  box.replaceChildren();
  if (dims.length < 2) return;
  [null, ...dims].forEach((dim) => {
    const b = el("button", "chip", dim ? pretty(dim) : "All");
    b.type = "button";
    b.setAttribute("aria-pressed", String(state.filter === dim));
    b.addEventListener("click", () => { state.filter = dim; renderFilters(); renderResults(); });
    box.append(b);
  });
}

function renderResults() {
  const results = $("results");
  const list = visiblePrecedents();
  $("results-count").textContent = list.length === state.data.precedents.length
    ? String(list.length) : `${list.length} of ${state.data.precedents.length}`;
  results.replaceChildren();
  if (!list.length) {
    results.append(el("p", "status info", state.data.precedents.length
      ? "No precedents match this filter." : "No relevant prior recommendations were found."));
    return;
  }
  list.forEach((p, i) => results.append(renderPrecedent(p, i)));
}

function render(data) {
  state.data = data;
  state.filter = null;
  $("empty").hidden = true;
  $("mock-banner").hidden = !data.is_mock;
  $("notice").hidden = !data.notice;
  $("notice-text").textContent = data.notice || "";
  $("parse").hidden = false;
  $("p-actor").value = data.draft.target_actor || "";
  $("p-topic").value = (data.draft.topic || []).join(", ");
  $("p-geo").value = (data.draft.geography || []).join(", ");
  $("results-wrap").hidden = false;
  renderFilters();
  renderResults();
}

function showSkeleton() {
  const results = $("results");
  $("results-wrap").hidden = false;
  $("empty").hidden = true;
  $("results-count").textContent = "";
  $("filters").replaceChildren();
  results.replaceChildren();
  for (let i = 0; i < 2; i++) {
    const s = el("div", "skeleton");
    s.setAttribute("aria-hidden", "true");
    ["40%", "100%", "92%", "70%"].forEach((w) => { const b = el("div", "sk"); b.style.width = w; s.append(b); });
    results.append(s);
  }
}

function setStatus(kind, text, retry) {
  const s = $("status");
  s.className = `status ${kind || ""}`;
  s.replaceChildren();
  if (!text) return;
  s.append(el("span", null, text));
  if (retry) {
    const b = el("button", "btn secondary small", "Try again");
    b.type = "button";
    b.addEventListener("click", retry);
    s.append(b);
  }
}

function setBusy(busy) {
  ["check", "recheck"].forEach((id) => { $(id).disabled = busy; });
  const label = $("check").querySelector(".btn-label");
  const old = $("check").querySelector(".spinner");
  if (busy && !old) $("check").prepend(el("span", "spinner"));
  if (!busy && old) old.remove();
  label.textContent = busy ? "Checking…" : "Check against previous HRW recommendations";
}

async function run(overrides = {}) {
  const draft = $("draft").value.trim();
  if (!draft) {
    setStatus("error", "Enter a draft recommendation first.");
    $("draft").focus();
    return;
  }
  state.lastOverrides = overrides;
  if (state.controller) state.controller.abort();
  const controller = (state.controller = new AbortController());
  setStatus("info", "");
  setBusy(true);
  if (!state.data) showSkeleton();
  try {
    const res = await fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft_text: draft, ...overrides }),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`The server responded with HTTP ${res.status}`);
    render(await res.json());
    $("parse").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (err) {
    if (err.name === "AbortError") return;
    if (state.data) renderResults(); else { $("results-wrap").hidden = true; $("empty").hidden = false; }
    setStatus("error", `Request failed: ${err.message}.`, () => run(state.lastOverrides));
  } finally {
    if (state.controller === controller) setBusy(false);
  }
}

function syncComposer() {
  const n = $("draft").value.length;
  $("count").textContent = `${n} / 4000`;
  $("clear").hidden = n === 0;
}

EXAMPLES.forEach((text) => {
  const b = el("button", "example", text.length > 58 ? `${text.slice(0, 55)}…` : text);
  b.type = "button";
  b.title = text;
  b.addEventListener("click", () => { $("draft").value = text; syncComposer(); $("draft").focus(); });
  $("examples").append(b);
});

$("check").addEventListener("click", () => run({}));
$("recheck").addEventListener("click", () => run({
  target_actor: $("p-actor").value.trim() || null,
  topic: $("p-topic").value.split(",").map((s) => s.trim()).filter(Boolean),
}));
$("clear").addEventListener("click", () => { $("draft").value = ""; syncComposer(); $("draft").focus(); });
$("draft").addEventListener("input", syncComposer);
$("draft").addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); run({}); }
});
$("sort").addEventListener("change", () => state.data && renderResults());
syncComposer();
