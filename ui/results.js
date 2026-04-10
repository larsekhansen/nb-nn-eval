// Results viewer — browse and compare saved evaluation runs.

const $ = (id) => document.getElementById(id);

let allResults = [];
let compareSet = new Set();  // names to compare

function escape(s) {
  return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
}

async function loadResults() {
  const wrap = $('results-list');
  try {
    const res = await fetch('/api/results');
    allResults = await res.json();
    if (!allResults.length) {
      wrap.innerHTML = '<div class="muted">Ingen lagra resultat enno. Kjør ei evaluering frå <a href="/eval">BLEU-sida</a> med "Lagre resultat automatisk" på.</div>';
      return;
    }
    renderList();
  } catch (err) {
    wrap.innerHTML = '<div class="muted">Feil: ' + err.message + '</div>';
  }
}

function renderList() {
  const wrap = $('results-list');
  wrap.innerHTML = '';

  const table = document.createElement('table');
  table.className = 'corpus-table';
  table.innerHTML = `
    <thead>
      <tr>
        <th></th>
        <th>Tidspunkt</th>
        <th>Merknad</th>
        <th>Modellar</th>
        <th>Køyringar</th>
        <th>Handlingar</th>
      </tr>
    </thead>
  `;
  const tbody = document.createElement('tbody');

  for (const r of allResults) {
    const tr = document.createElement('tr');
    const checked = compareSet.has(r.name) ? 'checked' : '';
    tr.innerHTML = `
      <td><input type="checkbox" data-name="${r.name}" ${checked} /></td>
      <td class="num">${formatTimestamp(r.timestamp)}</td>
      <td>${escape(r.label) || '<span class="muted">—</span>'}</td>
      <td>${(r.models || []).map((m) => `<code>${m}</code>`).join(', ')}</td>
      <td class="num">${r.runs || 1}</td>
      <td>
        <button data-name="${r.name}" class="view-btn">Vis</button>
        <button data-name="${r.name}" class="del-btn" style="color: var(--bad)">Slett</button>
      </td>
    `;

    tr.querySelector('input').addEventListener('change', (e) => {
      if (e.target.checked) compareSet.add(r.name);
      else compareSet.delete(r.name);
      updateComparison();
    });

    tr.querySelector('.view-btn').addEventListener('click', () => viewResult(r.name));
    tr.querySelector('.del-btn').addEventListener('click', async () => {
      if (!confirm(`Slett "${r.label || r.name}"?`)) return;
      await fetch('/api/results/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: r.name }),
      });
      loadResults();
    });

    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  wrap.appendChild(table);
}

function formatTimestamp(ts) {
  if (!ts) return '—';
  // ts is "20260410-123456"
  const m = ts.match(/^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})$/);
  if (!m) return ts;
  return `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}`;
}

async function viewResult(name) {
  $('detail-section').hidden = false;
  $('detail-content').innerHTML = '<div class="muted">Lastar…</div>';
  try {
    const res = await fetch('/api/results/load?name=' + encodeURIComponent(name));
    const data = await res.json();
    $('detail-title').textContent = data.label || name;
    renderDetail(data);
  } catch (err) {
    $('detail-content').innerHTML = '<div class="muted">Feil: ' + err.message + '</div>';
  }
}

function renderDetail(data) {
  const summary = data.summary || [];
  const runs = data.runs || 1;
  const showVariance = runs > 1;

  let thExtra = '';
  if (showVariance) thExtra = '<th>Spread BLEU</th><th>σ BLEU</th>';

  const rows = summary.map((r) => {
    if (r.error) return `<tr><td>${r.model}</td><td colspan="4" style="color:var(--bad)">${escape(r.error)}</td></tr>`;
    let extra = '';
    if (showVariance) extra = `<td class="num">${r.bleu.spread}</td><td class="num">${r.bleu.stddev}</td>`;
    return `
      <tr>
        <td><strong>${r.model}</strong></td>
        <td class="num">${r.n || '—'}</td>
        <td class="num">${r.bleu.mean}</td>
        <td class="num">${r.chrf.mean}</td>
        <td class="num">${(r.time.mean / 1000).toFixed(1)}s</td>
        ${extra}
      </tr>
    `;
  }).join('');

  $('detail-content').innerHTML = `
    <p class="muted">${data.pairs_count || '?'} par · ${data.runs || 1} køyring(ar) · ${(data.models || []).join(', ')}</p>
    <table class="corpus-table">
      <thead><tr><th>Modell</th><th>N</th><th>BLEU</th><th>chrF</th><th>Tid</th>${thExtra}</tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

async function updateComparison() {
  if (compareSet.size < 2) {
    $('compare-section').hidden = true;
    return;
  }
  $('compare-section').hidden = false;
  $('compare-table').innerHTML = '<div class="muted">Lastar…</div>';

  // Load all selected results.
  const loaded = [];
  for (const name of compareSet) {
    try {
      const res = await fetch('/api/results/load?name=' + encodeURIComponent(name));
      loaded.push(await res.json());
    } catch { /* skip */ }
  }

  // Build a comparison: for each model that appears in ANY result, show
  // its BLEU/chrF across all runs.
  const modelScores = {};  // model → [{label, bleu, chrf}]
  for (const data of loaded) {
    const label = data.label || data.timestamp || '?';
    for (const s of (data.summary || [])) {
      if (s.error) continue;
      if (!modelScores[s.model]) modelScores[s.model] = [];
      modelScores[s.model].push({
        label,
        bleu: s.bleu.mean,
        chrf: s.chrf.mean,
        time: s.time.mean,
      });
    }
  }

  // Render comparison table.
  const labels = loaded.map((d) => d.label || d.timestamp || '?');
  const labelHeaders = labels.map((l) => `<th colspan="2">${escape(l)}</th>`).join('');

  let bodyRows = '';
  for (const [model, scores] of Object.entries(modelScores)) {
    let cells = '';
    for (const data of loaded) {
      const s = scores.find((sc) => sc.label === (data.label || data.timestamp || '?'));
      if (s) {
        cells += `<td class="num">${s.bleu}</td><td class="num">${s.chrf}</td>`;
      } else {
        cells += '<td class="num muted">—</td><td class="num muted">—</td>';
      }
    }
    bodyRows += `<tr><td><strong>${model}</strong></td>${cells}</tr>`;
  }

  const subHeaders = loaded.map(() => '<th class="num">BLEU</th><th class="num">chrF</th>').join('');

  $('compare-table').innerHTML = `
    <table class="corpus-table">
      <thead>
        <tr><th rowspan="2">Modell</th>${labelHeaders}</tr>
        <tr>${subHeaders}</tr>
      </thead>
      <tbody>${bodyRows}</tbody>
    </table>
  `;
}

loadResults();
