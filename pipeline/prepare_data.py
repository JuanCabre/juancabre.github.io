"""Convert the BibTeX file to the data the site reads.

Adapted from the Publication Observatory pipeline. The observatory tracks a roster of
project members; this site tracks one author and treats everyone else as a coauthor.
"""
import re
import unicodedata
from collections import Counter

from .bib_utils import latex_text, parse_bib
from .deduplication import duplicate_key, normalize_doi
from .venues import load_aliases, normalize_venues

# Category shown on each publication, by BibTeX entry type.
CATEGORIES = {
    'article': 'Journal article',
    'inproceedings': 'Conference paper',
    'conference': 'Conference paper',
    'book': 'Book chapter',
    'inbook': 'Book chapter',
    'incollection': 'Book chapter',
    'phdthesis': 'Doctoral thesis',
    'mastersthesis': 'Thesis',
}
# A keyword in the entry overrides the entry type.
KEYWORD_CATEGORIES = {
    'preprint': 'Preprint',
    'dataset': 'Dataset',
    'patent': 'Patent',
    'demo': 'Demonstration',
    'workshop-abstract': 'Workshop abstract',
}
# The charts group the categories into five types. The order is the stacking order.
TYPES = ('Journal', 'Conference', 'Book chapter', 'Preprint', 'Other')
TYPE_OF = {
    'Journal article': 'Journal',
    'Conference paper': 'Conference',
    'Book chapter': 'Book chapter',
    'Preprint': 'Preprint',
}


def clean(value):
    return re.sub(r'\s+', ' ', latex_text(value or '')).strip()


def normalize(name):
    for special, plain in (('ø', 'o'), ('Ø', 'O'), ('ß', 'ss'), ('æ', 'ae'), ('ł', 'l'), ('ı', 'i')):
        name = name.replace(special, plain)
    ascii_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9 ]', '', ascii_name.lower().replace('-', ' '))


def author_name(value):
    parts = clean(value).split(',')
    if len(parts) == 1:
        return parts[0]
    return f'{parts[-1].strip()} {parts[0].strip()}'


def signature(name):
    """Surname and first initial: the key that groups spellings of one person."""
    parts = normalize(name).split()
    return (parts[-1], parts[0][0]) if parts else None


def same_given_name(a, b):
    """Two spellings agree when one given name is an initial or both are equal."""
    first_a, first_b = normalize(a).split()[0], normalize(b).split()[0]
    return len(first_a) == 1 or len(first_b) == 1 or first_a == first_b


def canonical_people(names, aliases):
    """Map every spelling to one display name.

    Spellings that share a surname and a compatible given name count as one person,
    shown under the most frequent spelling (the longest one on a tie). An explicit
    alias always wins. Returns {spelling: display name}.
    """
    explicit = {normalize(spelling): person for spelling, person in aliases.items()}
    counts, groups = Counter(names), {}
    for name in counts:
        if normalize(name) in explicit:
            continue
        key = signature(name)
        for group in groups.setdefault(key, []):
            if all(same_given_name(name, other) for other in group):
                group.append(name)
                break
        else:
            groups[key].append([name])
    mapping = {name: explicit[normalize(name)] for name in counts if normalize(name) in explicit}
    for variants in groups.values():
        for group in variants:
            display = max(group, key=lambda name: (counts[name], len(name), name))
            mapping.update({name: display for name in group})
    return mapping


def category_of(entry):
    keywords = {word.strip().lower() for word in re.split(r'[,;]', entry.get('keywords', ''))}
    for keyword, category in KEYWORD_CATEGORIES.items():
        if keyword in keywords:
            return category
    return CATEGORIES.get(entry['ENTRYTYPE'].lower(), 'Other')


