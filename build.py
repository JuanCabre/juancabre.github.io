"""Build the site into a directory of static files.

    python build.py                 # writes _site/
    python build.py --output dist   # writes dist/
    python build.py --url https://example.org/

Pages live in pages/, the shared frame in templates/base.html, and files that are
copied as they are in static/. The publications come from data/publications.bib.
No package installation is needed.
"""
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from pipeline.prepare_data import build_data
from pipeline.venues import new_names_notice, show

ROOT = Path(__file__).resolve().parent
TOKEN = re.compile(r'@@([A-Z0-9_]+)(?::([A-Za-z0-9_+.\-]+))?@@')
FRONT_MATTER = re.compile(r'\A\s*<!--(.*?)-->', re.S)
SECTION = re.compile(r'^<!--\s*@section\s+(\w+)\s*-->\s*$', re.M)
# Output path of each page, relative to the site root.
PAGES = {
    'index.html': 'index.html',
    'publications.html': 'publications/index.html',
    'legal.html': 'legal/index.html',
    '404.html': '404.html',
}
CV_FILE = 'cv/Juan-Cabrera-CV.pdf'
LIST_PAGE = 'publications/list/index.html'
LIST_PDF = 'publications/Juan-Cabrera-Publications.pdf'
# Sections of the printed publication list, in order: category, heading.
LIST_SECTIONS = (
    ('Conference paper', 'Conference Papers'),
    ('Journal article', 'Journal Articles'),
    ('Book chapter', 'Book Chapters'),
    ('Preprint', 'Preprints'),
    ('Dataset', 'Datasets and Research Data'),
    ('Workshop abstract', 'Workshop Contributions'),
    ('Demonstration', 'Conference Demonstrations'),
    ('Patent', 'Patents'),
    ('Doctoral thesis', 'Doctoral Thesis'),
)
BROWSERS = ('chrome-headless-shell', 'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser',
            'chrome', 'microsoft-edge')


def snapshot_date(path):
    """Date of the last change to the bibliography: its last commit, else the file date."""
    try:
        done = subprocess.run(['git', 'log', '-1', '--format=%cs', '--', str(path)],
                              cwd=ROOT, capture_output=True, text=True, timeout=20)
        if done.returncode == 0 and re.fullmatch(r'\d{4}-\d{2}-\d{2}', done.stdout.strip()):
            return done.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return date.fromtimestamp(path.stat().st_mtime).isoformat()


def read_page(path):
    """Split a page into its settings (leading comment) and its named sections."""
    text = path.read_text(encoding='utf-8')
    settings = {}
    front = FRONT_MATTER.match(text)
    if front:
        for line in front[1].strip().splitlines():
            key, _, value = line.partition(':')
            settings[key.strip()] = value.strip()
        text = text[front.end():]
    parts = SECTION.split(text)
    sections = {'main': parts[0]} if parts[0].strip() else {}
    sections.update({parts[i]: parts[i + 1].strip('\n') for i in range(1, len(parts), 2)})
    return settings, sections


def author_html(publication, owner):
    # People are shown under one spelling each, as set by the pipeline.
    names = [f'<strong>{html.escape(person)}</strong>' if person == owner else html.escape(person)
             for person in publication['people']]
    return ', '.join(names)


def citation_html(publication, owner):
    title = html.escape(publication['title'])
    if publication['link']:
        title = f'<a class="cite-title" href="{html.escape(publication["link"])}">{title}</a>'
    else:
        title = f'<span class="cite-title">{title}</span>'
    venue = ' · '.join(part for part in (html.escape(publication['venue']), str(publication['year'] or '')) if part)
    award = (f' <span class="badge award-badge">{html.escape(publication["award"])}</span>'
             if publication['award'] else '')
    return f'<li class="cite">{title}{author_html(publication, owner)}<br>{venue}{award}</li>'


def list_entry_html(publication, owner):
    """One line of the printed list: authors (year). Title. Venue. Details. Link."""
    authors = '; '.join(f'<strong>{html.escape(person)}</strong>' if person == owner else html.escape(person)
                        for person in publication['people'])
    venue = publication['venue']
    if venue and publication['category'] in ('Conference paper', 'Book chapter', 'Workshop abstract', 'Demonstration'):
        venue = 'In ' + venue
    parts = [venue, publication['details'], publication['award']]
    if publication['note'] and publication['note'] != publication['category']:
        parts.append(publication['note'])
    text = ''.join(f' {html.escape(part.rstrip("."))}.' for part in parts if part)
    link = ''
    if publication['link']:
        label = ('DOI: ' + publication['doi']) if publication['doi'] else publication['link']
        link = f' <a href="{html.escape(publication["link"])}">{html.escape(label)}</a>'
    title = html.escape(publication['title'])
    title += '' if title.endswith(('?', '!', '.')) else '.'
    return f'<li>{authors} ({publication["year"]}). <span class="t">{title}</span>{text}{link}</li>'


