let currentJobId = null;
let pollTimer = null;

// Entitástípus → megjelenési szín mapping
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

function renderEntities(entities) {
  const container = document.getElementById("entityPanel");
  if (!container) return;

  if (!entities || entities.length === 0) {
    container.innerHTML = "<p class=\"muted\">Nincs entitásadat ebben az időablakban.</p>";
    return;
  }

  // Típusonkénti csoportosítás
  const byType = {};
  for (const ent of entities) {
    if (!byType[ent.entity_type]) byType[ent.entity_type] = [];
    byType[ent.entity_type].push(ent);
  }

  let html = "";
  for (const [type, items] of Object.entries(byType)) {
    const colors = TYPE_COLORS[type] || { bg: "#1e293b", border: "#475569", label: type };
    html += `<div class="entity-group">
      <div class="entity-type-label" style="color:${colors.border}">${colors.label}</div>
      <div class="entity-tags">`;
    for (const ent of items) {
      const pct = Math.round(ent.avg_score * 100);
      html += `<span class="entity-tag" style="background:${colors.bg};border-color:${colors.border}" title="${ent.count}× előfordulás, ${pct}% konfidencia">
        ${ent.entity_text}
        <span class="entity-count">${ent.count}</span>
      </span>`;
    }
    html += `</div></div>`;
  }
  container.innerHTML = html;
}

async function loadTopEntities(window) {
  try {
    const res = await fetch(`/top-entities?window=${window}`);
    if (!res.ok) return;
    const data = await res.json();
    renderEntities(data);
  } catch (e) {
    // Csendesen kezeljük – az entitáspanel nem kritikus
  }
}

function applyStatus(data) {
  document.getElementById("fill").style.width = `${data.progress || 0}%`;
  document.getElementById("statusText").innerText =
    `${data.message || "Várakozás"} (${data.progress || 0}%)`;
  document.getElementById("jobPill").innerText = currentJobId
    ? `Feladat: ${currentJobId.slice(0, 8)}`
    : "Nincs aktív feladat";

  const stats = data.stats || {};
  setStat("rssCount",         stats.rss_count);
  setStat("newCount",         stats.new_urls);
  setStat("cacheCount",       stats.cache_hits);
  setStat("scrapedCount",     stats.scraped_ok);
  setStat("dupCount",         stats.duplicates_removed);
  setStat("translationCount", stats.translation_count);
  setStat("nerOkCount",       stats.ner_ok);
  setStat("nerErrCount",      stats.ner_errors);
  setStat("usedCount",        stats.used_for_summary);
  setStat("errorCount",       stats.scrape_errors);

  document.getElementById("errorText").innerText = data.error || "";

  if (data.html) {
    document.getElementById("resultFrame").srcdoc = data.html;
  }

  if (data.stage === "done" || data.stage === "error") {
    document.getElementById("runBtn").disabled = false;
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }

    // Entitások betöltése a job végén
    if (data.stage === "done") {
      const windowValue = document.getElementById("window").value;
      loadTopEntities(windowValue);
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
