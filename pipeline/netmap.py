"""The research map of the About page, drawn as a transit diagram.

Foundations run in from the left to one interchange, from which the three research
directions branch. Each station is an entry of the bibliography; along each line the
stations run by year. The map is plain SVG written at build time, so the page needs no
script to show it. It comes in two drawings: a wide one for large screens and a vertical
one, with the lines running down the page and the labels beside them, for everything
narrower. The style sheet shows one of the two.
"""
import html
import json
import math

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
        return f'<text class="lbl" text-anchor="{anchor}">{" ".join(reversed(out))}</text>'
    rows = [(part, 'nm') for part in lines] + [(year, 'yr')]
    out, cy = [], y + 30
    for value, cls in rows:
        out.append(f'<tspan class="{cls}" x="{x}" y="{cy}">{html.escape(value)}</tspan>')
        cy += step
    return f'<text class="lbl" text-anchor="{anchor}">{" ".join(out)}</text>'


def _marker(kind, x, y):
    if kind == 'demo':
        return f'<rect class="mk mk-demo" x="{x - 7}" y="{y - 7}" width="14" height="14"/>'
    if kind == 'patent':
        return (f'<path class="mk mk-patent" d="M{x} {y - 9} L{x + 9} {y} L{x} {y + 9} L{x - 9} {y} Z"/>')
    return f'<circle class="mk" cx="{x}" cy="{y}" r="7.5"/>'


def _star(x, y, r=8):
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


def _aria(station):
    """The accessible name of a station link: map label, year, and full title."""
    name = f"{station['label'].replace('|', ' ')}, {station['year']}: {station['title']}"
    if station.get('award'):
        name += ', Best Demo Award'
    return html.escape(name, quote=True)


