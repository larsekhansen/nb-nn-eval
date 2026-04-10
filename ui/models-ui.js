// Shared model-list renderer used by both playground and eval pages.
// Depends on: models (array), selected (Set), $ (id lookup).

function renderModels() {
  const wrap = $('model-list');
  wrap.innerHTML = '';

  // Group models.
  const groups = {};
  for (const m of models) {
    const g = m.group || 'Andre';
    if (!groups[g]) groups[g] = [];
    groups[g].push(m);
  }

  for (const [group, items] of Object.entries(groups)) {
    const section = document.createElement('div');
    section.className = 'model-group';
    section.innerHTML = `<div class="model-group-label">${group}</div>`;
    const grid = document.createElement('div');
    grid.className = 'model-group-grid';

    for (const m of items) {
      const disabled = !m.available;
      const card = document.createElement('div');
      card.className = 'model-card'
        + (selected.has(m.key) ? ' selected' : '')
        + (disabled ? ' unavailable' : '');

      let stateHtml;
      if (disabled) {
        stateHtml = `<span class="state unavailable" title="${m.unavailable_reason || ''}">ikkje tilgjengeleg</span>`;
      } else if (m.loaded) {
        stateHtml = '<span class="state loaded">loaded</span>';
      } else {
        stateHtml = '<span class="state unloaded">ikkje lasta</span>';
      }

      card.innerHTML = `
        <label>
          <input type="checkbox" ${selected.has(m.key) ? 'checked' : ''} ${disabled ? 'disabled' : ''} data-key="${m.key}" />
          <span class="key">${m.display_name}</span>
          ${stateHtml}
        </label>
        ${disabled ? `<div class="detail unavailable-hint">${m.unavailable_reason || ''}</div>` : `<div class="detail">${m.hf_name || m.key}${m.param_count ? ' · ' + m.param_count : ''}</div>`}
      `;

      if (!disabled) {
        card.querySelector('input').addEventListener('change', (e) => {
          const key = e.target.dataset.key;
          if (e.target.checked) selected.add(key);
          else selected.delete(key);
          card.classList.toggle('selected', e.target.checked);
        });
      }
      grid.appendChild(card);
    }
    section.appendChild(grid);
    wrap.appendChild(section);
  }

  // Auto-select first available model on first load.
  if (selected.size === 0) {
    const first = models.find((m) => m.available);
    if (first) {
      selected.add(first.key);
      renderModels();
    }
  }
}
