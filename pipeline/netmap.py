"""The research map of the About page, drawn as a transit diagram.

Foundations run in from the left to one interchange, from which the three research
directions branch. Each station is an entry of the bibliography; along each line the
stations run by year. The map is plain SVG written at build time, so the page needs no
script to show it. A compact key replaces it on narrow screens.
"""
import html
import json

# Geometry of the wide map, in SVG units.
WIDTH, TOP, BOTTOM = 1140, 44, 478
HUB = (380, 260)
BRANCH_X = 530            # where the diagonal branches turn horizontal
FIRST_X, LAST_X = 590, 1060
LINE_Y = {'F': 260, '1': 110, '2': 260, '3': 410}
FOUNDATION_X = (70, 175, 280)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _label(text, x, y, above, year, anchor='middle'):
    lines = text.split('|')
    step = 17
    if above:
        # the year sits closest to the line, the name above it
        rows = [(year, 'yr')] + [(part, 'nm') for part in reversed(lines)]
        out, cy = [], y - 18
        for value, cls in rows:
            out.append(f'<tspan class="{cls}" x="{x}" y="{cy}">{html.escape(value)}</tspan>')
            cy -= step
        return f'<text class="lbl" text-anchor="{anchor}">{"".join(reversed(out))}</text>'
    rows = [(part, 'nm') for part in lines] + [(year, 'yr')]
    out, cy = [], y + 30
    for value, cls in rows:
        out.append(f'<tspan class="{cls}" x="{x}" y="{cy}">{html.escape(value)}</tspan>')
        cy += step
    return f'<text class="lbl" text-anchor="{anchor}">{"".join(out)}</text>'


def _marker(kind, x, y):
    if kind == 'demo':
        return f'<rect class="mk mk-demo" x="{x - 7}" y="{y - 7}" width="14" height="14"/>'
    if kind == 'patent':
        return (f'<path class="mk mk-patent" d="M{x} {y - 9} L{x + 9} {y} L{x} {y + 9} L{x - 9} {y} Z"/>')
    return f'<circle class="mk" cx="{x}" cy="{y}" r="7.5"/>'


def _star(x, y, r=6.5):
    import math
    points = []
    for i in range(10):
        radius = r if i % 2 == 0 else r * 0.45
        angle = -math.pi / 2 + i * math.pi / 5
        points.append(f'{x + radius * math.cos(angle):.1f},{y + radius * math.sin(angle):.1f}')
    return f'<polygon class="star" points="{" ".join(points)}"><title>Best Demo Award</title></polygon>'


def _bullet(line_id, x, y, size=30):
    half = size / 2
    return (f'<g class="bullet" aria-hidden="true"><rect x="{x - half}" y="{y - half}" width="{size}" height="{size}" rx="3"/>'
            f'<text x="{x}" y="{y + 6}" text-anchor="middle">{line_id}</text></g>')


def _stations(line, by_id):
    stations = []
    for station in line['stations']:
        entry = by_id.get(station['key'])
        if entry is None:
            raise KeyError(f"network-map.json: {station['key']} names no entry in publications.bib")
        stations.append({**station, 'year': entry['year'], 'title': entry['title']})
    return sorted(stations, key=lambda s: s['year'])


def _station_group(line, station, x, y, above):
    label = _label(station['label'], x, y, above, str(station['year']))
    star = _star(x + 14, y - 13) if station.get('award') else ''
    title = html.escape(station['title'])
    return (f'<a class="st" href="#p-{html.escape(station["key"])}" data-line="{line["id"]}">'
            f'<title>{title} ({station["year"]})</title>{_marker(station["kind"], x, y)}{star}{label}</a>')


