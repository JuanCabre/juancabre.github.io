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
    star = _star(x + 14, y + 13 if above else y - 13) if station.get('award') else ''   # away from the label
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


# Geometry of the narrow map: lines run down the page. The three directions leave the
# interchange side by side; each one shows its stations in its own stretch and ends there,
# so the next one can take the label column. Labels sit to the right of the tracks.
V_WIDTH = 372
V_X = {'F': 42, '1': 62, '2': 42, '3': 22}
V_LABEL_X = 86
V_ROW, V_HEAD, V_GAP = 33, 44, 12


def _v_label(station, x, y):
    name = html.escape(station['label'].replace('|', ' '))
    return (f'<text class="lbl" x="{x}" y="{y + 5}"><tspan class="nm">{name}</tspan>'
            f'<tspan class="yr" dx="8">{station["year"]}</tspan></text>')


def _v_head(line, y):
    x = V_LABEL_X
    return (f'<a class="line-link" href="#{line["anchor"]}" data-line="{line["id"]}">'
            f'<title>Line {line["id"]}: {html.escape(line["name"])}</title>'
            f'{_bullet(line["id"], x + 11, y, size=22)}'
            f'<text class="lbl line-head" x="{x + 30}" y="{y + 5}">{html.escape(line["name"])}</text></a>')


def map_vertical(config, by_id):
    """The narrow map, drawn top to bottom."""
    lines = {line['id']: line for line in config['lines']}
    paths, groups = [], []
    y = 26
    # Foundations: a short trunk into the interchange
    f = lines['F']
    items = [_v_head(f, y)]
    y += V_HEAD - 10
    f_top = y - 14
    for station in _stations(f, by_id):
        items.append(f'<a class="st" href="#p-{html.escape(station["key"])}" data-line="F">'
                     f'<title>{html.escape(station["title"])} ({station["year"]})</title>'
                     f'{_marker(station["kind"], V_X["F"], y)}{_v_label(station, V_LABEL_X, y)}</a>')
        y += V_ROW
    hub_y = y + 4
    paths.append(f'<path class="ln" data-line="F" pathLength="1" d="M{V_X["F"]} {f_top} V{hub_y}"/>')
    groups.append(f'<g class="line-group" data-line="F">{"".join(items)}</g>')
    hub_lines = config['hub'].replace('|', ' ')
    hub = (f'<a class="hub" href="#about-text"><title>The central hypothesis, explained below</title>'
           f'<circle cx="{V_X["F"]}" cy="{hub_y}" r="12"/>'
           f'<text class="lbl hub-lbl" x="{V_LABEL_X}" y="{hub_y + 5}"><tspan>{html.escape(hub_lines)}</tspan></text></a>')
    y = hub_y + 40
    branch_y = hub_y + 26
    # each direction: its own stretch, ending in a terminus
    for line_id in ('1', '2', '3'):
        line = lines[line_id]
        x = V_X[line_id]
        items = [_v_head(line, y)]
        y += V_HEAD - 8
        for station in _stations(line, by_id):
            star = _star(x + 13, y - 11) if station.get('award') else ''
            items.append(f'<a class="st" href="#p-{html.escape(station["key"])}" data-line="{line_id}">'
                         f'<title>{html.escape(station["title"])} ({station["year"]})</title>'
                         f'{_marker(station["kind"], x, y)}{star}{_v_label(station, V_LABEL_X, y)}</a>')
            y += V_ROW
        end = y - V_ROW + 14
        bend = f'M{V_X["F"]} {hub_y} L{x} {branch_y}' if x != V_X['F'] else f'M{x} {hub_y}'
        paths.append(f'<path class="ln" data-line="{line_id}" pathLength="1" d="{bend} V{end}"/>')
        groups.append(f'<g class="line-group" data-line="{line_id}">{"".join(items)}</g>')
        y += V_GAP
    height = y + 6
    return (f'<svg class="netmap netmap-v" viewBox="0 0 {V_WIDTH} {height}" role="group" '
            f'aria-labelledby="netmap-v-title"><title id="netmap-v-title">Research map: foundations lead to one interchange, '
            f'from which three research directions run. Each station is a paper, demonstrator, or patent.</title>'
            f'<g class="lines">{"".join(paths)}</g>{hub}{"".join(groups)}</svg>')


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
    return map_svg(config, by_id) + line_names(config) + map_vertical(config, by_id)
