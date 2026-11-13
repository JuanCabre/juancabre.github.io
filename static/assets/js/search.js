'use strict';

// Publication-library search, taken from the Publication Observatory: every term must
// match (any order), ignoring case, accents and German/Nordic transliteration
// (Rötter = Rotter = Roetter).

// Letters that Unicode decomposition does not reduce to ASCII.
const SEARCH_LETTERS = { 'ß': 'ss', 'æ': 'ae', 'œ': 'oe', 'ø': 'o', 'ł': 'l', 'đ': 'd', 'ð': 'd', 'þ': 'th', 'ı': 'i' };
const SEARCH_PUNCTUATION = { '‐': '-', '‑': '-', '‒': '-', '–': '-', '—': '-', '−': '-', '‘': "'", '’': "'", '“': '"', '”': '"' };
const searchCache = new WeakMap();

// Lower case, accents removed, special letters spelled out, whitespace collapsed.
function searchFold(value) {
  return String(value ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/[ßæœøłđðþı]/g, c => SEARCH_LETTERS[c])
    .replace(/[‐‑‒–—−‘’“”]/g, c => SEARCH_PUNCTUATION[c])
    .replace(/\s+/g, ' ').trim();
}

// Collapses the umlaut transliterations so ä, ae and a compare equal (likewise ö/oe/o, ü/ue/u).
function searchCollapse(folded) {
  return folded.replace(/([aou])e+/g, '$1');
}

// Splits a query into terms; "quoted text" stays one term. DOI links reduce to the bare DOI.
function parseSearchQuery(query) {
  const terms = [];
  const pattern = /"([^"]*)"?|(\S+)/g;
  const folded = searchFold(query);
  let match;
  while ((match = pattern.exec(folded))) {
    let term = (match[1] ?? match[2]).trim();
    term = term.replace(/^(?:https?:\/\/)?(?:dx\.)?doi\.org\//, '').replace(/^doi:\s*/, '');
    if (term) terms.push({ plain: term, collapsed: searchCollapse(term) });
  }
  return terms;
}

function searchText(publication) {
  let text = searchCache.get(publication);
  if (!text) {
    const plain = searchFold([
      publication.title, ...(publication.authors || []), ...(publication.people || []),
      publication.venue, publication.category, publication.award, publication.note, publication.doi, publication.year
    ].filter(value => value !== undefined && value !== null && value !== '').join(' \n '));
    text = { plain, collapsed: searchCollapse(plain) };
    searchCache.set(publication, text);
  }
  return text;
}

// terms comes from parseSearchQuery; an empty list matches everything.
function matchesSearch(publication, terms) {
  if (!terms.length) return true;
  const text = searchText(publication);
  return terms.every(term => text.plain.includes(term.plain) || text.collapsed.includes(term.collapsed));
}

if (typeof module !== 'undefined') module.exports = { searchFold, searchCollapse, parseSearchQuery, matchesSearch };
