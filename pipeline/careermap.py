"""The map of career stations on the About page.

A crop of the world from the Caribbean to Central Europe, drawn with the Mercator
projection, and an enlarged view of Central Europe, where three of the stations lie
close together. One line in the style of the research map runs through the stations
in order. Like the research map, it is plain SVG written at build time.

The coastlines come from Natural Earth (public domain) by way of the world-atlas
package. `data/career-land.json` holds only the parts this map needs. To make it again:

    npm pack world-atlas@2.0.2 && tar xzf world-atlas-2.0.2.tgz
    python -m pipeline.careermap package/land-110m.json package/land-50m.json
"""
import html
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAND_FILE = ROOT / 'data' / 'career-land.json'

# The world view: longitudes and latitudes it shows, and its width in SVG units.
WORLD = {'lon': (-95.0, 45.0), 'lat': (5.0, 61.0)}
WIDTH = 1000
# The enlarged view of Central Europe and the box of the world view that it fills.
DETAIL = {'lon': (7.5, 17.5), 'lat': (49.4, 57.9)}
DETAIL_BOX = (322, 34, 270)  # x, y and width; the height follows from the projection


def _merc(lat):
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


class View:
    """Projects longitude and latitude into one rectangle of the drawing."""

    def __init__(self, lon, lat, x, y, width):
        self.lon0, self.lon1 = lon
        self.top = _merc(lat[1])
        self.k = width / math.radians(self.lon1 - self.lon0)
        self.x, self.y = x, y
        self.width = width
        self.height = self.k * (self.top - _merc(lat[0]))

    def __call__(self, lon, lat):
        return (self.x + self.k * math.radians(lon - self.lon0),
                self.y + self.k * (self.top - _merc(lat)))


# --- Making career-land.json from world-atlas ------------------------------------------

def _decode(topology):
    """The rings of every polygon of a TopoJSON topology, as lists of (lon, lat)."""
    scale, shift = topology['transform']['scale'], topology['transform']['translate']
    arcs = []
    for arc in topology['arcs']:
        x = y = 0
        points = []
        for dx, dy in arc:
            x, y = x + dx, y + dy
            points.append((x * scale[0] + shift[0], y * scale[1] + shift[1]))
        arcs.append(points)

    def ring(indices):
        points = []
        for index in indices:
            arc = arcs[index] if index >= 0 else arcs[~index][::-1]
            points.extend(arc if not points else arc[1:])
        return points

    rings = []
    for geometry in topology['objects']['land']['geometries']:
        polygons = geometry['arcs'] if geometry['type'] == 'MultiPolygon' else [geometry['arcs']]
        for polygon in polygons:
            rings.extend(ring(indices) for indices in polygon)
    return rings


def _clip(points, lon, lat):
    """Sutherland-Hodgman clipping of one ring to a longitude and latitude box."""
    edges = [(0, lon[0], 1), (0, lon[1], -1), (1, lat[0], 1), (1, lat[1], -1)]
    for axis, limit, side in edges:
        if not points:
            break
        inside = lambda p: (p[axis] - limit) * side >= 0  # noqa: E731
        out = []
        for i, current in enumerate(points):
            previous = points[i - 1]
            if inside(current):
                if not inside(previous):
                    out.append(_cross(previous, current, axis, limit))
                out.append(current)
            elif inside(previous):
                out.append(_cross(previous, current, axis, limit))
        points = out
    return points


def _cross(a, b, axis, limit):
    t = (limit - a[axis]) / (b[axis] - a[axis])
    return tuple(a[i] + t * (b[i] - a[i]) for i in range(2))


def _extract(path, box, margin):
    lon = (box['lon'][0] - margin, box['lon'][1] + margin)
    lat = (box['lat'][0] - margin, min(box['lat'][1] + margin, 80))
    rings = []
    for ring in _decode(json.loads(Path(path).read_text(encoding='utf-8'))):
        # Afro-Eurasia crosses the antimeridian, where its ring jumps by 360 degrees. The jump
        # lies far north of this map, so clipping to the latitudes below removes it.
        clipped = _clip(ring, lon, lat)
        if len(clipped) >= 3:
            rings.append([[round(x, 2), round(y, 2)] for x, y in clipped])
    return rings


def make_land(world_source, detail_source):
    land = {
        'source': 'Natural Earth via world-atlas 2.0.2 (land-110m and land-50m)',
        'world': _extract(world_source, WORLD, 2),
        'detail': _extract(detail_source, DETAIL, 1),
    }
    LAND_FILE.write_text(json.dumps(land, separators=(',', ':')) + '\n', encoding='utf-8')


# --- Drawing ----------------------------------------------------------------------------

