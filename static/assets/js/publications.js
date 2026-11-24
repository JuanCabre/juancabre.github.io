'use strict';
// The publications page: filters, charts, the coauthor flower and the library.
// The data comes from assets/data/publications.json, which build.py writes from the BibTeX file.

const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const count = (list, test) => list.filter(test).length;
const plural = (n, word) => `${n.toLocaleString('en-US')} ${word}${n === 1 ? '' : 's'}`;

const TYPE_COLOR = {
  'Journal': 'var(--type-journal)',
  'Conference': 'var(--type-conference)',
  'Book chapter': 'var(--type-book)',
  'Preprint': 'var(--type-preprint)',
  'Other': 'var(--type-other)'
};
const TYPE_LABEL = { 'Journal': 'Journal articles', 'Conference': 'Conference papers', 'Book chapter': 'Book chapters', 'Preprint': 'Preprints', 'Other': 'Other outputs' };
const PAGE_SIZE = 50;
// Chart text is drawn at real CSS pixels, never below the site's smallest step (13.8px).
const CHART_FONT = 14;

let D, TYPES, years;
let current = [];      // entries that pass the filter bar
let library = [];      // entries shown in the library (filter bar + search)
let page = 0;
const scrollBehavior = () => (window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth');

/* ---------- Tooltip ---------- */
function tip(event, text) {
  const box = $('#tooltip');
  box.textContent = text;
  box.style.display = 'block';
  const x = event.clientX ?? window.innerWidth / 2, y = event.clientY ?? 150;
  box.style.left = Math.max(8, Math.min(x + 12, window.innerWidth - box.offsetWidth - 8)) + 'px';
  box.style.top = Math.max(8, Math.min(y + 14, window.innerHeight - box.offsetHeight - 8)) + 'px';
}
const untip = () => { $('#tooltip').style.display = 'none'; };
function bindTips(root) {
  root.querySelectorAll('[data-tip]').forEach(element => {
    element.addEventListener('pointermove', event => tip(event, element.dataset.tip));
    element.addEventListener('pointerleave', untip);
    element.addEventListener('focus', () => {
      const box = element.getBoundingClientRect();
      tip({ clientX: box.left + box.width / 2, clientY: box.top + box.height / 2 }, element.dataset.tip);
    });
    element.addEventListener('blur', untip);
  });
}
function activate(element, action) {
  element.addEventListener('click', action);
  element.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); action(); }
  });
}

/* ---------- Filters ---------- */
function filtered(ignoreCoauthor) {
  const lo = +$('#from').value, hi = +$('#to').value, type = $('#type').value, coauthor = $('#coauthor').value;
  return D.publications.filter(p =>
    (p.year === null || (p.year >= lo && p.year <= hi)) &&
    (!type || p.category === type) &&
    (ignoreCoauthor || !coauthor || p.people.includes(coauthor)) &&
    (ignoreCoauthor || !pair || pair.every(name => p.people.includes(name))));
}

// A curve in the coauthor flower selects the papers that two coauthors wrote together with me.
let pair = null;
function setPair(a, b) {
  pair = [a, b];
  $('#coauthor').value = '';
  render();
  $('#library').scrollIntoView({ behavior: scrollBehavior() });
}

function setCoauthor(name) {
  $('#coauthor').value = $('#coauthor').value === name ? '' : name;
  pair = null;
  render();
}

function resetFilters() {
  $('#from').value = years[0];
  $('#to').value = years[years.length - 1];
  $('#type').value = '';
  $('#coauthor').value = '';
  pair = null;
  $('#search').value = '';
  $('#award-only').checked = false;
  render();
}

// render() rebuilds the charts; keep keyboard focus on the matching new element.
const FOCUS_KEYS = ['year', 'node', 'person', 'type', 'a'];
function render() {
  const active = document.activeElement, key = active && active.dataset && FOCUS_KEYS.find(k => k in active.dataset);
  const holder = key && active.closest('[id]');
  const selector = key && holder ? `#${holder.id} [data-${key}="${CSS.escape(active.dataset[key])}"]` : null;
  page = 0;
  current = filtered(false);
  stats();
  timeline();
  mix();
  topVenues();
  flower();
  coauthorRank();
  publications();
  syncUrl();
  if (selector) {
    const again = document.querySelector(selector);
    if (again) { if (again.getAttribute('tabindex') === '-1' && again.classList.contains('node')) roveTo(again); again.focus({ preventScroll: true }); }
  }
}

