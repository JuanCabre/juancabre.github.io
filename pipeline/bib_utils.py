import re, unicodedata

ACCENTS = {'"': '\u0308', "'": '\u0301', '`': '\u0300', '^': '\u0302', '~': '\u0303', '=': '\u0304', '.': '\u0307',
           'u': '\u0306', 'v': '\u030c', 'H': '\u030b', 'c': '\u0327', 'k': '\u0328', 'b': '\u0331', 'd': '\u0323',
           'r': '\u030a', 't': '\u0361'}
LETTERS = {'ss': 'ß', 'ae': 'æ', 'AE': 'Æ', 'oe': 'œ', 'OE': 'Œ', 'aa': 'å', 'AA': 'Å', 'o': 'ø', 'O': 'Ø',
           'l': 'ł', 'L': 'Ł', 'i': 'i', 'j': 'j'}
SYMBOLS = {'textasteriskcentered': '*', 'textendash': '–', 'textemdash': '—', 'textregistered': '®',
           'texttrademark': '™', 'textdegree': '°', 'textmu': 'μ', 'infty': '∞', 'pm': '±', 'times': '×',
           'cdot': '·', 'approx': '≈', 'leq': '≤', 'geq': '≥', 'le': '≤', 'ge': '≥', 'to': '→', 'rightarrow': '→',
           'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ', 'epsilon': 'ε', 'varepsilon': 'ε', 'zeta': 'ζ',
           'eta': 'η', 'theta': 'θ', 'iota': 'ι', 'kappa': 'κ', 'lambda': 'λ', 'mu': 'μ', 'nu': 'ν', 'xi': 'ξ',
           'pi': 'π', 'rho': 'ρ', 'sigma': 'σ', 'tau': 'τ', 'phi': 'φ', 'varphi': 'φ', 'chi': 'χ', 'psi': 'ψ',
           'omega': 'ω', 'Gamma': 'Γ', 'Delta': 'Δ', 'Theta': 'Θ', 'Lambda': 'Λ', 'Xi': 'Ξ', 'Pi': 'Π',
           'Sigma': 'Σ', 'Phi': 'Φ', 'Psi': 'Ψ', 'Omega': 'Ω'}
# Commands whose argument is kept as plain text.
WRAPPERS = ('textit', 'textbf', 'textsc', 'textrm', 'textsf', 'texttt', 'textup', 'textnormal', 'emph', 'text',
            'mathrm', 'mathit', 'mathbf', 'mathcal', 'mathsf', 'mathtt', 'mathbb', 'operatorname', 'url', 'mbox',
            'hbox', 'ensuremath')
DROPPED = ('strut', 'relax', 'protect', 'xspace')
SUB = dict(zip('0123456789+-=()', '₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎'))
SUP = dict(zip('0123456789+-=()', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾'))
GROUP = r'\{((?:[^{}]|\{[^{}]*\})*)\}'  # a brace group with at most one level of nesting


def _script(marker, table):
    def convert(m):
        body = (m[1] if m[1] is not None else m[2]).replace('{', '').replace('}', '').strip()
        return ''.join(table[c] for c in body) if body and all(c in table for c in body) else marker + body
    return convert


def _math(m):
    s = m[1]
    s = re.sub(r'_\s*(?:\{([^{}]*)\}|(\S))', _script('_', SUB), s)
    s = re.sub(r'\^\s*(?:\{([^{}]*)\}|(\S))', _script('^', SUP), s)
    return s


def latex_text(s):
    """Turn the LaTeX found in BibTeX fields into plain Unicode text."""
    s = s.replace('\\$', '\x00')
    # \"Name\" written as quotation marks rather than umlauts: the closing \" is followed by no letter.
    s = re.sub(r'\\"([A-Za-z][^\\"$]*?)\\"(?![A-Za-z{])', '“\\1”', s)
    # Letter commands are matched only as whole words, so \tau or \delta never count as the \t or \d accents.
    s = re.sub(r'\\(' + '|'.join(sorted(LETTERS, key=len, reverse=True)) + r')(?![A-Za-z])\s*', lambda m: LETTERS[m[1]], s)
    s = re.sub(r'\\(?:([\"\x27`^~=.])|([uvHckbdtr])(?![A-Za-z]))\s*(?:\{\s*([A-Za-z])\s*\}|([A-Za-z]))',
               lambda m: m[3 if m[3] else 4] + ACCENTS[m[1] or m[2]], s)
    s = unicodedata.normalize('NFC', s)
    s = re.sub(r'\\(' + '|'.join(SYMBOLS) + r')(?![A-Za-z])(?:\{\})?', lambda m: SYMBOLS[m[1]], s)
    s = re.sub(r'\\(?:' + '|'.join(DROPPED) + r')(?![A-Za-z])\s*', '', s)
    s = re.sub(r'\\enquote\s*' + GROUP, lambda m: '\u201c' + m[1] + '\u201d', s)
    s = re.sub(r'\\(?:MakeUppercase|uppercase)\s*' + GROUP, lambda m: m[1].upper(), s)
    for _ in range(3):  # unwrap nested wrappers from the inside out
        s = re.sub(r'\\(?:' + '|'.join(WRAPPERS) + r')(?![A-Za-z])\s*\{([^{}]*)\}', r'\1', s)
    s = re.sub(r'\\(?:' + '|'.join(WRAPPERS) + r')(?![A-Za-z])\s*', '', s)
    s = re.sub(r'\$([^$]*)\$', _math, s)
    s = re.sub(r'\\[,;: ]', ' ', s).replace('\\!', '').replace('\\-', '').replace('\\/', '')
    s = re.sub(r'\\([&%_#])', r'\1', s).replace('~', ' ')
    return s.replace('{', '').replace('}', '').replace('\x00', '$')


def parse_bib(text):
 entries=[]; pos=0
 while True:
  m=re.search(r'@(\w+)\s*\{',text[pos:])
  if not m: break
  entry_start=pos+m.start()
  typ=m[1].lower(); start=pos+m.end(); i=start; depth=1
  while i<len(text) and depth:
   if text[i]=='\\': i+=2; continue
   if text[i]=='{': depth+=1
   elif text[i]=='}': depth-=1
   i+=1
  if depth: raise ValueError('Unbalanced bibliography')
  body=text[start:i-1]; pos=i
  if typ in ['comment','preamble','string']: continue
  key,sep,rest=body.partition(',')
  e={'ENTRYTYPE':typ,'ID':key.strip(),'rawBibtex':text[entry_start:i]}; j=0
  while j<len(rest):
   f=re.match(r'\s*,?\s*([\w-]+)\s*=\s*',rest[j:])
   if not f: break
   j+=f.end(); begin=j
   if rest[j:j+1]=='{':
    j+=1; begin=j; d=1
    while j<len(rest) and d:
     if rest[j]=='\\': j+=2; continue
     if rest[j]=='{': d+=1
     elif rest[j]=='}': d-=1
     j+=1
    val=rest[begin:j-1]
   elif rest[j:j+1]=='"':
    j+=1; begin=j
    while j<len(rest) and (rest[j]!='"' or rest[j-1]=='\\'): j+=1
    val=rest[begin:j]; j+=1
   else:
    while j<len(rest) and rest[j]!=',': j+=1
    val=rest[begin:j].strip()
   e[f[1].lower()]=val
  entries.append(e)
 return entries
