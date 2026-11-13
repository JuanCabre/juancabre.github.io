"""Normalize venue names with generic rules and a curated alias file.

Taken from the Publication Observatory, with the paths adapted to this site: the
bibliography and its alias file live in ``data/``. Without ``data/venues.json`` the
venue strings are left exactly as supplied.

The rules only remove what never identifies a venue series: a "Proceedings of"
prefix, years, edition ordinals, and status remarks. Whether two differently
worded names are the same venue is decided by the alias file, never guessed.
The alias file also decides whether a workshop held at a conference counts toward
that conference (marked on the record) or toward a separate workshop venue.
The one built-in name is arXiv, which absorbs "arXiv preprint arXiv:..." entries.

Run ``python -m pipeline.venues`` for a report of what was merged.

A refreshed bibliography can bring wordings that no alias matches. ``venues-reviewed.txt``
lists the unmatched names that were looked at and left as they are, so that the build can
print only the ones that are new. ``python -m pipeline.venues --new`` prints the
same list, and ``--accept`` records every current unmatched name as reviewed.
"""
import difflib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ALIAS_FILE = 'venues.json'
REVIEWED_FILE = 'venues-reviewed.txt'
CONFERENCE_TYPES = ('inproceedings', 'conference')

PROCEEDINGS = re.compile(r'^(?:in:?\s+)?proc(?:eedings|\.)?(?:\s+of)?(?:\s+the)?\s+', re.I)
YEAR = re.compile(r"\b(?:19|20)\d{2}\b|(?<=[A-Za-z])(?:19|20)\d{2}\b|\s?['’‘`]\s?\d{2}\b")
ORDINAL = re.compile(r'\b(?:\d+(?:st|nd|rd|th|ST|ND|RD|TH)|[IVXL]+th)\b')
UNITS = 'first|second|third|fourth|fifth|sixth|seventh|eighth|ninth'
WORD_ORDINAL = re.compile(
    rf'\b(?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)[- ](?:{UNITS})'
    rf'|{UNITS}|tenth|eleventh|twelfth|(?:thir|four|fif|six|seven|eigh|nine)teenth'
    r'|(?:twent|thirt|fort|fift|sixt|sevent|eight|ninet)ieth)\b', re.I)
STATUS = re.compile(
    r'^\s*accepted\s+(?:at|for)\s+|\(?\bto appear\b\)?|,?\s*\baccepted(?:\s+for\s+publication)?\s*$', re.I)
PARENTHETICAL = re.compile(r'\(([^()]*)\)|\(([^()]*)$')
DELIMITER = re.compile(r'\s*[:;]\s+|\s+(?:-{1,2}|–|—)\s+')
WORKSHOP = re.compile(r'\b(?:workshops?|wkshps?|ws\d+)\b', re.I)
REPEATED_PARENTHETICAL = re.compile(r'(\([^()]*\))\s*\([^()]*\)?\s*$')
PREPRINT = re.compile(r'^arxiv\b', re.I)
ACRONYM = re.compile(r'(?<![\w-])(?=[A-Za-z0-9]*[A-Z][A-Za-z0-9]*[A-Z])[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*(?![\w-])')
ORGANIZERS = frozenset('ACM CVF EAI GI IEEE IFAC IFIP ITG KuVS OSA RSJ SPIE USENIX VDE'.split())


def tidy(text):
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+([,;:.)])', r'\1', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip(' -–—:;,.')


def clean_name(raw, proceedings=True, editions=True):
    """Remove the proceedings prefix, years, and edition numbers; keep the wording."""
    text = raw
    if proceedings:
        text = PROCEEDINGS.sub('', text.strip())
    text = YEAR.sub(' ', text)
    text = tidy(ORDINAL.sub(' ', text) if editions else text)
    return REPEATED_PARENTHETICAL.sub(r'\1', text) or raw.strip()


def fold(text):
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', text.replace('&', ' and ')).strip()


def split_extras(raw, proceedings=True):
    """Return the name without parentheticals, and the text that was set aside."""
    text = STATUS.sub(' ', raw)
    extras = [clean_name(a or b) for a, b in PARENTHETICAL.findall(text)]
    return clean_name(PARENTHETICAL.sub(' ', text), proceedings), extras


def match_key(text):
    """Key used only to match a name against the alias file."""
    return ' '.join(re.sub(r'^the\b|\bannual\b', ' ', fold(WORD_ORDINAL.sub(' ', text))).split())


def match_keys(raw, proceedings=True):
    """Keys for one name, most specific first: as worded, without edition numbers, without parentheticals."""
    text = STATUS.sub(' ', raw)
    return (
        fold(clean_name(text, proceedings, editions=False)),
        match_key(clean_name(text, proceedings)),
        match_key(split_extras(raw, proceedings)[0]),
    )


AMBIGUOUS = object()