// One line that says what the page shows: the filter bar, and the library search on top of it.
const entries = n => plural(n, 'entry').replace('entrys', 'entries');
function filterInfo() {
  const coauthor = $('#coauthor').value, type = $('#type').value, query = $('#search').value.trim(), awardOnly = $('#award-only').checked;
  const narrowed = query || awardOnly;
  const parts = [narrowed ? `${library.length.toLocaleString('en-US')} of ${entries(current.length)}` : entries(current.length), `${$('#from').value} to ${$('#to').value}`];
  if (type) parts.push(type);
  if (coauthor) parts.push('with ' + coauthor);
  if (pair) parts.push('with ' + pair.join(' and '));
  if (query) parts.push(`matching “${query}”`);
  if (awardOnly) parts.push('with an award mention');
  $('#filter-info').textContent = parts.join(' · ');
}

/* ---------- Stat tiles ---------- */
function stats() {
  const people = new Set();
  current.forEach(p => p.people.forEach(name => { if (name !== D.author) people.add(name); }));
  const tiles = [
    ['Entries', current.length, 'In this view'],
    ['Journal articles', count(current, p => p.type === 'Journal'), 'Peer-reviewed journals'],
    ['Conference papers', count(current, p => p.type === 'Conference'), 'Proceedings contributions'],
    ['Coauthors', people.size, 'People I have published with']
  ];
  $('#stats').innerHTML = tiles.map(([label, value, sub]) =>
    `<div class="stat"><div class="stat-label">${label}</div><div class="stat-value">${value.toLocaleString('en-US')}</div><div class="stat-sub">${sub}</div></div>`).join('');
}

/* ---------- Publications over time ---------- */
function niceStep(max) {
  for (const step of [1, 2, 5, 10, 20, 25, 50, 100]) if (max / step <= 5) return step;
  return 200;
}

function timeline() {
  const lo = +$('#from').value, hi = +$('#to').value;
  const ys = years.filter(year => year >= lo && year <= hi);
  const perYear = ys.map(year => TYPES.map(type => count(current, p => p.year === year && p.type === type)));
  const totals = perYear.map(row => row.reduce((a, b) => a + b, 0));
  const step = niceStep(Math.max(...totals, 1));
  const top = Math.max(step, Math.ceil(Math.max(...totals, 1) / step) * step);
  // Drawn at the container's own pixel width, so that the text is exactly CHART_FONT pixels.
  const box = $('#timeline');
  const W = Math.max(300, Math.floor(box.clientWidth || 640)), H = W < 520 ? 280 : 340;
  const left = 34, right = 6, bottom = H - 34, height = bottom - 36;
  const slot = (W - left - right) / Math.max(ys.length, 1), bar = Math.min(28, slot * 0.62), gap = 2;
  const single = lo === hi;
  // A year label needs about 40px; on narrow screens label every second (or third) year.
  const every = Math.max(1, Math.ceil(40 / slot));
  timelineWidth = box.clientWidth;

  $('#legend').innerHTML = TYPES.map(type => `<span><i style="background:${TYPE_COLOR[type]}"></i>${esc(TYPE_LABEL[type])}</span>`).join('');
  let svg = `<svg class="chart-svg chart-px" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="group" aria-label="Entries per year, stacked by type">`;
  for (let tick = 0; tick <= top; tick += step) {
    const y = bottom - tick / top * height;
    svg += `<line x1="${left}" x2="${W - right}" y1="${y}" y2="${y}" style="stroke:var(--line-soft)"/>`
      + `<text x="${left - 8}" y="${y + 5}" text-anchor="end" font-size="${CHART_FONT}">${tick}</text>`;
  }
  ys.forEach((year, index) => {
    const x = left + index * slot + (slot - bar) / 2;
    const breakdown = TYPES.map((type, t) => perYear[index][t] ? `${TYPE_LABEL[type]}: ${perYear[index][t]}` : '').filter(Boolean).join(' · ');
    const description = `${year}: ${plural(totals[index], 'entry').replace('entrys', 'entries')}${breakdown ? ' (' + breakdown + ')' : ''}`;
    svg += `<g class="year-col clickable${single ? ' selected' : ''}" tabindex="0" role="button" aria-pressed="${single}" data-year="${year}" aria-label="${esc(description)}. Select to show only this year." data-tip="${esc(description)}">`
      + `<rect class="hover-band" x="${left + index * slot + 2}" y="14" width="${slot - 4}" height="${H - 18}" rx="5" fill="transparent"/>`;
    let y = bottom;
    const present = TYPES.map((type, t) => t).filter(t => perYear[index][t]);
    present.forEach((t, position) => {
      const full = perYear[index][t] / top * height;
      const h = Math.max(full - (position ? gap : 0), 1.5);
      y -= full;
      const isTop = position === present.length - 1;
      const r = isTop ? Math.min(4, h) : 0;
      // square at the baseline, rounded at the data end
      svg += `<path d="M ${x} ${y + h} V ${y + r} Q ${x} ${y} ${x + r} ${y} H ${x + bar - r} Q ${x + bar} ${y} ${x + bar} ${y + r} V ${y + h} Z" style="fill:${TYPE_COLOR[TYPES[t]]}"/>`;
    });
    const labelled = single || (ys.length - 1 - index) % every === 0;
    svg += `<text class="value-label" x="${x + bar / 2}" y="${y - 7}" text-anchor="middle" font-size="${CHART_FONT}">${totals[index] || ''}</text>`
      + (labelled ? `<text class="year-label" x="${x + bar / 2}" y="${bottom + 22}" text-anchor="middle" font-size="${CHART_FONT}">${year}</text>` : '') + '</g>';
  });
  svg += '</svg>';
  box.innerHTML = svg;
  $('#timeline').querySelectorAll('[data-year]').forEach(element => activate(element, () => {
    const year = element.dataset.year;
    if (single && $('#from').value === year) {         // selecting the only year again clears the range
      $('#from').value = years[0];
      $('#to').value = years[years.length - 1];
    } else {
      $('#from').value = $('#to').value = year;
    }
    untip();
    render();
  }));
  bindTips($('#timeline'));
}

