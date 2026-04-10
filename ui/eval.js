// BLEU evaluator — compare many models against a human-written reference corpus.
// Supports multi-run mode (run the same eval N times to measure variance).

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
        pairs[+e.target.dataset.i][e.target.dataset.field] = e.target.value;
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

// ── Multi-run evaluation ──────────────────────────────────────
function setProgress(pct, text) {
  $('progress-bar').hidden = false;
  $('progress-fill').style.width = pct + '%';
  $('progress-text').textContent = text;
}

async function runEval() {
  const validPairs = pairs.filter((p) => p.nb.trim() && p.nn.trim());
  if (validPairs.length === 0) {
    $('run-status').textContent = 'Legg til minst eitt par.';
    return;
  }
  if (selected.size === 0) {
    $('run-status').textContent = 'Vel minst ein modell.';
    return;
  }

  const numRuns = Math.max(1, Math.min(20, parseInt($('run-count').value) || 1));
  const modelKeys = Array.from(selected);
  const totalSteps = numRuns * modelKeys.length;

  $('run-btn').disabled = true;
  $('results-section').hidden = false;
  $('corpus-results').innerHTML = '<div class="muted">Ventar…</div>';
  $('segment-results').innerHTML = '';

  // allRuns[modelKey] = [{corpus, segments, elapsed_ms}, ...]
  const allRuns = {};
  for (const k of modelKeys) allRuns[k] = [];

  let step = 0;
  try {
    for (let run = 0; run < numRuns; run++) {
      for (const key of modelKeys) {
        step++;
        const label = numRuns > 1
          ? `Køyring ${run + 1}/${numRuns}, modell ${key} (${step}/${totalSteps})…`
          : `Modell ${key} (${step}/${totalSteps})…`;
        $('run-status').textContent = label;
        setProgress(Math.round((step / totalSteps) * 100), label);

        // Run one model at a time for cleaner progress.
        const res = await fetch('/api/bleu', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pairs: validPairs, models: [key] }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Feil');

        const r = data.results[0];
        allRuns[key].push(r);
      }
    }

    const summary = buildSummary(allRuns, numRuns);
    renderResults(summary, numRuns);
    loadModels();

    // Auto-save.
    if ($('auto-save').checked) {
      const label = $('result-label').value.trim();
      const saveBody = {
        label: label || `${modelKeys.join(', ')} × ${numRuns} runs`,
        corpus_name: $('corpus-name').value.trim() || '(unnamed)',
        runs: numRuns,
        models: modelKeys,
        pairs_count: validPairs.length,
        summary,
        all_runs: allRuns,
      };
      const saveRes = await fetch('/api/results/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(saveBody),
      });
      const saved = await saveRes.json();
      $('run-status').textContent = `Ferdig! Lagra som "${saved.saved}"`;
    } else {
      $('run-status').textContent = 'Ferdig!';
    }
  } catch (err) {
    $('run-status').textContent = 'Feil: ' + err.message;
    $('corpus-results').innerHTML = '';
  } finally {
    $('run-btn').disabled = false;
    $('progress-bar').hidden = true;
  }
}

function buildSummary(allRuns, numRuns) {
  // For each model, compute mean/min/max/stddev of corpus BLEU and chrF.
  const summary = [];
  for (const [key, runs] of Object.entries(allRuns)) {
    const validRuns = runs.filter((r) => !r.error && r.corpus);
    if (validRuns.length === 0) {
      summary.push({ model: key, error: runs[0]?.error || 'Unknown error' });
      continue;
    }

    const bleus = validRuns.map((r) => r.corpus.bleu);
    const chrfs = validRuns.map((r) => r.corpus.chrf);
    const times = validRuns.map((r) => r.elapsed_ms);

    const stats = (arr) => {
      const n = arr.length;
      const mean = arr.reduce((a, b) => a + b, 0) / n;
      const min = Math.min(...arr);
      const max = Math.max(...arr);
      const variance = n > 1 ? arr.reduce((s, x) => s + (x - mean) ** 2, 0) / (n - 1) : 0;
      const stddev = Math.sqrt(variance);
      return { mean: +mean.toFixed(2), min: +min.toFixed(2), max: +max.toFixed(2), stddev: +stddev.toFixed(2), spread: +(max - min).toFixed(2) };
    };

    summary.push({
      model: key,
      hf_name: validRuns[0].hf_name,
      runs: validRuns.length,
      n: validRuns[0].corpus.n,
      bleu: stats(bleus),
      chrf: stats(chrfs),
      time: stats(times),
      // Keep the last run's segments for detail view.
      segments: validRuns[validRuns.length - 1].segments,
    });
  }
  return summary;
}