class Aliases:
    def __init__(self, config):
        venues = self.venues = config.get('venues', {})
        self.workshops = dict(config.get('workshops', {}))
        self.parents = {workshop: conference for conference, workshop in self.workshops.items()}
        self.workshops_with_conference = bool(config.get('count_workshops_with_conference', False))
        missing = [name for pair in self.workshops.items() for name in pair if name not in venues]
        if missing:
            raise ValueError(f'Workshop mappings name venues that are not listed: {missing}')
        # Two venues may share a looser key, such as two names that differ only in a
        # parenthetical. That key then matches neither. The same wording under two venues is an error.
        self.index = ({}, {}, {})
        for canonical, variants in venues.items():
            for variant in (canonical, *variants):
                for proceedings in (False, True):
                    for level, key in enumerate(match_keys(variant, proceedings)):
                        known = self.index[level].setdefault(key, canonical)
                        if known is canonical or known == canonical:
                            continue
                        if level == 0:
                            raise ValueError(f'Venue alias {variant!r} is listed for both {known!r} and {canonical!r}.')
                        self.index[level][key] = AMBIGUOUS

    def find(self, level, key):
        canonical = self.index[level].get(key)
        return None if canonical is AMBIGUOUS else canonical

    def match(self, raw, proceedings=True):
        """Return (listed venue, whether the name describes a co-located workshop), or None."""
        for strip in ((False, True) if proceedings else (False,)):
            exact, named, _ = match_keys(raw, strip)
            canonical = self.find(0, exact) or self.find(1, named)
            if canonical:
                return canonical, False
            name, extras = split_extras(raw, strip)
            cuts = [match.start() for match in DELIMITER.finditer(name)]
            for cut in [len(name), *reversed(cuts)]:
                head, tail = name[:cut], name[cut:]
                canonical = self.find(2, match_key(head))
                if not canonical:
                    continue
                # A track or symposium belongs to the conference itself. A co-located workshop
                # is flagged, unless the remainder only restates the conference.
                rest = [DELIMITER.sub(' ', tail, 1), *extras]
                workshop = not WORKSHOP.search(head) and any(
                    WORKSHOP.search(part) and self.find(2, match_key(part)) != canonical for part in rest)
                return canonical, workshop
        return None

    def resolve(self, raw, proceedings=True):
        """Return (venue to show, counted there as a workshop). The venue is None when no alias applies."""
        if PREPRINT.match(raw):
            return 'arXiv', False
        canonical, workshop = self.match(raw, proceedings) or (None, False)
        if canonical is None:
            return None, False
        if self.workshops_with_conference:
            if canonical in self.parents:
                return self.parents[canonical], True
            return canonical, workshop
        if workshop:
            return self.workshops.get(canonical), False
        return canonical, False

    def lookup(self, raw, proceedings=True):
        """Return the venue to show for a supplied name, or None when no alias applies."""
        return self.resolve(raw, proceedings)[0]


def load_aliases(source):
    path = Path(source) / ALIAS_FILE
    if not path.exists():
        return None
    return Aliases(json.loads(path.read_text(encoding='utf-8')))


def normalize_venues(publications, aliases):
    """Rewrite each publication's venue in place and return {venue: Counter(supplied names)}.

    A workshop counted under its conference is marked with ``workshop: True``.
    """
    cleaned, forms = {}, defaultdict(Counter)
    for publication in publications:
        raw = publication['venue']
        if not raw:
            continue
        proceedings = publication.get('bibType') != 'article'
        canonical, workshop = aliases.resolve(raw, proceedings)
        if workshop:
            publication['workshop'] = True
        if canonical:
            cleaned[id(publication)] = canonical
        elif publication.get('bibType') in CONFERENCE_TYPES:
            name = clean_name(STATUS.sub(' ', raw))
            key = fold(name)
            forms[key][name] += 1
            cleaned[id(publication)] = ('rule', key)
        else:
            cleaned[id(publication)] = raw
    display = {key: min(names, key=lambda name: (-names[name], name)) for key, names in forms.items()}
    merged = defaultdict(Counter)
    for publication in publications:
        venue = cleaned.get(id(publication))
        if venue is None:
            continue
        if isinstance(venue, tuple):
            venue = display[venue[1]]
        merged[venue][publication['venue']] += 1
        publication['venue'] = venue
    return merged


def show(text):
    """Print text that may hold characters the console cannot encode, as on Windows."""
    encoding = sys.stdout.encoding or 'utf-8'
    print(text.encode(encoding, 'replace').decode(encoding))


def unlisted_names(publications, aliases):
    """Count the supplied names that no alias matches, cleaned by the rules. Call before normalize_venues."""
    names = Counter()
    for publication in publications:
        raw = publication['venue']
        proceedings = publication.get('bibType') != 'article'
        if raw and aliases.resolve(raw, proceedings)[0] is None:
            names[clean_name(STATUS.sub(' ', raw), proceedings)] += 1
    return names