/* ---------- Publication mix ---------- */
// Ruled rows with counts and shares; a thin bar under each row shows the share.
function mix() {
  const total = current.length;
  const rows = TYPES.map(type => {
    const n = count(current, p => p.type === type), share = total ? Math.round(n / total * 100) : 0;
    const single = new Set(D.publications.filter(p => p.type === type).map(p => p.category)).size === 1;
    const name = `<i class="dot" style="background:${TYPE_COLOR[type]}"></i>${esc(TYPE_LABEL[type])}`;
    const head = single
      ? `<button type="button" data-type="${esc(type)}" aria-label="${esc(TYPE_LABEL[type])}: ${n}, ${share}%. Select to list them.">${name}</button>`
      : `<span class="mix-name">${name}</span>`;
    return `<div class="mix-item">${head}`
      + `<b>${n}<span>${share}%</span></b>`
      + `<div class="mix-bar" aria-hidden="true"><div style="width:${total ? n / total * 100 : 0}%;background:${TYPE_COLOR[type]}"></div></div></div>`;
  }).join('');
  $('#mix').innerHTML = `<div class="mix-legend">${rows}<div class="mix-item mix-total"><span>All entries</span><b>${total}</b></div></div>`;
  // A type groups one or more categories; jump to the library filtered by the type's search word.
  $('#mix').querySelectorAll('[data-type]').forEach(button => {
    button.onclick = () => {
      const categories = [...new Set(D.publications.filter(p => p.type === button.dataset.type).map(p => p.category))];
      if (categories.length === 1) { $('#type').value = categories[0]; render(); }
      $('#library').scrollIntoView({ behavior: scrollBehavior() });
    };
  });
}

