// Playground logic — pick models, paste text, see translations side-by-side.

const $ = (id) => document.getElementById(id);

let models = [];
let selected = new Set();

async function loadModels() {
  const res = await fetch('/api/models');
  models = await res.json();
  renderModels();
}

// renderModels() is provided by models-ui.js

async function translate() {
  const text = $('input').value.trim();
  if (!text) {
    $('status').textContent = 'Skriv inn tekst først.';
    return;
  }
  if (selected.size === 0) {
    $('status').textContent = 'Vel minst ein modell.';
    return;
  }

  $('translate-btn').disabled = true;
  $('status').textContent = 'Oversett… (første gongs bruk av ein modell kan ta litt tid medan han blir lasta)';
  $('results-section').hidden = false;
  $('results').innerHTML = '';

  const wrap = $('results');
  const slots = {};
  for (const key of selected) {
    const row = document.createElement('div');
    row.className = 'result-row';
    const m = models.find((x) => x.key === key);
    row.innerHTML = `
      <h3>${m?.display_name || key}</h3>
      <div class="meta">${m?.hf_name || key} · ventar…</div>
      <div class="output">…</div>
    `;
    wrap.appendChild(row);
    slots[key] = row;
  }

  try {
    const res = await fetch('/api/translate-many', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, models: Array.from(selected) }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Feil');

    for (const r of data.results) {
      const row = slots[r.model];
      if (r.error) {
        row.classList.add('error');
        row.querySelector('.meta').textContent = 'Feil';
        row.querySelector('.output').textContent = r.error;
      } else {
        row.querySelector('.meta').textContent = `${r.hf_name} · ${(r.ms / 1000).toFixed(2)}s`;
        row.querySelector('.output').textContent = r.translation;
      }
    }
    // Refresh model list to reflect loaded state.
    loadModels();
    $('status').textContent = 'Ferdig.';
  } catch (err) {
    $('status').textContent = 'Feil: ' + err.message;
  } finally {
    $('translate-btn').disabled = false;
  }
}

async function searchWiki() {
  const q = $('wiki-search').value.trim();
  if (!q) return;
  $('wiki-results').innerHTML = '<div class="muted">Søkjer…</div>';
  try {
    const res = await fetch('/api/wiki/search?q=' + encodeURIComponent(q));
    const titles = await res.json();
    if (!Array.isArray(titles) || titles.length === 0) {
      $('wiki-results').innerHTML = '<div class="muted">Ingen treff.</div>';
      return;
    }
    $('wiki-results').innerHTML = '';
    for (const title of titles) {
      const row = document.createElement('div');
      row.className = 'wiki-result';
      row.innerHTML = `
        <span class="title">${title}</span>
        <span>
          <button data-title="${title.replace(/"/g, '&quot;')}" class="use-btn">Bruk nb-teksten</button>
        </span>
      `;
      row.querySelector('.use-btn').addEventListener('click', async (e) => {
        e.target.disabled = true;
        e.target.textContent = 'Hentar…';
        const r = await fetch('/api/wiki/parallel?title=' + encodeURIComponent(title));
        const d = await r.json();
        if (d.pairs && d.pairs.length) {
          $('input').value = d.pairs.map((p) => p[0]).join('\n\n');
          $('status').textContent = `Lasta inn ${d.pairs.length} avsnitt frå "${title}" (nn-artikkel: "${d.nn_title}"). Trykk Oversett.`;
          window.scrollTo({ top: 0, behavior: 'smooth' });
        } else {
          $('status').textContent = `"${title}" har ikkje ei nynorsk parallell-utgåve.`;
        }
        e.target.disabled = false;
        e.target.textContent = 'Bruk nb-teksten';
      });
      $('wiki-results').appendChild(row);
    }
  } catch (err) {
    $('wiki-results').innerHTML = '<div class="muted">Feil: ' + err.message + '</div>';
  }
}

$('translate-btn').addEventListener('click', translate);
$('clear-btn').addEventListener('click', () => {
  $('input').value = '';
  $('results').innerHTML = '';
  $('results-section').hidden = true;
  $('status').textContent = '';
});
$('wiki-search-btn').addEventListener('click', searchWiki);
$('wiki-search').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') searchWiki();
});

loadModels();