def title_and_venue(entry):
    """Use a named chapter as the title of a book chapter, with the book as its venue."""
    title = entry.get('title', 'Untitled')
    venue = entry.get('journal') or entry.get('booktitle')
    chapter = re.sub(r'^\s*(?:\d+|title)\s*:\s*', '', entry.get('chapter', ''))
    named = re.search(r'[A-Za-z]', chapter) and not re.fullmatch(r'(?i)(?:chapter|ch\.?)\s*\d+', chapter.strip())
    if entry['ENTRYTYPE'].lower() in ('inbook', 'incollection') and named:
        return clean(chapter), clean(venue or title)
    return clean(title), clean(venue or entry.get('howpublished') or entry.get('school') or entry.get('publisher', ''))


def award_mentions(entry):
    fields = ('award', 'awards', 'prize', 'note', 'annote')
    return '; '.join(
        clean(entry[field]) for field in fields if entry.get(field)
        and (field in fields[:3] or re.search(r'\b(award|prize|best paper)\b', entry[field], re.I))
    )


def link_of(entry, doi):
    if doi:
        return f'https://doi.org/{doi}'
    return entry.get('url', '').strip()


def build_data(source, config, snapshot, normalize_names=True):
    """Return the site data for the bibliography in ``source`` (a directory)."""
    owner = config['author']
    aliases = config.get('author_aliases', {})
    entries = parse_bib((source / 'publications.bib').read_text(encoding='utf-8-sig'))

    spelled = [
        author_name(value) for entry in entries
        for value in re.split(r'\s+and\s+', entry.get('author', '')) if value.strip()
    ]
    people = canonical_people(spelled, {**aliases, owner: owner})
    owner_spellings = sorted(name for name, person in people.items() if person == owner)
    if not owner_spellings:
        raise ValueError(f'No entry lists the site author {owner!r}.')

    publications, duplicates, without_owner, seen = [], [], [], set()
    for order, entry in enumerate(entries):
        authors = [author_name(value) for value in re.split(r'\s+and\s+', entry.get('author', '')) if value.strip()]
        identity = duplicate_key(entry)
        if identity in seen:
            duplicates.append(entry['ID'])
            continue
        if identity:
            seen.add(identity)
        persons = [people[name] for name in authors]
        if owner not in persons:
            without_owner.append(entry['ID'])
        year = re.search(r'\d{4}', entry.get('year', ''))
        kind = entry['ENTRYTYPE'].lower()
        category = category_of(entry)
        title, venue = title_and_venue(entry)
        doi = normalize_doi(entry.get('doi', '')) if identity else ''
        award = award_mentions(entry)
        note = clean(entry.get('note', ''))
        publications.append({
            'id': entry['ID'], 'order': order, 'title': title,
            'year': int(year[0]) if year else None,
            'type': TYPE_OF.get(category, 'Other'), 'category': category,
            'bibType': kind, 'bibtex': entry['rawBibtex'],
            'authors': authors, 'people': persons,
            'venue': venue, 'doi': doi, 'link': link_of(entry, doi),
            'note': '' if note == award else note, 'award': award,
        })
    venue_aliases = load_aliases(source) if normalize_names else None
    venues = normalize_venues(publications, venue_aliases) if venue_aliases else None

    coauthors = Counter(person for publication in publications for person in set(publication['people']) if person != owner)
    spellings = {}
    for name, person in people.items():
        spellings.setdefault(person, set()).add(name)
    return {
        'author': owner,
        'types': list(TYPES),
        'publications': publications,
        'coauthors': [{'name': name, 'count': count} for name, count in
                      sorted(coauthors.items(), key=lambda item: (-item[1], item[0]))],
        'meta': {
            'source': 'publications.bib', 'snapshot': snapshot,
            'rawEntries': len(entries), 'duplicatesRemoved': len(duplicates), 'duplicateIds': duplicates,
            'entriesWithoutAuthor': without_owner,
            'deduplication': 'Identical normalized valid DOI only.',
            'matching': 'Accent-insensitive surname and given name or initial, with explicit aliases.',
            'spellings': {person: sorted(names) for person, names in sorted(spellings.items()) if len(names) > 1},
            **({'venueNormalization': {
                'suppliedNames': sum(len(names) for names in venues.values()), 'venues': len(venues),
            }} if venues else {}),
        },
    }