/* ---------- Top venues ---------- */
function topVenues() {
  const venues = new Map();
  current.forEach(p => {
    if (!p.venue || p.category === 'Patent' || p.category === 'Doctoral thesis') return;
    if (!venues.has(p.venue)) venues.set(p.venue, { name: p.venue, n: 0, types: {} });
    const venue = venues.get(p.venue);
    venue.n++;
    venue.types[p.type] = (venue.types[p.type] || 0) + 1;
  });
  const top = [...venues.values()].sort((a, b) => b.n - a.n || a.name.localeCompare(b.name)).slice(0, 10);
  const max = top[0]?.n || 1;
  $('#venue-legend').innerHTML = TYPES.filter(type => top.some(v => v.types[type]))
    .map(type => `<span><i style="background:${TYPE_COLOR[type]}"></i>${esc(TYPE_LABEL[type])}</span>`).join('');
  $('#top-venues').innerHTML = top.map(v =>
    `<div class="venue-row"><div class="venue-label"><span>${esc(v.name)}</span><b>${v.n}</b></div>`
    + `<div class="venue-track" role="img" aria-label="${esc(v.name)}: ${v.n}">${TYPES.filter(type => v.types[type]).map(type =>
      `<div style="width:${v.types[type] / max * 100}%;background:${TYPE_COLOR[type]}"></div>`).join('')}</div></div>`).join('')
    || '<p class="empty">No venues in this view.</p>';
}

/* ---------- Coauthors ---------- */
// Coauthor counts under the year and type filters, ignoring the coauthor filter itself,
// so that the diagram stays the same while one person is selected.
function coauthorCounts() {
  const counts = new Map();
  filtered(true).forEach(p => new Set(p.people).forEach(name => {
    if (name !== D.author) counts.set(name, (counts.get(name) || 0) + 1);
  }));
  return [...counts].map(([name, n]) => ({ name, n })).sort((a, b) => b.n - a.n || a.name.localeCompare(b.name));
}
const surname = name => name.split(' ').at(-1);
// Academic title of a coauthor, where the data gives one ("Prof. Jane Doe").
let TITLES = new Map();
const titled = name => (TITLES.has(name) ? TITLES.get(name) + ' ' : '') + name;
const initials = name => { const parts = name.replace(/\./g, '').split(' '); return (parts[0][0] + parts.at(-1)[0]).toUpperCase(); };

// Ring labels: the full titled name where it fits, otherwise the given name and surname without initials.
const shortName = name => { const parts = name.split(' '); return parts.filter((part, i) => i === 0 || i === parts.length - 1 || !/^[A-Z]\.?$/.test(part)).join(' '); };
let measureContext;
function textWidth(text, size, weight = 400) {
  measureContext ||= document.createElement('canvas').getContext('2d');
  measureContext.font = `${weight} ${size}px ${getComputedStyle(document.body).fontFamily}`;
  return measureContext.measureText(text).width;
}
let flowerWidth = 0, timelineWidth = 0;

