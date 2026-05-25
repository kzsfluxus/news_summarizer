let currentJobId = null;
let pollTimer = null;

// Entitástípus → megjelenési szín
const TYPE_COLORS = {
  PERSON:   { bg: "#1e3a5f", border: "#3b82f6", label: "Személy" },
  ORG:      { bg: "#1a3a2a", border: "#22c55e", label: "Szervezet" },
  LOCATION: { bg: "#3a2a1a", border: "#f59e0b", label: "Helyszín" },
  EVENT:    { bg: "#3a1a2a", border: "#ec4899", label: "Esemény" },
  PRODUCT:  { bg: "#2a1a3a", border: "#a855f7", label: "Termék" },
};

function setStat(id, value) {
  const el = document.getElementById(id);
  if (el) el.innerText = value ?? 0;
}

// --- Entitás panel ---

function renderEntities(entities) {
  const container = document.getElementById("entityPanel");
  if (!container) return;
  if (!entities || entities.length === 0) {
    container.innerHTML = "<p class=\"muted\">Nincs entitásadat ebben az időablakban.</p>";
    return;
  }
  const byType = {};
  for (const ent of entities) {
    if (!byType[ent.entity_type]) byType[ent.entity_type] = [];
    byType[ent.entity_type].push(ent);
  }
  let html = "";
  for (const [type, items] of Object.entries(byType)) {
    const c = TYPE_COLORS[type] || { bg: "#1e293b", border: "#475569", label: type };
    html += `<div class="entity-group">
      <div class="entity-type-label" style="color:${c.border}">${c.label}</div>
      <div class="tag-row">`;
    for (const ent of items) {
      const pct = Math.round((ent.avg_score ?? ent.score ?? 0) * 100);
      html += `<span class="tag" style="background:${c.bg};border-color:${c.border}"
        title="${ent.count ?? ""}× előfordulás, ${pct}% konfidencia">
        ${ent.entity_text}${ent.count ? `<span class="tag-count">${ent.count}</span>` : ""}
      </span>`;
    }
    html += `</div></div>`;
  }
  container.innerHTML = html;
}

// --- Kulcsszó panel ---

function renderKeywords(keywords) {
  const container = document.getElementById("keywordPanel");
  if (!container) return;
  if (!keywords || keywords.length === 0) {
    container.innerHTML = "<p class=\"muted\">Nincs kulcsszóadat ebben az időablakban.</p>";
    return;
  }
  // Hőtérkép-szerű megjelenítés: magasabb score → erősebb kék
  const maxScore = Math.max(...keywords.map(k => k.avg_score ?? k.score ?? 0));
  let html = "<div class=\"tag-row\">";
  for (const kw of keywords) {
    const score = kw.avg_score ?? kw.score ?? 0;
    const intensity = maxScore > 0 ? score / maxScore : 0;
    const alpha = (0.2 + intensity * 0.6).toFixed(2);
    const pct = Math.round(score * 100);
    html += `<span class="tag kw-tag" style="background:rgba(59,130,246,${alpha});border-color:rgba(99,160,255,${alpha})"
      title="${kw.count ?? ""}× előfordulás, ${pct}% relevancia">
      ${kw.keyword}${kw.count ? `<span class="tag-count">${kw.count}</span>` : ""}
    </span>`;
  }
  html += "</div>";
  container.innerHTML = html;
}

async function loadPanels(window) {
  try {
    const [entRes, kwRes] = await Promise.all([
      fetch(`/top-entities?window=${window}`),
      fetch(`/top-keywords?window=${window}`),
    ]);
    if (entRes.ok) renderEntities(await entRes.json());
    if (kwRes.ok)  renderKeywords(await kwRes.json());
  } catch (e) {
    // Nem kritikus, csendesen kezeljük
  }
}

function applyStatus(data) {
  document.getElementById("fill").style.width = `${data.progress || 0}%`;
  document.getElementById("statusText").innerText =
    `${data.message || "Várakozás"} (${data.progress || 0}%)`;
  document.getElementById("jobPill").innerText = currentJobId
    ? `Feladat: ${currentJobId.slice(0, 8)}`
    : "Nincs aktív feladat";

  const s = data.stats || {};
  setStat("rssCount",         s.rss_count);
  setStat("newCount",         s.new_urls);
  setStat("cacheCount",       s.cache_hits);
  setStat("scrapedCount",     s.scraped_ok);
  setStat("dupCount",         s.duplicates_removed);
  setStat("translationCount", s.translation_count);
  setStat("nerOkCount",       s.ner_ok);
  setStat("nerErrCount",      s.ner_errors);
  setStat("kwOkCount",        s.keyword_ok);
  setStat("kwErrCount",       s.keyword_errors);
  setStat("usedCount",        s.used_for_summary);
  setStat("errorCount",       s.scrape_errors);

  document.getElementById("errorText").innerText = data.error || "";

  if (data.html) {
    document.getElementById("resultFrame").srcdoc = data.html;
  }

  if (data.stage === "done" || data.stage === "error") {
    document.getElementById("runBtn").disabled = false;
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    if (data.stage === "done") {
      loadPanels(document.getElementById("window").value);
    }
  }
}

async function pollStatus() {
  if (!currentJobId) return;
  const res = await fetch(`/status/${currentJobId}`);
  if (!res.ok) return;
  applyStatus(await res.json());
}

async function runJob() {
  document.getElementById("runBtn").disabled = true;
  document.getElementById("errorText").innerText = "";
  document.getElementById("fill").style.width = "0%";
  document.getElementById("statusText").innerText = "Indítás...";

  const windowValue = document.getElementById("window").value;
  const res = await fetch("/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ window: windowValue }),
  });
  const data = await res.json();

  if (data.already_running) {
    document.getElementById("statusText").innerText = "Már fut egy feladat – csatlakozás...";
  }

  currentJobId = data.job_id;
  document.getElementById("jobPill").innerText = `Feladat: ${currentJobId.slice(0, 8)}`;

  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(pollStatus, 1200);
  await pollStatus();
}

document.getElementById("runBtn").addEventListener("click", runJob);
