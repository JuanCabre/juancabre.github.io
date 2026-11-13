'use strict';
// Per-publication BibTeX, taken from the Publication Observatory: shown inline in a
// collapsed panel with a copy button, so an entry can be read or copied without a download.

const bibEscape = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function bibEntryPanel(paper) {
  const text = String(paper?.bibtex ?? '').trim();
  if (!text) return '';
  const title = bibEscape(paper.title);
  return `<details class="bib-entry"><summary class="button small" aria-label="BibTeX for ${title}">BibTeX</summary>`
    + `<div class="bib-entry-body"><div class="bib-entry-tools"><button type="button" class="button small bib-copy" aria-label="Copy BibTeX for ${title}">Copy</button>`
    + `<span class="bib-copy-status" role="status" aria-live="polite"></span></div>`
    + `<pre class="bib-entry-text" tabindex="0">${bibEscape(text)}</pre></div></details>`;
}

function selectNodeText(node, env) {
  const selection = env.getSelection?.();
  const range = env.document?.createRange?.();
  if (!selection || !range) return false;
  range.selectNodeContents(node);
  selection.removeAllRanges();
  selection.addRange(range);
  return true;
}

// Returns 'copied' when the text reached the clipboard and 'selected' when the
// browser refused (for example inside a sandboxed frame), leaving the entry
// selected so Ctrl+C or Cmd+C copies it.
async function copyBibText(text, node, env = globalThis) {
  try {
    if (env.navigator?.clipboard?.writeText) {
      await env.navigator.clipboard.writeText(text);
      return 'copied';
    }
  } catch (error) { /* fall back to selecting the text */ }
  const selected = node ? selectNodeText(node, env) : false;
  try {
    if (selected && env.document?.execCommand?.('copy')) return 'copied';
  } catch (error) { /* keep the selection for a manual copy */ }
  return selected ? 'selected' : 'failed';
}

const BIB_COPY_MESSAGES = {
  copied: 'Copied',
  selected: 'Selected. Press Ctrl+C (Cmd+C on Mac) to copy.',
  failed: 'Copy failed. Select the entry to copy it.'
};

function wireBibPanels(root, env = globalThis) {
  root.querySelectorAll('.bib-entry').forEach(panel => {
    const button = panel.querySelector('.bib-copy'), pre = panel.querySelector('.bib-entry-text'), status = panel.querySelector('.bib-copy-status');
    if (!button || !pre) return;
    button.onclick = async () => {
      const result = await copyBibText(pre.textContent, pre, env);
      if (status) status.textContent = BIB_COPY_MESSAGES[result];
      if (result === 'copied' && env.setTimeout) env.setTimeout(() => { if (status && status.textContent === BIB_COPY_MESSAGES.copied) status.textContent = ''; }, 2000);
    };
  });
}

if (typeof module !== 'undefined') module.exports = { bibEntryPanel, copyBibText };