function renderResults(summary, numRuns) {
  const valid = summary.filter((r) => !r.error);
  const bestBleu = valid.length ? Math.max(...valid.map((r) => r.bleu.mean)) : 0;
  const bestChrf = valid.length ? Math.max(...valid.map((r) => r.chrf.mean)) : 0;
  const showVariance = numRuns > 1;

  let thExtra = '';
  let colCount = 5;
  if (showVariance) {
    thExtra = '<th>BLEU spread</th><th>chrF spread</th><th>σ BLEU</th>';
    colCount = 8;
  }

  const rows = summary.map((r) => {
    if (r.error) {
      return `<tr><td>${r.model}</td><td colspan="${colCount - 1}" style="color: var(--bad)">${escape(r.error)}</td></tr>`;
    }
    const bleuCls = r.bleu.mean === bestBleu && bestBleu > 0 ? 'num best' : 'num';
    const chrfCls = r.chrf.mean === bestChrf && bestChrf > 0 ? 'num best' : 'num';
    let extra = '';
    if (showVariance) {
      extra = `
        <td class="num">${r.bleu.spread}</td>
        <td class="num">${r.chrf.spread}</td>
        <td class="num">${r.bleu.stddev}</td>
      `;
    }
    return `
      <tr>
        <td><strong>${r.model}</strong><br /><span class="muted">${r.hf_name || ''}</span></td>
        <td class="num">${r.n}</td>
        <td class="${bleuCls}">${r.bleu.mean}</td>
        <td class="${chrfCls}">${r.chrf.mean}</td>
        <td class="num">${(r.time.mean / 1000).toFixed(1)}s</td>
        ${extra}
      </tr>
    `;
  }).join('');

  $('corpus-results').innerHTML = `
    <table class="corpus-table">
      <thead>
        <tr>
          <th>Modell</th><th>N</th><th>BLEU ↑</th><th>chrF ↑</th><th>Tid</th>
          ${thExtra}
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    ${showVariance ? `
    <p class="muted" style="margin-top: 0.5rem">
      <strong>Spread</strong> = max − min over ${numRuns} køyringar. <strong>σ</strong> = standardavvik.
      Deterministiske modellar (beam search) gjev spread = 0. API-modellar med temperature &gt; 0 kan variere.
    </p>` : ''}
  `;

  // Per-segment details (from last run).
  const seg = $('segment-results');
  seg.innerHTML = '';
  for (const r of summary) {
    if (r.error || !r.segments) continue;
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
          $('corpus-name').value = c.name;
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
  if (!name) { $('run-status').textContent = 'Skriv inn eit namn for korpuset.'; return; }
  if (pairs.length === 0) { $('run-status').textContent = 'Ingen par å lagre.'; return; }
  const validPairs = pairs.filter((p) => p.nb.trim() && p.nn.trim());
  try {
    const res = await fetch('/api/corpora/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, pairs: validPairs, source: 'manual' }),
    });
    const d = await res.json();
    $('run-status').textContent = `Lagra "${d.saved}" (${d.pairs} par)`;
    loadSavedCorpora();
  } catch (err) {
    $('run-status').textContent = 'Feil ved lagring: ' + err.message;
  }
}

// ── Event listeners ───────────────────────────────────────────
$('run-btn').addEventListener('click', runEval);
$('add-pair').addEventListener('click', () => { pairs.push({ nb: '', nn: '' }); renderPairs(); });
$('clear-pairs').addEventListener('click', () => { pairs = []; renderPairs(); });
$('wiki-search-btn').addEventListener('click', searchWiki);
$('wiki-search').addEventListener('keydown', (e) => { if (e.key === 'Enter') searchWiki(); });
$('tsv-load').addEventListener('click', loadTsv);
$('save-corpus-btn').addEventListener('click', saveCorpus);
$('select-all').addEventListener('click', () => {
  models.forEach((m) => selected.add(m.key));
  renderModels();
});
$('select-none').addEventListener('click', () => {
  selected.clear();
  renderModels();
});

loadModels();
renderPairs();
loadSavedCorpora();
