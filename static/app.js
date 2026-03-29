let currentJobId = null;
let pollTimer = null;

function setStat(id, value) {
  document.getElementById(id).innerText = value ?? 0;
}

function applyStatus(data) {
  document.getElementById('fill').style.width = `${data.progress || 0}%`;
  document.getElementById('statusText').innerText = `${data.message || 'Várakozás'} (${data.progress || 0}%)`;
  document.getElementById('jobPill').innerText = currentJobId ? `Feladat: ${currentJobId.slice(0, 8)}` : 'Nincs aktív feladat';

  const stats = data.stats || {};
  setStat('rssCount', stats.rss_count);
  setStat('newCount', stats.new_urls);
  setStat('cacheCount', stats.cache_hits);
  setStat('scrapedCount', stats.scraped_ok);
  setStat('dupCount', stats.duplicates_removed);
  setStat('translationCount', stats.translation_count);
  setStat('usedCount', stats.used_for_summary);
  setStat('errorCount', stats.scrape_errors);

  document.getElementById('errorText').innerText = data.error || '';

  if (data.html) {
    document.getElementById('resultFrame').srcdoc = data.html;
  }

  if (data.stage === 'done' || data.stage === 'error') {
    document.getElementById('runBtn').disabled = false;
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }
}

async function pollStatus() {
  if (!currentJobId) return;
  const res = await fetch(`/status/${currentJobId}`);
  if (!res.ok) return;
  const data = await res.json();
  applyStatus(data);
}

async function runJob() {
  document.getElementById('runBtn').disabled = true;
  document.getElementById('errorText').innerText = '';
  document.getElementById('fill').style.width = '0%';
  document.getElementById('statusText').innerText = 'Indítás...';

  const windowValue = document.getElementById('window').value;
  const res = await fetch('/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ window: windowValue })
  });
  const data = await res.json();
  currentJobId = data.job_id;
  document.getElementById('jobPill').innerText = `Feladat: ${currentJobId.slice(0, 8)}`;

  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(pollStatus, 1200);
  await pollStatus();
}

document.getElementById('runBtn').addEventListener('click', runJob);