def list_html(publications, owner):
    """The complete list, grouped by kind, newest first. Returns (summary, sections)."""
    summary, sections = [], []
    known = [category for category, _ in LIST_SECTIONS]
    other = sorted({p['category'] for p in publications} - set(known))
    for category, heading in (*LIST_SECTIONS, *((name, name) for name in other)):
        group = sorted((p for p in publications if p['category'] == category),
                       key=lambda p: (-(p['year'] or 0), p['order']))
        if not group:
            continue
        summary.append(f'{heading}: {len(group)}')
        sections.append(f'<h2>{html.escape(heading)} ({len(group)})</h2>\n<ol>\n'
                        + '\n'.join(list_entry_html(p, owner) for p in group) + '\n</ol>')
    return ' | '.join(summary), '\n'.join(sections)


def find_browser():
    """A Chromium-based browser that can print a page to PDF, or None."""
    candidates = [os.environ.get('CHROME'), *BROWSERS]
    for candidate in candidates:
        path = candidate and (shutil.which(candidate) or (candidate if Path(candidate).is_file() else None))
        if path:
            return path
    return None


def print_pdf(browser, page, target):
    """Print ``page`` to ``target`` with a headless browser. Returns True on success."""
    profile = target.with_suffix('.profile')
    command = [browser, '--headless', '--no-sandbox', '--disable-gpu', '--no-pdf-header-footer',
               '--print-to-pdf-no-header', '--virtual-time-budget=10000', f'--user-data-dir={profile}',
               f'--print-to-pdf={target}', page.resolve().as_uri()]
    try:
        subprocess.run(command, capture_output=True, timeout=90, check=False)
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    return target.is_file() and target.read_bytes()[:5] == b'%PDF-'


