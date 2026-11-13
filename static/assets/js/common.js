'use strict';
// Shared by every page: the light and dark toggle, section highlighting in the rail, and the e-mail address.

// Light and dark mode. The page follows the system setting until the visitor picks the other mode;
// that choice is saved and applied by the small script in the page head before the first paint.
// Picking the mode the system already uses clears the saved choice, so the page follows the system again.
(function () {
  const button = document.querySelector('.theme-toggle');
  if (!button) return;
  const root = document.documentElement;
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const system = () => (media.matches ? 'dark' : 'light');
  const current = () => root.dataset.theme || system();
  const show = () => {
    const dark = current() === 'dark';
    button.setAttribute('aria-pressed', String(dark));
    button.title = dark ? 'Switch to light mode' : 'Switch to dark mode';
  };
  const apply = theme => {
    if (theme === 'light' || theme === 'dark') root.dataset.theme = theme;
    else delete root.dataset.theme;
    show();
  };
  button.addEventListener('click', () => {
    const next = current() === 'dark' ? 'light' : 'dark';
    const saved = next === system() ? null : next;
    apply(saved);
    try {
      if (saved) localStorage.setItem('theme', saved); else localStorage.removeItem('theme');
    } catch (error) { /* storage may be blocked; the choice then lasts for this page only */ }
  });
  media.addEventListener('change', show);
  // keep other open tabs of the site in step
  window.addEventListener('storage', event => { if (event.key === 'theme') apply(event.newValue); });
  button.hidden = false;
  show();
})();

// Highlight the rail link of the section that is currently in view.
(function () {
  const links = [...document.querySelectorAll('.page-nav a[href^="#"]')];
  const sections = links.map(link => document.getElementById(link.getAttribute('href').slice(1))).filter(Boolean);
  if (!sections.length) return;
  const mark = () => {
    const line = window.scrollY + window.innerHeight * 0.3;
    let current = sections[0];
    for (const section of sections) {
      if (section.getBoundingClientRect().top + window.scrollY <= line) current = section;
    }
    // At the bottom of the page the last section may never reach the line.
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) current = sections[sections.length - 1];
    links.forEach(link => link.classList.toggle('active', link.getAttribute('href') === '#' + current.id));
  };
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
    const text = document.createElement('span');
    text.textContent = address;
    text.style.userSelect = 'all';
    node.replaceChildren(text);
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'button small';
    copy.textContent = 'Copy';
    copy.style.marginLeft = '10px';
    copy.setAttribute('aria-label', 'Copy e-mail address');
    copy.onclick = async () => {
      try {
        await navigator.clipboard.writeText(address);
        copy.textContent = 'Copied';
      } catch (error) {
        const range = document.createRange();
        range.selectNodeContents(text);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        copy.textContent = 'Selected';
      }
      setTimeout(() => { copy.textContent = 'Copy'; }, 2000);
    };
    node.append(copy);
  });
  document.querySelectorAll('a[data-mail-link]').forEach(link => {
    link.href = 'mailto:' + link.dataset.mailLink + '@' + link.dataset.mailDomain;
  });
})();
