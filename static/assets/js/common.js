'use strict';
// Shared by every page: section highlighting in the rail, and the e-mail address.

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