function flower() {
  const ranked = coauthorCounts(), size = +$('#flower-size').value;
  $('#flower-size-value').textContent = size;
  const shown = ranked.slice(0, size).sort((a, b) => surname(a.name).localeCompare(surname(b.name)) || a.name.localeCompare(b.name));
  const selected = $('#coauthor').value;
  if (!shown.length) {
    $('#flower').innerHTML = '<p class="empty">No coauthors in this view.</p>';
    $('#flower-summary').textContent = '';
    return;
  }
  const inView = new Set(shown.map(person => person.name)), pairs = new Map();
  filtered(true).forEach(p => {
    const people = [...new Set(p.people)].filter(name => inView.has(name)).sort();
    for (let i = 0; i < people.length; i++) for (let j = i + 1; j < people.length; j++) {
      const key = people[i] + '\t' + people[j];
      pairs.set(key, (pairs.get(key) || 0) + 1);
    }
  });
  const edges = [...pairs].map(([key, n]) => ({ a: key.split('\t')[0], b: key.split('\t')[1], n })).sort((a, b) => a.n - b.n);
  const maxEdge = Math.max(1, ...edges.map(edge => edge.n)), maxNode = Math.max(1, ...shown.map(person => person.n));
  // Drawn at real pixels (up to 980px wide), so the names and initials are exactly CHART_FONT pixels.
  const box = $('#flower');
  flowerWidth = box.clientWidth;
  if (!flowerWidth) { box.innerHTML = ''; return; }          // hidden on small screens; the ranked list leads there
  const W = Math.max(640, Math.min(980, flowerWidth)), font = CHART_FONT + 1;
  const nodeMax = 12 + 9, ringGap = 8;
  let label = titled, labelMax = Math.max(...shown.map(person => textWidth(titled(person.name), font)));
  let r = W / 2 - labelMax - nodeMax - ringGap - 6;
  if (r < 200) {
    label = shortName;
    labelMax = Math.max(...shown.map(person => textWidth(shortName(person.name), font)));
    r = W / 2 - labelMax - nodeMax - ringGap - 6;
  }
  r = Math.max(150, r);
  const H = Math.ceil(2 * (r + nodeMax + ringGap + labelMax + 6)), cx = W / 2, cy = H / 2;
  const position = new Map(shown.map((person, index) => {
    const angle = index / shown.length * 2 * Math.PI - Math.PI / 2;
    return [person.name, { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle), angle }];
  }));
  let svg = `<svg class="chart-svg chart-px" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="group" aria-label="Coauthorship diagram of ${shown.length} coauthors">`
    + `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" style="stroke:var(--line)" stroke-dasharray="2 5"/>`;
  edges.forEach(edge => {
    const p = position.get(edge.a), q = position.get(edge.b);
    const description = `${titled(edge.a)} and ${titled(edge.b)}: ${plural(edge.n, 'paper')} together with me`;
    const chosen = pair && pair.includes(edge.a) && pair.includes(edge.b);
    svg += `<path class="link flower-pair${chosen ? ' selected' : ''}" tabindex="-1" role="button" aria-label="${esc(description)}. Select to show these papers." data-a="${esc(edge.a)}" data-b="${esc(edge.b)}" data-tip="${esc(description)}" d="M ${p.x} ${p.y} Q ${cx} ${cy} ${q.x} ${q.y}" fill="none" stroke-opacity="${(.12 + .5 * edge.n / maxEdge).toFixed(2)}" stroke-width="${(1 + 11 * edge.n / maxEdge).toFixed(1)}" stroke-linecap="round"/>`;
  });
  shown.forEach(person => {
    const p = position.get(person.name), leftSide = Math.cos(p.angle) < -0.08;
    let rotation = p.angle * 180 / Math.PI;
    if (leftSide) rotation += 180;
    const radius = 12 + 9 * Math.sqrt(person.n / maxNode);
    const description = `${titled(person.name)}: ${plural(person.n, 'paper')} with me`;
    svg += `<g class="node clickable${person.name === selected ? ' selected' : ''}" tabindex="-1" role="button" aria-pressed="${person.name === selected}" data-node="${esc(person.name)}" aria-label="${esc(description)}. Select to filter the page." data-tip="${esc(description)}">`
      + `<circle cx="${p.x}" cy="${p.y}" r="${radius.toFixed(1)}"/>`
      + `<text class="initials" x="${p.x}" y="${p.y}" text-anchor="middle" dominant-baseline="central" font-size="${CHART_FONT}">${esc(initials(person.name))}</text>`
      + `<text class="name" transform="translate(${p.x + (radius + ringGap) * Math.cos(p.angle)},${p.y + (radius + ringGap) * Math.sin(p.angle)}) rotate(${rotation})" text-anchor="${leftSide ? 'end' : 'start'}" dominant-baseline="central" font-size="${font}">${esc(label(person.name))}</text></g>`;
  });
  svg += `<g class="hub"><circle cx="${cx}" cy="${cy}" r="58" fill-opacity=".95"/>`
    + `<text class="hub-count" x="${cx}" y="${cy + 2}" text-anchor="middle" font-size="30">${ranked.length}</text>`
    + `<text x="${cx}" y="${cy + 24}" text-anchor="middle" font-size="${CHART_FONT}">${ranked.length === 1 ? 'coauthor' : 'coauthors'}</text></g></svg>`;
  box.innerHTML = svg;
  $('#flower-summary').textContent = `${shown.length} of ${plural(ranked.length, 'coauthor')} · ${plural(edges.length, 'connection')}`;
  const links = [...box.querySelectorAll('.link')];
  const focus = name => links.forEach(link => { link.style.opacity = link.dataset.a === name || link.dataset.b === name ? '1' : '.05'; });
  const focusPair = () => links.forEach(link => { link.style.opacity = link.classList.contains('selected') ? '1' : '.05'; });
  const clear = () => (selected && inView.has(selected) ? focus(selected)
    : pair && links.some(link => link.classList.contains('selected')) ? focusPair()
    : links.forEach(link => { link.style.opacity = '1'; }));
  box.querySelectorAll('.node').forEach(node => {
    node.addEventListener('pointerenter', () => focus(node.dataset.node));
    node.addEventListener('pointerleave', clear);
    node.addEventListener('focus', () => focus(node.dataset.node));
    node.addEventListener('blur', clear);
    activate(node, () => { untip(); setCoauthor(node.dataset.node); });
  });
  links.forEach(link => {
    activate(link, () => { untip(); setPair(link.dataset.a, link.dataset.b); });
    link.addEventListener('pointerenter', () => links.forEach(other => { other.style.opacity = other === link ? '1' : '.05'; }));
    link.addEventListener('pointerleave', clear);
  });
  // One tab stop for the diagram; arrow keys move between coauthors.
  const nodes = [...box.querySelectorAll('.node')];
  roveTo(nodes.find(node => node.classList.contains('selected')) || nodes[0]);
  nodes.forEach((node, index) => node.addEventListener('keydown', event => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    const target = step ? nodes[(index + step + nodes.length) % nodes.length]
      : event.key === 'Home' ? nodes[0] : event.key === 'End' ? nodes[nodes.length - 1] : null;
    if (!target) return;
    event.preventDefault();
    roveTo(target);
    target.focus();
  }));
  clear();
  bindTips(box);
}

