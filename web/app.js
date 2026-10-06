// Thin client: all content is inserted with textContent (never innerHTML),
// because prior-recommendation text is external data.

const $ = (id) => document.getElementById(id);

const LABELS = {
  source_text: ["Source text (verbatim HRW wording)", "source"],
  model_synthesis: ["Model interpretation", "synth"],
  for_human_review: ["Inference: for human review", "review"],
};

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = text;
  return e;
}

function tag(provenance) {
  const [label, cls] = LABELS[provenance] || [provenance, "synth"];
  return el("span", `tag ${cls}`, label);
}

function renderDifference(d) {
  const li = el("li", "diff");
  const head = el("div", "diff-head");
  head.append(
    el("strong", null, d.dimension.replaceAll("_", " ")),
    tag(d.provenance),
    el("span", "tag method", d.method === "deterministic" ? "computed by code" : "judged by model"),
  );
  li.append(head, el("p", null, d.observation));
  if (d.draft_quote || d.prior_quote) {
    const q = el("div", "quotes");
    if (d.draft_quote) q.append(el("div", null, `Draft: "${d.draft_quote}"`));
    if (d.prior_quote) q.append(el("div", null, `Prior: "${d.prior_quote}"`));
    q.append(el("div", "verified", d.quotes_verified ? "Quotes verified against text" : "Quotes NOT verified"));
    li.append(q);
  }
  return li;
}

function renderPrecedent(p) {
  const r = p.recommendation;
  const card = el("article", "card");

  const top = el("div", "card-top");
  top.append(
    el("span", "relevance", `Relevance ${(p.relevance * 100).toFixed(0)}%`),
    el("span", "matched", `Matched on: ${p.matched_dimensions.join(", ")}`),
  );

  const quote = el("blockquote", null, r.recommendation_text);
  const meta = el("dl", "meta");
  const add = (k, v) => { if (v) meta.append(el("dt", null, k), el("dd", null, v)); };
  add("Target actor (as written)", r.target_actor_raw);
  add("Target actor (normalised)", r.target_actor);
  add("Topic", r.topic.join(", "));
  add("Geography", r.geography.join(", "));
  add("Published", r.publication_date);
  add("Document", `${r.document_title} (${r.document_type})`);

  const source = r.source_url
    ? Object.assign(el("a", "src", "Open original HRW publication"), { href: r.source_url, target: "_blank", rel: "noopener noreferrer" })
    : el("span", "src disabled", "Source link: none (placeholder record)");

  const ctx = el("details");
  ctx.append(el("summary", null, "Source context"), el("p", null, r.source_context));

  card.append(top, tag("source_text"), quote, meta, source, ctx);

  if (p.differences.length) {
    const ul = el("ul", "diffs");
    p.differences.forEach((d) => ul.append(renderDifference(d)));
    card.append(el("h3", null, "Possible differences from your draft"), ul);
  }
  return card;
}

function render(data) {
  $("mock-banner").hidden = !data.is_mock;
  $("notice").hidden = false;
  $("notice").textContent = data.notice;
  $("parse").hidden = false;
  $("p-actor").value = data.draft.target_actor || "";
  $("p-topic").value = data.draft.topic.join(", ");

  const results = $("results");
  results.replaceChildren(el("h2", null, `Relevant prior recommendations (${data.precedents.length})`));
  data.precedents.forEach((p) => results.append(renderPrecedent(p)));
}

async function run(overrides) {
  const draft = $("draft").value.trim();
  if (!draft) { $("status").textContent = "Enter a draft recommendation first."; return; }
  $("status").textContent = "Checking…";
  try {
    const res = await fetch("/api/check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft_text: draft, ...overrides }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    render(await res.json());
    $("status").textContent = "";
  } catch (err) {
    $("status").textContent = `Request failed: ${err.message}`;
  }
}

$("check").addEventListener("click", () => run({}));
$("recheck").addEventListener("click", () => run({
  target_actor: $("p-actor").value.trim() || null,
  topic: $("p-topic").value.split(",").map((s) => s.trim()).filter(Boolean),
}));