def map_svg(config, by_id):
    """The wide map."""
    parts = []
    hub_x, hub_y = HUB
    lines = {line['id']: line for line in config['lines']}
    paths, groups = [], []
    for line_id, line in lines.items():
        y = LINE_Y[line_id]
        stations = _stations(line, by_id)
        if line_id == 'F':
            d = f'M{FOUNDATION_X[0] - 20} {y} H{hub_x}'
            xs = list(FOUNDATION_X)
        else:
            if y == hub_y:
                d = f'M{hub_x} {y} H{LAST_X + 30}'
            else:
                d = f'M{hub_x} {hub_y} L{BRANCH_X} {y} H{LAST_X + 30}'
            n = len(stations)
            gap = (LAST_X - FIRST_X) / (n - 1) if n > 1 else 0
            xs = [round(FIRST_X + i * gap) for i in range(n)]
        paths.append(f'<path class="ln" data-line="{line_id}" pathLength="1" d="{d}"/>')
        items = []
        for i, (station, x) in enumerate(zip(stations, xs)):
            above = (i % 2 == 0) if line_id != 'F' else True
            if line_id == '3':
                above = i % 2 == 1   # keep the lowest labels below the line, clear of line 2
            items.append(_station_group(line, station, x, y, above))
        end = (FOUNDATION_X[0] - 20 - 20, y) if line_id == 'F' else (LAST_X + 30 + 20, y)
        bullet = _bullet(line_id, *end)
        groups.append(f'<g class="line-group" data-line="{line_id}"><a class="line-link" href="#{line["anchor"]}" data-line="{line_id}">'
                      f'<title>Line {line_id}: {html.escape(line["name"])}</title>{bullet}</a>{"".join(items)}</g>')
    hub_lines = config['hub'].split('|')
    hub_label = ''.join(f'<tspan x="{hub_x - 6}" y="{hub_y + 40 + i * 17}">{html.escape(t)}</tspan>' for i, t in enumerate(hub_lines))
    hub = (f'<a class="hub" href="#about-text"><title>The central hypothesis, explained below</title>'
           f'<circle cx="{hub_x}" cy="{hub_y}" r="14"/>'
           f'<text class="lbl hub-lbl" text-anchor="end">{hub_label}</text></a>')
    parts.append('<g class="lines">' + ''.join(paths) + '</g>')
    parts.append(hub)
    parts.append(''.join(groups))
    height = BOTTOM - TOP
    return (f'<svg class="netmap" viewBox="0 {TOP} {WIDTH} {height}" role="group" '
            f'aria-labelledby="netmap-title"><title id="netmap-title">Research map: foundations lead to one interchange, '
            f'from which three research directions branch. Each station is a paper, demonstrator, or patent.</title>'
            + ''.join(parts) + '</svg>')


def map_key(config, by_id):
    """The compact key for narrow screens: one row per line with its stations as dots."""
    rows = []
    for line in config['lines']:
        stations = _stations(line, by_id)
        dots = ''.join(
            f'<i class="k-{s["kind"]}" title="{html.escape(s["label"].replace("|", " "))}, {s["year"]}"></i>' for s in stations)
        counts = {}
        for s in stations:
            counts[s['kind']] = counts.get(s['kind'], 0) + 1
        words = {'paper': ('paper', 'papers'), 'demo': ('demonstrator', 'demonstrators'), 'patent': ('patent', 'patents')}
        summary = ', '.join(f'{n} {words[k][n != 1]}' for k, n in counts.items())
        rows.append(f'<li><a href="#{line["anchor"]}" data-line="{line["id"]}">'
                    f'<span class="lb" aria-hidden="true">{line["id"]}</span>'
                    f'<span class="kn"><strong>{html.escape(line["name"])}</strong><span>{summary}</span></span>'
                    f'<span class="strip" aria-hidden="true">{dots}</span></a></li>')
    return '<ol class="netmap-key" aria-label="Research lines">' + ''.join(rows) + '</ol>'


def line_names(config):
    """The names of the lines, set under the wide map."""
    items = ''.join(
        f'<li><a href="#{line["anchor"]}" data-line="{line["id"]}"><span class="lb" aria-hidden="true">{line["id"]}</span>'
        f'{html.escape(line["name"])}</a></li>' for line in config['lines'])
    return f'<ol class="line-names" aria-label="Research lines">{items}</ol>'


def netmap_html(path, by_id):
    config = load(path)
    return map_svg(config, by_id) + line_names(config) + map_key(config, by_id)