function roveTo(node) {
  if (!node) return;
  node.closest('svg').querySelectorAll('.node').forEach(other => other.setAttribute('tabindex', other === node ? '0' : '-1'));
}

function coauthorRank() {
  const ranked = coauthorCounts().slice(0, 12), max = ranked[0]?.n || 1, selected = $('#coauthor').value;
  $('#coauthor-rank').innerHTML = ranked.map(person =>
    `<button type="button" class="rank${person.name === selected ? ' selected' : ''}" data-person="${esc(person.name)}" aria-pressed="${person.name === selected}" aria-label="${esc(titled(person.name))}: ${plural(person.n, 'paper')} together. Select to filter the page.">`
    + `<span>${esc(titled(person.name))}</span><div class="bar-track"><div class="bar-fill" style="width:${person.n / max * 100}%"></div></div><b>${person.n}</b></button>`).join('')
    || '<p class="empty">No coauthors in this view.</p>';
  $('#coauthor-rank').querySelectorAll('[data-person]').forEach(button => { button.onclick = () => setCoauthor(button.dataset.person); });
}

/* ---------- Library ---------- */
function publications() {
  const terms = parseSearchQuery($('#search').value), awardOnly = $('#award-only').checked, sort = $('#sort').value;
  library = current.filter(p => (!awardOnly || p.award) && matchesSearch(p, terms));
  library.sort((a, b) => sort === 'title'
    ? a.title.localeCompare(b.title)
    : ((sort === 'old' ? 1 : -1) * ((a.year || 0) - (b.year || 0)) || a.order - b.order));
  const pages = Math.max(1, Math.ceil(library.length / PAGE_SIZE));
  page = Math.min(page, pages - 1);
  $('#pub-count').textContent = library.length.toLocaleString('en-US');
  $('#pubs').innerHTML = library.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map(p => {
    const title = p.link ? `<a href="${esc(p.link)}">${esc(p.title)}</a>` : esc(p.title);
    const authors = p.people.map(name => name === D.author ? `<strong>${esc(name)}</strong>` : esc(name)).join(', ');
    const doi = p.doi ? `<a class="ext-link" href="https://doi.org/${esc(p.doi)}" aria-label="DOI of ${esc(p.title)}">DOI${EXT_ICON}</a>` : (p.link ? `<a class="ext-link" href="${esc(p.link)}" aria-label="Link to ${esc(p.title)}">Link${EXT_ICON}</a>` : '');
    const note = p.note ? `<span>${esc(p.note)}</span>` : '';
    const award = p.award ? `<span class="badge award-badge">${esc(p.award)}</span>` : '';
    return `<article class="pub"><div class="pub-year">${p.year || 'n.d.'}</div><div>`
      + `<h3 class="pub-title">${title}</h3><div class="pub-authors">${authors}</div>`
      + `<div class="pub-meta"><span class="badge"><i style="background:${TYPE_COLOR[p.type]}"></i>${esc(p.category)}</span><span>${esc(p.venue)}</span>${note}${doi}${award}${bibEntryPanel(p)}</div>`
      + '</div></article>';
  }).join('') || '<div class="empty"><p>No entries match.</p><p>Try fewer words, or <button type="button" class="text-button" id="empty-reset">reset the filters</button>.</p></div>';
  // The per-entry BibTeX toggle is a compact text control at the end of the meta line.
  $('#pubs').querySelectorAll('.bib-entry > summary').forEach(summary => { summary.className = 'bib-toggle'; });
  wireBibPanels($('#pubs'));
  const emptyReset = $('#empty-reset');
  if (emptyReset) emptyReset.onclick = () => { resetFilters(); $('#search').focus(); };
  filterInfo();
  $('#page-status').textContent = `Page ${page + 1} of ${pages}`;
  $('#prev').disabled = page === 0;
  $('#next').disabled = page >= pages - 1;
  $('#export-bib').disabled = !library.length;
}