def suggester(aliases):
    """Return a function that names the listed venues a new name may belong to.

    This is a hint for the person editing the alias file. It is never applied to the data.
    A workshop series is suggested as its conference, which is where the alias file lists both.
    """
    def family(venue):
        return aliases.parents.get(venue, venue)

    keys = {key: family(venue) for key, venue in aliases.index[2].items() if venue is not AMBIGUOUS}
    phrases = sorted((key for key in keys if len(key.split()) >= 3), key=len, reverse=True)
    owners = defaultdict(set)
    for canonical, variants in aliases.venues.items():
        for name in (canonical, *variants):
            for acronym in set(ACRONYM.findall(name)) - ORGANIZERS:
                owners[acronym].add(family(canonical))

    def suggest(name):
        padded = f' {match_key(name)} '
        for phrase in phrases:
            if f' {phrase} ' in padded:
                return [keys[phrase]]
        shared = [owners[acronym] for acronym in ACRONYM.findall(name) if 0 < len(owners.get(acronym, ())) <= 2]
        if shared:
            return sorted(min(shared, key=len))
        close = difflib.get_close_matches(match_key(split_extras(name)[0]), phrases, 1, 0.9)
        return [keys[close[0]]] if close else []

    return suggest


def read_reviewed(source):
    path = Path(source) / REVIEWED_FILE
    if not path.exists():
        return set()
    lines = path.read_text(encoding='utf-8').splitlines()
    return {fold(line) for line in lines if line.strip() and not line.startswith('#')}


def new_names(source, publications, aliases):
    """Return [(name, records, suggested venues)] for unmatched names that are not in the reviewed file."""
    reviewed, suggest = read_reviewed(source), suggester(aliases)
    names = unlisted_names(publications, aliases)
    return [(name, names[name], suggest(name)) for name in sorted(names, key=lambda name: (-names[name], name))
            if fold(name) not in reviewed]


SOURCE = Path(__file__).resolve().parent.parent / 'data'


def raw_publications(source):
    from .prepare_data import build_data
    config = json.loads((Path(source).parent / 'site.json').read_text(encoding='utf-8'))
    return build_data(Path(source), config, snapshot='', normalize_names=False)['publications']


def new_names_notice(source):
    """Return the text to print after a build, or '' when every unmatched name was reviewed."""
    source = Path(source)
    aliases = load_aliases(source)
    found = new_names(source, raw_publications(source), aliases) if aliases else []
    if not found:
        return ''
    lines = [f'{len(found)} venue name{"s are" if len(found) > 1 else " is"} new and matched by no alias:']
    for name, count, suggestions in found:
        hint = f'   (may be: {" or ".join(suggestions)})' if suggestions else ''
        lines.append(f'  {count} × {name}{hint}')
    lines.append(f'Add a wording to data/{ALIAS_FILE} to count it under a listed venue. '
                 'To keep the rest as they are: python -m pipeline.venues --accept')
    return '\n'.join(lines)


def write_reviewed(source, names):
    """Record these unmatched names as reviewed, replacing the file, and return how many there are."""
    source = Path(source)
    kept = {}
    for name in sorted(names, key=lambda name: (-names[name], name)):
        kept.setdefault(fold(name), name)
    header = (f'# Venue names that no alias in {ALIAS_FILE} matches and that were reviewed and left as they are.\n'
              '# The build prints unmatched names that are missing here. Rewritten by:\n'
              '# python -m pipeline.venues --accept\n')
    body = ''.join(f'{name}\n' for name in sorted(kept.values(), key=str.casefold))
    (source / REVIEWED_FILE).write_text(header + body, encoding='utf-8', newline='\n')
    return len(kept)


def report(source=SOURCE):
    aliases = load_aliases(source)
    if aliases is None:
        return f'No {ALIAS_FILE}, venue names are used as supplied.'
    publications = raw_publications(source)
    merged = normalize_venues(publications, aliases)
    workshops = Counter(publication['venue'] for publication in publications if publication.get('workshop'))
    supplied = sum(len(names) for names in merged.values())
    groups = {venue: names for venue, names in merged.items() if len(names) > 1}
    lines = [
        '# Venue normalization report', '',
        f'{supplied} supplied venue names became {len(merged)} venues. '
        f'{len(groups)} venues combine more than one supplied name; they are listed below, largest first.',
        *([f'{sum(workshops.values())} records are workshops counted under their conference.'] if workshops else []), '',
    ]
    for venue, names in sorted(groups.items(), key=lambda item: (-sum(item[1].values()), item[0])):
        note = f', {workshops[venue]} of them workshop records' if workshops[venue] else ''
        lines.append(f'## {venue} ({sum(names.values())} records{note}, {len(names)} names)')
        lines.extend(f'- {count} × {name}' for name, count in sorted(names.items(), key=lambda item: (-item[1], item[0])))
        lines.append('')
    return '\n'.join(lines)


def main(options):
    if not options:
        return report()
    if load_aliases(SOURCE) is None:
        return f'No {ALIAS_FILE}, venue names are used as supplied.'
    if options == ['--accept']:
        count = write_reviewed(SOURCE, unlisted_names(raw_publications(SOURCE), load_aliases(SOURCE)))
        return f'{count} unmatched venue names recorded in {REVIEWED_FILE}.'
    if options == ['--new']:
        return new_names_notice(SOURCE) or 'No new venue names.'
    raise SystemExit(f'Unknown option: {" ".join(options)}. Use --new or --accept.')


if __name__ == '__main__':
    show(main(sys.argv[1:]))