def _path(rings, view, tolerance):
    parts = []
    for ring in rings:
        points, last = [], None
        for lon, lat in ring:
            x, y = view(lon, lat)
            if last is None or abs(x - last[0]) + abs(y - last[1]) >= tolerance:
                points.append((x, y))
                last = (x, y)
        if len(points) >= 3:
            parts.append('M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in points) + 'Z')
    return ''.join(parts)


def _label(station, x, y):
    anchor = {'left': 'end', 'right': 'start'}.get(station['label'], 'start')
    dx = {'left': -18, 'right': 18}.get(station['label'], 18)
    name = html.escape(station['city'])
    note = html.escape(station['short'])
    return (f'<text class="cm-lbl" text-anchor="{anchor}">'
            f'<tspan class="nm" x="{x + dx:.1f}" y="{y - 2:.1f}">{name}</tspan>'
            f'<tspan class="yr" x="{x + dx:.1f}" y="{y + 16:.1f}">{note}</tspan></text>')


def _station(number, x, y):
    return (f'<g class="cm-st"><circle cx="{x:.1f}" cy="{y:.1f}" r="11"/>'
            f'<text x="{x:.1f}" y="{y + 1:.1f}" text-anchor="middle" dominant-baseline="central">{number}</text></g>')


def careermap_html(stations_path, land_path=LAND_FILE):
    stations = json.loads(Path(stations_path).read_text(encoding='utf-8'))['stations']
    land = json.loads(Path(land_path).read_text(encoding='utf-8'))
    world = View(WORLD['lon'], WORLD['lat'], 0, 0, WIDTH)
    bx, by, bw = DETAIL_BOX
    detail = View(DETAIL['lon'], DETAIL['lat'], bx, by, bw)
    bh = round(detail.height, 1)
    height = math.ceil(world.height)

    # Where each station is drawn: in the detail view when it lies inside it.
    def inside_detail(s):
        return DETAIL['lon'][0] <= s['lon'] <= DETAIL['lon'][1] and DETAIL['lat'][0] <= s['lat'] <= DETAIL['lat'][1]

    points = [detail(s['lon'], s['lat']) if inside_detail(s) else world(s['lon'], s['lat']) for s in stations]

    # The line: straight within Europe, a long curve across the Atlantic into the detail view.
    d = f'M{points[0][0]:.1f} {points[0][1]:.1f}'
    for (x0, y0), (x1, y1), s0, s1 in zip(points, points[1:], stations, stations[1:]):
        if inside_detail(s0) == inside_detail(s1):
            bend = s1.get('bend', 0)
            if bend:
                mx, my = (x0 + x1) / 2, (y0 + y1) / 2
                nx, ny = (y1 - y0), -(x1 - x0)
                length = math.hypot(nx, ny) or 1
                cx, cy = mx + nx / length * bend, my + ny / length * bend
                d += f' Q{cx:.1f} {cy:.1f} {x1:.1f} {y1:.1f}'
            else:
                d += f' L{x1:.1f} {y1:.1f}'
        else:
            d += f' C{x0 + 60:.1f} {y0 - 170:.1f} {x1 - 210:.1f} {y1 + 30:.1f} {x1:.1f} {y1:.1f}'

    # The region the detail view enlarges, marked on the world view and joined to it.
    (ex0, ey0), (ex1, ey1) = world(DETAIL['lon'][0], DETAIL['lat'][1]), world(DETAIL['lon'][1], DETAIL['lat'][0])

    title = 'Map of career stations: ' + '; '.join(
        f'{i}. {s["city"]}, {s["country"]}: {s["role"]}, {s["years"]}' for i, s in enumerate(stations, 1))
    svg = [
        f'<svg class="careermap" viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="cm-title">',
        f'<title id="cm-title">{html.escape(title)}</title>',
        '<defs><clipPath id="cm-clip">'
        f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="6"/></clipPath></defs>',
        f'<path class="cm-land" d="{_path(land["world"], world, 1.2)}"/>',
        f'<rect class="cm-zoom" x="{ex0:.1f}" y="{ey0:.1f}" width="{ex1 - ex0:.1f}" height="{ey1 - ey0:.1f}"/>',
        f'<path class="cm-guide" d="M{bx + bw} {by} L{ex0:.1f} {ey0:.1f} M{bx + bw} {by + bh} L{ex0:.1f} {ey1:.1f}"/>',
        f'<rect class="cm-detail" x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="6"/>',
        f'<path class="cm-land" clip-path="url(#cm-clip)" d="{_path(land["detail"], detail, 0.8)}"/>',
        f'<rect class="cm-frame" x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="6"/>',
        f'<path class="cm-ln" pathLength="1" d="{d}"/>',
    ]
    for number, (station, (x, y)) in enumerate(zip(stations, points), 1):
        svg.append(_station(number, x, y))
        svg.append(_label(station, x, y))
    svg.append('</svg>')

    key = ['<ol class="careermap-key">']
    for number, station in enumerate(stations, 1):
        key.append(f'<li><span class="cm-n" aria-hidden="true">{number}</span><span><strong>'
                   f'{html.escape(station["city"])}, {html.escape(station["country"])}</strong>'
                   f'<span>{html.escape(station["role"])}, {html.escape(station["years"])}</span></span></li>')
    key.append('</ol>')
    return '\n'.join(svg) + '\n' + ''.join(key)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: python -m pipeline.careermap land-110m.json land-50m.json')
    make_land(sys.argv[1], sys.argv[2])