const EXT_ICON = '<svg class="ext-icon" width="11" height="11" viewBox="0 0 12 12" aria-hidden="true" focusable="false"><path d="M4.5 2.5h5v5M9.5 2.5 3 9" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';

function downloadBib() {
  if (!library.length) return;
  const text = library.map(p => p.bibtex.trim()).join('\n\n') + '\n';
  const url = URL.createObjectURL(new Blob([text], { type: 'application/x-bibtex;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = 'cabrera-publications.bib';
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ---------- Data notes ---------- */
function notes() {
  const meta = D.meta, date = new Date(meta.snapshot + 'T00:00:00Z');
  const label = Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(date) : meta.snapshot;
  const categories = [...new Set(D.publications.map(p => p.category))]
    .map(category => `${count(D.publications, p => p.category === category)} ${category.toLowerCase()}${count(D.publications, p => p.category === category) === 1 ? '' : 's'}`)
    .join(', ').replace(/doctoral thesiss/, 'doctoral theses').replace(/thesiss/, 'theses');
  $('#notes-content').innerHTML =
    `<p><strong>Source.</strong> The page is built from one BibTeX file, last changed on ${esc(label)}. You can download the <a href="../assets/data/publications.bib">complete file</a>. It holds ${meta.rawEntries} entries: ${esc(categories)}.</p>`
    + `<p><strong>What is counted.</strong> Preprints are listed only until the paper is published. Datasets, demonstrations, patents, and the doctoral thesis appear as "other outputs" in the charts. `
    + `${meta.duplicatesRemoved ? plural(meta.duplicatesRemoved, 'entry').replace('entrys', 'entries') + ' with a DOI already listed ' + (meta.duplicatesRemoved === 1 ? 'was' : 'were') + ' left out.' : 'No entry shares a DOI with another one.'}</p>`
    + `<p><strong>Names.</strong> Different spellings of one coauthor count as one person when the surname and the given name or initial agree, ignoring accents. `
    + `${meta.venueNormalization ? `Venue names are grouped by a curated list, so that ${meta.venueNormalization.suppliedNames} supplied names become ${meta.venueNormalization.venues} venues.` : ''}</p>`
    + `<p><strong>No citation counts.</strong> This page shows what was published and with whom. It makes no estimate of impact.</p>`;
  const rows = Object.entries(meta.spellings || {});
  $('#aliases').innerHTML = rows.length
    ? `<table class="alias-table"><thead><tr><th>Shown as</th><th>Spellings in the bibliography</th></tr></thead><tbody>${rows.map(([person, names]) =>
      `<tr><td>${esc(person)}</td><td>${names.map(esc).join('; ')}</td></tr>`).join('')}</tbody></table>`
    : '<p>Every person appears under one spelling.</p>';
}

/* ---------- Shareable view (query string) ---------- */
const URL_FIELDS = { from: '#from', to: '#to', type: '#type', coauthor: '#coauthor', q: '#search', sort: '#sort' };
function readUrl() {
  let params;
  try { params = new URLSearchParams(window.location.search); } catch (error) { return; }
  for (const [key, selector] of Object.entries(URL_FIELDS)) {
    const value = params.get(key), field = $(selector);
    if (value === null) continue;
    let wanted = value;
    if (key === 'type' && D) {
      const categories = [...new Set(D.publications.filter(p => p.type === value).map(p => p.category))];
      if (categories.length === 1) wanted = categories[0];
    }
    if (field.tagName === 'SELECT' && ![...field.options].some(option => option.value === wanted)) continue;
    field.value = wanted;
  }
  if (params.get('awards') === '1') $('#award-only').checked = true;
  if (+$('#from').value > +$('#to').value) $('#to').value = $('#from').value;
}
function syncUrl() {
  const defaults = { from: String(years[0]), to: String(years[years.length - 1]), type: '', coauthor: '', q: '', sort: 'new' };
  const params = new URLSearchParams();
  for (const [key, selector] of Object.entries(URL_FIELDS)) {
    const value = $(selector).value.trim();
    if (value !== defaults[key]) params.set(key, value);
  }
  if ($('#award-only').checked) params.set('awards', '1');
  const query = params.toString();
  try {
    window.history.replaceState(null, '', window.location.pathname + (query ? '?' + query : '') + window.location.hash);
  } catch (error) { /* a sandboxed frame may refuse; the page works without it */ }
}

/* ---------- Start ---------- */
async function init() {
  try {
    const response = await fetch('../assets/data/publications.json');
    if (!response.ok) throw new Error('HTTP ' + response.status);
    D = await response.json();
  } catch (error) {
    $('#stats').innerHTML = '<div class="panel" style="grid-column:1/-1">The publication list could not be loaded. Please reload the page, or download the <a href="../assets/data/publications.bib">BibTeX file</a>.</div>';
    console.error(error);
    return;
  }
  TYPES = D.types;
  TITLES = new Map(D.coauthors.filter(person => person.title).map(person => [person.name, person.title]));
  const dated = D.publications.map(p => p.year).filter(Boolean);
  years = [];
  for (let year = Math.min(...dated); year <= Math.max(...dated); year++) years.push(year);
  const options = years.map(year => `<option>${year}</option>`).join('');
  $('#from').innerHTML = options;
  $('#to').innerHTML = options;
  $('#from').value = years[0];
  $('#to').value = years[years.length - 1];
  const categories = [...new Set(D.publications.map(p => p.category))];
  $('#type').innerHTML += categories.map(category => `<option value="${esc(category)}">${esc(category)} (${count(D.publications, p => p.category === category)})</option>`).join('');
  $('#coauthor').innerHTML += D.coauthors.map(person => `<option value="${esc(person.name)}">${esc(person.name)} (${person.n ?? person.count})</option>`).join('');
  $('#flower-size').max = Math.max(8, Math.min(36, D.coauthors.length - D.coauthors.length % 2));

  readUrl();
  ['from', 'to', 'type', 'coauthor'].forEach(id => {
    $('#' + id).onchange = () => {
      if (id === 'coauthor') pair = null;
      if (+$('#from').value > +$('#to').value) {
        if (id === 'from') $('#to').value = $('#from').value; else $('#from').value = $('#to').value;
      }
      render();
    };
  });
  $('#reset').onclick = resetFilters;
  $('#flower-size').oninput = flower;
  $('#search').addEventListener('input', () => { page = 0; publications(); syncUrl(); });
  $('#award-only').onchange = () => { page = 0; publications(); syncUrl(); };
  $('#sort').onchange = () => { page = 0; publications(); syncUrl(); };
  const turn = (delta, button) => {
    page += delta;
    publications();
    $('#library').scrollIntoView({ behavior: scrollBehavior() });
    if (button.disabled) (button.id === 'next' ? $('#prev') : $('#next')).focus({ preventScroll: true });
  };
  $('#prev').onclick = () => turn(-1, $('#prev'));
  $('#next').onclick = () => turn(1, $('#next'));
  $('#export-bib').onclick = downloadBib;
  notes();
  render();
  // Redraw the pixel-sized charts when their containers change width.
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if ($('#timeline').clientWidth !== timelineWidth) timeline();
      if ($('#flower').clientWidth !== flowerWidth) flower();
    }, 150);
  });
  // Fonts change text widths, which set the flower's ring size.
  if (document.fonts?.ready) document.fonts.ready.then(flower);
}
init();