def _station_group(line, station, x, y, above):
    label = _label(station['label'], x, y, above, str(station['year']))
    star = _star(x + 14, y + 13 if above else y - 13) if station.get('award') else ''   # away from the label
    title = html.escape(station['title'])
    return (f'<a class="st" href="#p-{html.escape(station["key"])}" data-line="{line["id"]}" aria-label="{_aria(station)}">'
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


# Geometry of the vertical map: lines run down the page. The three directions leave the
# interchange side by side; each one shows its stations in its own stretch and ends there,
# so the next one can take the label column. Labels sit to the right of the tracks.
# Every link carries an invisible rectangle over its whole row, so the row is the tap target.
V_WIDTH = 352
V_X = {'F': 32, '1': 50, '2': 32, '3': 14}
V_LABEL_X = 68
V_ROW, V_GAP = 40, 12


def _v_hit(y):
    return f'<rect class="hit" x="0" y="{y - V_ROW / 2:g}" width="{V_WIDTH}" height="{V_ROW}"/>'


def _v_split(text, limit):
    """Break a long name in two near its middle, or return None when it fits on one line."""
    if len(text) <= limit:
        return None
    words = text.split()
    cut = min(range(1, len(words)), key=lambda i: abs(len(' '.join(words[:i])) - len(' '.join(words[i:]))))
    return ' '.join(words[:cut]), ' '.join(words[cut:])


def _v_text(cls, x, y, name, tail='', limit=26):
    """A label on one line and, for a long name, a second setting on two lines. The style
    sheet shows the second one where the map is drawn small and its type is enlarged."""
    one = f'<text class="lbl {cls}" x="{x}" y="{y + 5:g}"><tspan class="nm">{html.escape(name)}</tspan>{tail}</text>'
    parts = _v_split(name, limit)
    if parts is None:
        return one
    two = (f'<text class="lbl {cls} lbl-two"><tspan class="nm" x="{x}" y="{y - 3:g}">{html.escape(parts[0])}</tspan> '
           f'<tspan class="nm" x="{x}" y="{y + 15:g}">{html.escape(parts[1])}</tspan>{tail}</text>')
    return one.replace(f'class="lbl {cls}"', f'class="lbl {cls} lbl-one"') + two


def _v_label(station, x, y):
    year = f' <tspan class="yr" dx="3">{station["year"]}</tspan>'
    return _v_text('st-lbl', x, y, station['label'].replace('|', ' '), year)


def _v_station(station, line_id, y):
    x = V_X[line_id]
    star = _star(x + 14, y - 12) if station.get('award') else ''
    return (f'<a class="st" href="#p-{html.escape(station["key"])}" data-line="{line_id}" aria-label="{_aria(station)}">'
            f'{_v_hit(y)}<title>{html.escape(station["title"])} ({station["year"]})</title>'
            f'{_marker(station["kind"], x, y)}{star}{_v_label(station, V_LABEL_X, y)}</a>')


def _v_head(line, y):
    x = V_LABEL_X
    return (f'<a class="line-link" href="#{line["anchor"]}" data-line="{line["id"]}">'
            f'{_v_hit(y)}<title>Line {line["id"]}: {html.escape(line["name"])}</title>'
            f'{_bullet(line["id"], x + 11, y, size=22)}'
            f'{_v_text("line-head", x + 29, y, line["name"], limit=30)}</a>')


def map_vertical(config, by_id):
    """The vertical map, drawn top to bottom."""
    lines = {line['id']: line for line in config['lines']}
    paths, groups = [], []
    y = V_ROW / 2 + 2
    # Foundations: a short trunk into the interchange
    f = lines['F']
    items = [_v_head(f, y)]
    y += V_ROW
    f_top = y - 16
    for station in _stations(f, by_id):
        items.append(_v_station(station, 'F', y))
        y += V_ROW
    hub_y = y + 4
    paths.append(f'<path class="ln" data-line="F" pathLength="1" d="M{V_X["F"]} {f_top:g} V{hub_y:g}"/>')
    groups.append(f'<g class="line-group" data-line="F">{"".join(items)}</g>')
    hub_lines = config['hub'].replace('|', ' ')
    hub = (f'<a class="hub" href="#about-text">{_v_hit(hub_y)}<title>The central hypothesis, explained below</title>'
           f'<circle cx="{V_X["F"]}" cy="{hub_y:g}" r="12"/>'
           f'<text class="lbl hub-lbl" x="{V_LABEL_X}" y="{hub_y + 5:g}"><tspan>{html.escape(hub_lines)}</tspan></text></a>')
    y = hub_y + V_ROW + 2
    branch_y = hub_y + 26
    # each direction: its own stretch, ending in a terminus
    for line_id in ('1', '2', '3'):
        line = lines[line_id]
        x = V_X[line_id]
        items = [_v_head(line, y)]
        y += V_ROW
        for station in _stations(line, by_id):
            items.append(_v_station(station, line_id, y))
            y += V_ROW
        end = y - V_ROW + 14
        bend = f'M{V_X["F"]} {hub_y:g} L{x} {branch_y:g}' if x != V_X['F'] else f'M{x} {hub_y:g}'
        paths.append(f'<path class="ln" data-line="{line_id}" pathLength="1" d="{bend} V{end:g}"/>')
        groups.append(f'<g class="line-group" data-line="{line_id}">{"".join(items)}</g>')
        y += V_GAP
    height = y - V_ROW / 2 - V_GAP + 4
    # the foundations come before the interchange, in reading and in focus order
    return (f'<svg class="netmap netmap-v" viewBox="0 0 {V_WIDTH} {height:g}" role="group" '
            f'aria-labelledby="netmap-v-title"><title id="netmap-v-title">Research map: foundations lead to one interchange, '
            f'from which three research directions run. Each station is a paper, demonstrator, or patent.</title>'
            f'<g class="lines">{"".join(paths)}</g>{groups[0]}{hub}{"".join(groups[1:])}</svg>')


def line_names(config):
    """The names of the lines, set under the wide map."""
    items = ''.join(
        f'<li><a href="#{line["anchor"]}" data-line="{line["id"]}"><span class="lb" aria-hidden="true">{line["id"]}</span>'
        f'{html.escape(line["name"])}</a></li>' for line in config['lines'])
    return f'<ol class="line-names" aria-label="Research lines">{items}</ol>'


def netmap_html(path, by_id):
    config = load(path)
    return map_svg(config, by_id) + line_names(config) + map_vertical(config, by_id)
