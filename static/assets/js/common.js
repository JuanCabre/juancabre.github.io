'use strict';
// Shared by every page: the light and dark toggle, section highlighting in the rail, and the e-mail address.

// Light and dark mode. A first visit follows the system setting; a visitor who picks a mode keeps it,
// because the choice is saved and applied by the small script in the page head before the first paint.
(function () {
  const button = document.querySelector('.theme-toggle');
  if (!button) return;
  const root = document.documentElement;
  const current = () => (root.dataset.theme === 'dark' ? 'dark' : 'light');
  const show = () => {
    const dark = current() === 'dark';
    button.setAttribute('aria-pressed', String(dark));
    button.title = dark ? 'Switch to light mode' : 'Switch to dark mode';
  };
  const apply = theme => {
    if (theme === 'dark') root.dataset.theme = 'dark';
    else delete root.dataset.theme;
    show();
  };
  button.addEventListener('click', () => {
    const next = current() === 'dark' ? 'light' : 'dark';
    apply(next);
    try {
      localStorage.setItem('theme', next);
    } catch (error) { /* storage may be blocked; the choice then lasts for this page only */ }
  });
  // keep other open tabs of the site in step
  const system = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  const saved = () => { try { return localStorage.getItem('theme'); } catch (error) { return null; } };
  const resolve = value => (value === 'dark' || value === 'light' ? value : (system && system.matches ? 'dark' : 'light'));
  window.addEventListener('storage', event => { if (event.key === 'theme') apply(resolve(event.newValue)); });
  // without a saved choice, follow the system when it switches (for example at sunset)
  if (system) system.addEventListener('change', () => { if (!saved()) apply(resolve(null)); });
  button.hidden = false;
  show();
})();

// Highlight the section link that is currently in view.
(function () {
  const links = [...document.querySelectorAll('.page-nav a[href^="#"]')];
  const sections = links.map(link => document.getElementById(link.getAttribute('href').slice(1))).filter(Boolean);
  if (!sections.length) return;
  const mark = () => {
    const line = window.scrollY + window.innerHeight * 0.3;
    let current = null;
    for (const section of sections) {
      if (section.getBoundingClientRect().top + window.scrollY <= line) current = section;
    }
    // At the bottom of the page the last section may never reach the line.
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) current = sections[sections.length - 1];
    let shown = null;
    links.forEach(link => {
      const on = Boolean(current) && link.getAttribute('href') === '#' + current.id;
      link.classList.toggle('active', on);
      if (on) { link.setAttribute('aria-current', 'location'); shown = link; } else link.removeAttribute('aria-current');
    });
    // On narrow screens the rail scrolls sideways: keep the current link in view.
    const rail = shown && shown.parentElement;
    if (rail && rail.scrollWidth > rail.clientWidth && shown !== lastShown) {
      const left = shown.offsetLeft - rail.offsetLeft, right = left + shown.offsetWidth;
      if (left < rail.scrollLeft || right > rail.scrollLeft + rail.clientWidth - 32) rail.scrollLeft = left - 16;
    }
    lastShown = shown;
  };
  let lastShown = null;
  let queued = false;
  window.addEventListener('scroll', () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; mark(); });
  }, { passive: true });
  window.addEventListener('resize', mark);
  mark();
})();

// The address is assembled here so that it does not sit in the page source as one string.
(function () {
  document.querySelectorAll('[data-mail-user]').forEach(node => {
    const address = node.dataset.mailUser + '@' + node.dataset.mailDomain;
    const text = document.createElement('a');
    text.href = 'mailto:' + address;
    text.className = 'mail-link';
    text.textContent = address;
    node.classList.add('mail-row');
    node.replaceChildren(text);
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'button small';
    copy.textContent = 'Copy';
    const said = document.createElement('span');
    said.className = 'visually-hidden';
    said.setAttribute('role', 'status');
    copy.onclick = async () => {
      try {
        await navigator.clipboard.writeText(address);
        copy.textContent = 'Copied';
        said.textContent = 'E-mail address copied';
      } catch (error) {
        const range = document.createRange();
        range.selectNodeContents(text);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        copy.textContent = 'Selected';
        said.textContent = 'E-mail address selected; press Ctrl+C to copy';
      }
      setTimeout(() => { copy.textContent = 'Copy'; said.textContent = ''; }, 2000);
    };
    node.append(copy, said);
  });
  document.querySelectorAll('a[data-mail-link]').forEach(link => {
    link.href = 'mailto:' + link.dataset.mailLink + '@' + link.dataset.mailDomain;
  });
})();

// Research map: pointing at or focusing a line or station lights that line and dims the others.
(function () {
  const map = document.querySelector('.netmap');
  if (!map) return;
  const set = line => { if (line) map.dataset.active = line; else delete map.dataset.active; };
  map.querySelectorAll('a[data-line]').forEach(link => {
    link.addEventListener('pointerenter', () => set(link.dataset.line));
    link.addEventListener('pointerleave', () => set(null));
    link.addEventListener('focus', () => set(link.dataset.line));
    link.addEventListener('blur', () => set(null));
  });
})();
