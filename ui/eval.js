// BLEU evaluator — compare many models against a human-written reference corpus.

const $ = (id) => document.getElementById(id);

let models = [];
let selected = new Set();
let pairs = [];  // [{nb, nn}]

async function loadModels() {
  const res = await fetch('/api/models');
  models = await res.json();
  renderModels();
}

function renderModels() {
  const wrap = $('model-list');
  wrap.innerHTML = '';
  for (const m of models) {
    const card = document.createElement('div');
    card.className = 'model-card' + (selected.has(m.key) ? ' selected' : '');
    card.innerHTML = `
      <label>
        <input type="checkbox" ${selected.has(m.key) ? 'checked' : ''} data-key="${m.key}" />
        <span class="key">${m.display_name}</span>
        <span class="state ${m.loaded ? 'loaded' : 'unloaded'}">${m.loaded ? 'loaded' : 'not loaded'}</span>
      </label>
      <div class="detail">${m.hf_name || m.key}${m.param_count ? ' · ' + m.param_count : ''}</div>
    `;
    card.querySelector('input').addEventListener('change', (e) => {
      const key = e.target.dataset.key;
      if (e.target.checked) selected.add(key);
      else selected.delete(key);
      card.classList.toggle('selected', e.target.checked);
    });
    wrap.appendChild(card);
  }
  if (selected.size === 0 && models.length) {
    selected.add(models[0].key);
    renderModels();
  }
}

function renderPairs() {
  const wrap = $('pair-editor');
  $('pair-count').textContent = pairs.length ? `${pairs.length} par` : '';
  if (pairs.length === 0) {
    wrap.innerHTML = '<div class="muted">Ingen par lagt til enno.</div>';
    return;
  }
  wrap.innerHTML = '';
  pairs.forEach((p, i) => {
    const row = document.createElement('div');
    row.className = 'pair';
    row.innerHTML = `
      <textarea data-i="${i}" data-field="nb" placeholder="bokmål">${escape(p.nb)}</textarea>
      <textarea data-i="${i}" data-field="nn" placeholder="nynorsk (referanse)">${escape(p.nn)}</textarea>
      <button data-i="${i}" class="remove">×</button>
    `;
    row.querySelectorAll('textarea').forEach((t) => {
      t.addEventListener('input', (e) => {
        const i = +e.target.dataset.i;
        const f = e.target.dataset.field;
        pairs[i][f] = e.target.value;
      });
    });
    row.querySelector('.remove').addEventListener('click', (e) => {
      pairs.splice(+e.target.dataset.i, 1);
      renderPairs();
    });
    wrap.appendChild(row);
  });
}