def build(output, site_url=None, pdf='auto'):
    config = json.loads((ROOT / 'site.json').read_text(encoding='utf-8'))
    url = (site_url or config['site_url']).rstrip('/') + '/'
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.query or parsed.fragment:
        raise ValueError('Provide an absolute site URL without a query or fragment.')

    source = ROOT / 'data'
    snapshot = snapshot_date(source / 'publications.bib')
    data = build_data(source, config, snapshot)
    publications = data['publications']
    by_id = {publication['id']: publication for publication in publications}
    owner = data['author']
    day = date.fromisoformat(snapshot)
    years = [publication['year'] for publication in publications if publication['year']]

    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(ROOT / 'static', output)
    if not (output / CV_FILE).exists():
        raise FileNotFoundError(f'static/{CV_FILE} is missing. The pages link to it.')
    data_dir = output / 'assets' / 'data'
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    (data_dir / 'publications.json').write_text(payload, encoding='utf-8')
    shutil.copyfile(source / 'publications.bib', data_dir / 'publications.bib')

    digest = hashlib.sha256(payload.encode('utf-8'))
    for path in sorted((ROOT / 'static' / 'assets').rglob('*')):
        if path.suffix in ('.css', '.js'):
            digest.update(path.read_bytes())

    def count(test):
        return str(sum(1 for publication in publications if test(publication)))

    values = {
        'NAME': config['name'], 'SITE_URL': url, 'SITE_DESCRIPTION': config['description'],
        'SNAPSHOT_LABEL': f'{day.day} {day:%B %Y}', 'SNAPSHOT_ISO': snapshot,
        'V': digest.hexdigest()[:10], 'CV_FILE': CV_FILE, 'BUILD_YEAR': str(date.today().year),
        'COUNT_ALL': str(len(publications)),
        'COUNT_JOURNAL': count(lambda p: p['type'] == 'Journal'),
        'COUNT_CONFERENCE': count(lambda p: p['type'] == 'Conference'),
        'COUNT_BOOK': count(lambda p: p['type'] == 'Book chapter'),
        'COUNT_PREPRINT': count(lambda p: p['type'] == 'Preprint'),
        'COUNT_PATENT': count(lambda p: p['category'] == 'Patent'),
        'COUNT_AWARDS': count(lambda p: p['award']),
        'COUNT_COAUTHORS': str(len(data['coauthors'])),
        'YEAR_FIRST': str(min(years)), 'YEAR_LAST': str(max(years)),
    }
    # The printable list, and its PDF where a browser is available to print it.
    summary, sections = list_html(publications, owner)
    list_page = output / LIST_PAGE
    list_page.parent.mkdir(parents=True, exist_ok=True)
    browser = find_browser() if pdf != 'skip' else None
    if pdf == 'require' and not browser:
        raise RuntimeError('No Chromium-based browser found to print the publication list. '
                           'Install one, or point the CHROME environment variable to it.')

    def write_list(with_pdf):
        link = f'<a href="../{Path(LIST_PDF).name}">Download as PDF</a>' if with_pdf else ''
        fields = {**{key: html.escape(value) for key, value in values.items()},
                  'SUMMARY': html.escape(summary), 'LIST': sections, 'PDF_LINK': link}
        template = (ROOT / 'templates' / 'list.html').read_text(encoding='utf-8')
        list_page.write_text(TOKEN.sub(lambda match: fields[match[1]], template), encoding='utf-8')

    write_list(with_pdf=False)  # the PDF is printed from the page without its own download link
    has_pdf = bool(browser) and print_pdf(browser, list_page, output / LIST_PDF)
    if pdf == 'require' and not has_pdf:
        raise RuntimeError(f'{browser} did not produce the publication list PDF.')
    write_list(with_pdf=has_pdf)
    # Pages link to the PDF, or to the printable page when no PDF could be made.
    values['PUBLIST_FILE'] = LIST_PDF if has_pdf else LIST_PAGE[:-len('index.html')]
    values['PUBLIST_LABEL'] = 'Publication list (PDF)' if has_pdf else 'Publication list'

    lookups = {
        'PUB': lambda p: citation_html(p, owner),
        'PUBLINK': lambda p: html.escape(p['link']),
        'PUBTITLE': lambda p: html.escape(p['title']),
    }

    base = (ROOT / 'templates' / 'base.html').read_text(encoding='utf-8')
    for name, target in PAGES.items():
        settings, sections = read_page(ROOT / 'pages' / name)
        depth = target.count('/')
        page = {
            # The 404 page is served at any address, so its links start at the site root.
            'ROOT': (parsed.path if name == '404.html' else '../' * depth),
            'PAGE_URL': url + (target[:-len('index.html')] if target.endswith('index.html') else target),
            'TITLE': html.escape(settings.get('title', config['name'])),
            'DESCRIPTION': html.escape(settings.get('description', config['description'])),
            'NAV': settings.get('nav', ''),
            **{key.upper(): value for key, value in sections.items()},
        }

        def replace(match, page=page, name=name):
            key, argument = match[1], match[2]
            if argument is not None:
                if key not in lookups:
                    raise KeyError(f'{name}: unknown token @@{key}:{argument}@@')
                if argument not in by_id:
                    raise KeyError(f'{name}: @@{key}:{argument}@@ names no entry in publications.bib')
                return lookups[key](by_id[argument])
            if key in page:
                return page[key]
            if key in values:
                return html.escape(values[key])
            if key in ('HEAD', 'PAGENAV', 'SCRIPTS'):
                return ''
            raise KeyError(f'{name}: unknown token @@{key}@@')

        text = base
        for _ in range(3):  # sections may contain tokens of their own
            text = TOKEN.sub(replace, text)
        # mark the current page in the site navigation
        text = text.replace(f'data-nav="{page["NAV"]}"', f'data-nav="{page["NAV"]}" aria-current="page"')
        destination = output / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding='utf-8')

    (output / '.nojekyll').write_text('', encoding='utf-8')
    (output / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {url}sitemap.xml\n', encoding='utf-8')
    listed = [target for target in PAGES.values() if target != '404.html']
    entries = ''.join(
        f'  <url><loc>{html.escape(url + (t[:-len("index.html")] if t.endswith("index.html") else t))}</loc>'
        f'<lastmod>{snapshot}</lastmod></url>\n' for t in listed)
    (output / 'sitemap.xml').write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{entries}</urlset>\n', encoding='utf-8')
    if config.get('custom_domain'):
        (output / 'CNAME').write_text(config['custom_domain'].strip() + '\n', encoding='utf-8')

    meta = data['meta']
    print(f"{len(publications)} entries, {len(data['coauthors'])} coauthors, bibliography of {snapshot}")
    print('Publication list PDF: ' + ('written' if has_pdf else 'not written (no browser to print it)' if pdf != 'skip' else 'skipped'))
    if meta['unknownProfessors']:
        print('Listed under "professors" in site.json but not a coauthor: ' + ', '.join(meta['unknownProfessors']))
    if meta['duplicateIds']:
        print('Duplicate DOIs removed: ' + ', '.join(meta['duplicateIds']))
    if meta['entriesWithoutAuthor']:
        print(f"Entries that do not list {owner}: " + ', '.join(meta['entriesWithoutAuthor']))
    notice = new_names_notice(source)
    if notice:
        show(notice)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--output', type=Path, default=ROOT / '_site', help='Directory to write (replaced if it exists)')
    parser.add_argument('--url', help='Public URL of the site, including its path if it has one')
    parser.add_argument('--pdf', choices=('auto', 'require', 'skip'), default='auto',
                        help='Publication list as PDF: auto prints it when a Chromium-based browser is found, '
                             'require fails without one, skip never prints')
    args = parser.parse_args()
    build(args.output.resolve(), args.url, args.pdf)
    print(args.output)


if __name__ == '__main__':
    main()