function escape(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
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
        <span class="title">${escape(title)}</span>
        <span>
          <button data-title="${title.replace(/"/g, '&quot;')}" class="use-btn">Legg til paralleltekst</button>
        </span>
      `;
      row.querySelector('.use-btn').addEventListener('click', async (e) => {
        e.target.disabled = true;
        e.target.textContent = 'Hentar…';
        const r = await fetch('/api/wiki/parallel?title=' + encodeURIComponent(title));
        const d = await r.json();
        if (d.pairs && d.pairs.length) {
          for (const [nb, nn] of d.pairs) {
            pairs.push({ nb, nn });
          }
          renderPairs();
          $('run-status').textContent = `+${d.pairs.length} par frå "${title}" → "${d.nn_title}" (no ${pairs.length} totalt)`;
        } else {
          $('run-status').textContent = `"${title}" har ikkje ei nynorsk parallell-utgåve.`;
        }
        e.target.disabled = false;
        e.target.textContent = 'Legg til paralleltekst';
      });
      $('wiki-results').appendChild(row);
    }
  } catch (err) {
    $('wiki-results').innerHTML = '<div class="muted">Feil: ' + err.message + '</div>';
  }
}

function loadTsv() {
  const text = $('tsv-input').value.trim();
  if (!text) return;
  const lines = text.split(/\r?\n/);
  let added = 0;
  for (const line of lines) {
    const parts = line.split('\t');
    if (parts.length >= 2 && parts[0].trim() && parts[1].trim()) {
      pairs.push({ nb: parts[0].trim(), nn: parts[1].trim() });
      added++;
    }
  }
  renderPairs();
  $('run-status').textContent = `+${added} par frå TSV (no ${pairs.length} totalt)`;
  $('tsv-input').value = '';
}

async function runEval() {
  if (pairs.length === 0) {
    $('run-status').textContent = 'Legg til minst eitt par.';
    return;
  }
  if (selected.size === 0) {
    $('run-status').textContent = 'Vel minst ein modell.';
    return;
  }
  const validPairs = pairs.filter((p) => p.nb.trim() && p.nn.trim());
  if (validPairs.length === 0) {
    $('run-status').textContent = 'Ingen fullstendige par.';
    return;
  }

  $('run-btn').disabled = true;
  $('run-status').textContent = `Køyrer ${validPairs.length} par × ${selected.size} modell(ar)…`;
  $('results-section').hidden = false;
  $('corpus-results').innerHTML = '<div class="muted">Ventar…</div>';
  $('segment-results').innerHTML = '';

  try {
    const res = await fetch('/api/bleu', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pairs: validPairs, models: Array.from(selected) }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Feil');
    renderResults(data.results);
    loadModels();
    $('run-status').textContent = 'Ferdig.';
  } catch (err) {
    $('run-status').textContent = 'Feil: ' + err.message;
    $('corpus-results').innerHTML = '';
  } finally {
    $('run-btn').disabled = false;
  }
}

function renderResults(results) {
  // Corpus-level table.
  const valid = results.filter((r) => !r.error);
  const bestBleu = valid.length ? Math.max(...valid.map((r) => r.corpus.bleu)) : 0;
  const bestChrf = valid.length ? Math.max(...valid.map((r) => r.corpus.chrf)) : 0;

  const rows = results.map((r) => {
    if (r.error) {
      return `<tr><td>${r.model}</td><td colspan="4" class="error">${escape(r.error)}</td></tr>`;
    }
    const bleuCls = r.corpus.bleu === bestBleu && bestBleu > 0 ? 'num best' : 'num';
    const chrfCls = r.corpus.chrf === bestChrf && bestChrf > 0 ? 'num best' : 'num';
    return `
      <tr>
        <td><strong>${r.model}</strong><br /><span class="muted">${r.hf_name}</span></td>
        <td class="num">${r.corpus.n}</td>
        <td class="${bleuCls}">${r.corpus.bleu}</td>
        <td class="${chrfCls}">${r.corpus.chrf}</td>
        <td class="num">${(r.elapsed_ms / 1000).toFixed(1)}s</td>
      </tr>
    `;
  }).join('');

  $('corpus-results').innerHTML = `
    <table class="corpus-table">
      <thead>
        <tr><th>Modell</th><th>N</th><th>BLEU ↑</th><th>chrF ↑</th><th>Tid</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="muted" style="margin-top: 0.5rem">
      BLEU og chrF måler begge kor nær ein maskin-oversettelse er ein menneskeleg referanse. chrF er meir forgjevande for morfologisk variasjon (ulike bøyingsformer) — viktig for nb↔nn.
    </p>
  `;

  // Per-segment details.
  const seg = $('segment-results');
  seg.innerHTML = '';
  for (const r of results) {
    if (r.error) continue;
    const header = document.createElement('h3');
    header.textContent = r.model;
    header.style.margin = '1rem 0 0.5rem 0';
    seg.appendChild(header);

    for (const s of r.segments) {
      const block = document.createElement('div');
      block.className = 'segment-block';
      block.innerHTML = `
        <div class="field"><span class="label">Bokmål</span><div>${escape(s.nb)}</div></div>
        <div class="field"><span class="label">Nynorsk (referanse)</span><div>${escape(s.nn_ref || s.nn)}</div></div>
        <div class="field"><span class="label">Nynorsk (modell)</span><div>${escape(s.nn_hyp || '')}</div></div>
        <div class="scores">BLEU ${s.bleu ?? '—'} · chrF ${s.chrf ?? '—'}</div>
      `;
      seg.appendChild(block);
    }
  }
}

// ── Corpus save/load ──────────────────────────────────────────
async function loadSavedCorpora() {
  const wrap = $('saved-corpora');
  try {
    const res = await fetch('/api/corpora');
    const list = await res.json();
    if (!list.length) {
      wrap.innerHTML = '<span class="muted">Ingen lagra korpus enno.</span>';
      return;
    }
    wrap.innerHTML = '';
    for (const c of list) {
      const row = document.createElement('div');
      row.className = 'wiki-result';
      row.innerHTML = `
        <span>
          <span class="title">${escape(c.name)}</span>
          <span class="muted" style="margin-left: 0.5rem">${c.pairs} par${c.source ? ' · ' + escape(c.source) : ''}</span>
        </span>
        <button data-name="${c.name.replace(/"/g, '&quot;')}">Last inn</button>
      `;
      row.querySelector('button').addEventListener('click', async (e) => {
        e.target.disabled = true;
        e.target.textContent = 'Lastar…';
        const r = await fetch('/api/corpora/load?name=' + encodeURIComponent(c.name));
        const d = await r.json();
        if (d.pairs) {
          pairs = d.pairs.map((p) => ({ nb: p.nb || p[0] || '', nn: p.nn || p[1] || '' }));
          renderPairs();
          $('run-status').textContent = `Lasta inn "${c.name}" (${pairs.length} par)`;
        }
        e.target.disabled = false;
        e.target.textContent = 'Last inn';
      });
      wrap.appendChild(row);
    }
  } catch (err) {
    wrap.innerHTML = '<span class="muted">Feil ved lasting av korpus.</span>';
  }
}

async function saveCorpus() {
  const name = $('corpus-name').value.trim();
  if (!name) {
    $('run-status').textContent = 'Skriv inn eit namn for korpuset.';
    return;
  }
  if (pairs.length === 0) {
    $('run-status').textContent = 'Ingen par å lagre.';
    return;
  }
  const validPairs = pairs.filter((p) => p.nb.trim() && p.nn.trim());
  try {
    const res = await fetch('/api/corpora/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, pairs: validPairs, source: 'manual' }),
    });
    const d = await res.json();
    $('run-status').textContent = `Lagra "${d.saved}" (${d.pairs} par)`;
    $('corpus-name').value = '';
    loadSavedCorpora();
  } catch (err) {
    $('run-status').textContent = 'Feil ved lagring: ' + err.message;
  }
}

$('run-btn').addEventListener('click', runEval);
$('add-pair').addEventListener('click', () => {
  pairs.push({ nb: '', nn: '' });
  renderPairs();
});
$('clear-pairs').addEventListener('click', () => {
  pairs = [];
  renderPairs();
});
$('wiki-search-btn').addEventListener('click', searchWiki);
$('wiki-search').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') searchWiki();
});
$('tsv-load').addEventListener('click', loadTsv);
$('save-corpus-btn').addEventListener('click', saveCorpus);

loadModels();
renderPairs();
loadSavedCorpora();
