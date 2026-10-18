#!/usr/bin/env python3
"""Small deterministic SVG of the threshold sweep's renewal and survival; no dependencies."""

import argparse
from html import escape
import json
import math
from pathlib import Path
from xml.etree import ElementTree

import population_sweep as sweep

WIDTH, HEIGHT = 960, 660
LEFT, RIGHT, TOP, BOTTOM = 96, 920, 170, 580
SURFACE, PRIMARY, SECONDARY, MUTED = '#fcfcfb', '#0b0b0b', '#52514e', '#898781'
GRID, AXIS, WASH = '#e1e0d9', '#c3c2b7', '#f0efec'
DIAL, FINALIST = '#2a78d6', '#eb6834'
FONT = 'system-ui, -apple-system, Segoe UI, sans-serif'
DASH = '6 4'


def ticks(low, high, count):
    """Clean steps of 1, 2 or 5 times a power of ten, widened to cover [low, high]."""
    raw = (high - low) / count
    power = 10 ** math.floor(math.log10(raw))
    step = next(power * m for m in (1, 2, 5, 10) if power * m >= raw)
    first, last = math.floor(low / step) * step, math.ceil(high / step) * step
    return [round(first + i * step, 10) for i in range(round((last - first) / step) + 1)], step


def overlaps(a, b):
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def crosses(box, line):
    """Whether a drawn segment passes through a label box, sampled every two pixels."""
    (x1, y1), (x2, y2) = line
    steps = max(1, math.ceil(math.hypot(x2 - x1, y2 - y1) / 2))
    return any(box[0] <= x1 + (x2 - x1) * i / steps <= box[2] and
               box[1] <= y1 + (y2 - y1) * i / steps <= box[3] for i in range(steps + 1))


def render(result, started):
    analysis, decision = result['analysis'], result['decision']
    thresholds = started['thresholds']
    fixed, search = analysis[sweep.FIXED], analysis[sweep.SEARCH]
    survive = lambda row: row['founders'] - row['extinct_families']
    lights = [p for p in analysis if p.startswith('light-')]
    points = {p: (survive(analysis[p]), analysis[p]['late_renewal']) for p in analysis}
    xs = [x for x, _ in points.values()]
    ys = [y for p in analysis for y in (*analysis[p]['late_renewal_interval'], points[p][1])]
    x_ticks, _ = ticks(min(xs) - 2, max(xs) + 2, 8)
    y_ticks, _ = ticks(0, max(ys) * 1.02, 6)
    x_low, x_high = x_ticks[0], x_ticks[-1]
    y_high = y_ticks[-1]
    sx = lambda x: LEFT + (x - x_low) / (x_high - x_low) * (RIGHT - LEFT)
    sy = lambda y: BOTTOM - y / y_high * (BOTTOM - TOP)
    at = lambda p: (sx(points[p][0]), sy(points[p][1]))

    gate = lambda p: ('never' if thresholds[p]['light_minimum'] is None else
                      str(thresholds[p]['light_minimum']))
    both = decision['both']
    title = ('No light setting matches Search 1’s renewal with fixed wear’s survival' if not both else
             'Light settings ' + ', '.join(gate(p) for p in both) +
             ' match Search 1’s renewal with fixed wear’s survival')
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
             f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img">',
             f'<title>{escape(title)}</title>',
             '<desc>Each point averages 32 whole-population gardens through day 1376. Two blue paths '
             'start at fixed wear: the solid one makes the repair light gate stricter, up to never '
             'repairing; the dashed one makes it more permissive, down to repairing in darkness. Orange '
             'diamonds are the learned finalists. The shaded corner meets both renewal and survival '
             'criteria. Vertical whiskers are 95% bootstrap intervals over weather seeds.</desc>',
             f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{SURFACE}"/>',
             f'<g font-family="{FONT}" font-size="13" fill="{SECONDARY}">']
    placed, marks, lines = [], [], []

    def text(x, y, value, size=13, anchor='start', color=SECONDARY, weight='normal', halo=False):
        # A surface halo keeps labels legible where they meet grid or data lines.
        ring = (f' stroke="{SURFACE}" stroke-width="3" stroke-linejoin="round" paint-order="stroke"'
                if halo else '')
        parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" text-anchor="{anchor}" '
                     f'font-weight="{weight}" fill="{color}"{ring}>{escape(str(value))}</text>')

    def box(x, y, value, size, anchor):
        width = 0.6 * size * len(value)
        left = x - (width if anchor == 'end' else width / 2 if anchor == 'middle' else 0)
        return (left - 2, y - 0.75 * size - 2, left + width + 2, y + 0.25 * size + 2)

    text(32, 40, title, 21, color=PRIMARY, weight='600')
    text(32, 66, 'Whole populations on 16 fresh weather seeds × 2 layouts through day 1376; '
                 'each point averages 32 gardens.')
    text(32, 86, 'Point labels give the minimum light at which a policy repairs; the condition gate '
                 'stays at 192.')
    # Legend: one row, identity marks beside ink text.
    legend, cursor = 118, 32
    for dash, name in (('', 'Stricter repair than fixed wear'), (DASH, 'More permissive repair')):
        pattern = f' stroke-dasharray="{dash}"' if dash else ''
        parts.append(f'<path d="M{cursor},{legend} H{cursor + 26}" stroke="{DIAL}" stroke-width="2"'
                     f'{pattern}/><circle cx="{cursor + 13}" cy="{legend}" r="4" fill="{DIAL}" '
                     f'stroke="{SURFACE}" stroke-width="2"/>')
        text(cursor + 34, legend + 4, name)
        cursor += 34 + 0.55 * 13 * len(name) + 28
    parts.append(f'<path d="M{cursor + 13},{legend - 6} L{cursor + 19},{legend} L{cursor + 13},'
                 f'{legend + 6} L{cursor + 7},{legend} Z" fill="{FINALIST}" stroke="{SURFACE}" '
                 f'stroke-width="2"/>')
    text(cursor + 34, legend + 4, 'Learned finalists')
    cursor += 34 + 0.55 * 13 * len('Learned finalists') + 28
    parts.append(f'<rect x="{cursor + 6}" y="{legend - 7}" width="14" height="14" fill="{WASH}" '
                 f'stroke="{AXIS}"/>')
    text(cursor + 34, legend + 4, 'Both criteria met')

    # The qualifying corner: at least fixed wear's survivors and Search 1's renewal.
    corner_x, corner_y = sx(survive(fixed)), sy(search['late_renewal'])
    parts.append(f'<rect x="{corner_x:.1f}" y="{TOP}" width="{RIGHT - corner_x:.1f}" '
                 f'height="{corner_y - TOP:.1f}" fill="{WASH}"/>')
    for value in y_ticks:
        y = sy(value)
        parts.append(f'<path d="M{LEFT},{y:.1f} H{RIGHT}" stroke="{GRID if value else AXIS}"/>')
        text(LEFT - 10, y + 4, f'{value:.2f}', 12, 'end', MUTED)
    for value in x_ticks:
        x = sx(value)
        parts.append(f'<path d="M{x:.1f},{TOP} V{BOTTOM}" stroke="{GRID}"/>')
        text(x, BOTTOM + 20, f'{value:g}', 12, 'middle', MUTED)
    parts.append(f'<path d="M{corner_x:.1f},{TOP} V{corner_y:.1f} H{RIGHT}" fill="none" '
                 f'stroke="{MUTED}"/>')
    lines += [((corner_x, TOP), (corner_x, corner_y)), ((corner_x, corner_y), (RIGHT, corner_y))]
    for x, y, value, anchor in ((RIGHT - 6, corner_y - 8, 'Search 1’s late renewal', 'end'),
                                (corner_x + 6, TOP + 16, 'Fixed wear’s survivors', 'start')):
        text(x, y, value, 12, anchor)
        placed.append(box(x, y, value, 12, anchor))
    text((LEFT + RIGHT) / 2, BOTTOM + 46, 'Founder families surviving at day 1376 (of '
         f'{fixed["founders"]})', 13, 'middle')
    parts.append(f'<text transform="translate(30,{(TOP + BOTTOM) / 2}) rotate(-90)" font-size="13" '
                 f'text-anchor="middle" fill="{SECONDARY}">Late renewal score</text>')

    for p in analysis:
        x, (low, high) = sx(points[p][0]), analysis[p]['late_renewal_interval']
        color = DIAL if p in lights else FINALIST
        parts.append(f'<path d="M{x:.1f},{sy(low):.1f} V{sy(high):.1f}" stroke="{color}" '
                     f'stroke-opacity="0.45" stroke-width="1"/>')
        lines.append(((x, sy(low)), (x, sy(high))))
    # Both branches start at fixed wear, so the dial reads outward from the reference policy.
    hub = lights.index(sweep.FIXED)
    for branch, dash in ((lights[hub:], ''), (lights[hub::-1], DASH)):
        pattern = f' stroke-dasharray="{dash}"' if dash else ''
        path = ' L'.join(f'{x:.1f},{y:.1f}' for x, y in map(at, branch))
        parts.append(f'<path d="M{path}" fill="none" stroke="{DIAL}" stroke-width="2"{pattern} '
                     f'stroke-linejoin="round" stroke-linecap="round"/>')
        lines += [(at(a), at(b)) for a, b in zip(branch, branch[1:])]

    def tooltip(p, name):
        row = analysis[p]
        return escape(f'{name}: late renewal {row["late_renewal"]:.4f}, {survive(row)} of '
                      f'{row["founders"]} founder families surviving, {row["single_species_gardens"]} '
                      f'single-species gardens, {row["shrub_gardens"]} gardens with shrubs')

    for p in lights:
        x, y = at(p)
        minimum = thresholds[p]['light_minimum']
        name = 'Never repairs' if minimum is None else f'Repairs at light {minimum} or more'
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{DIAL}" stroke="{SURFACE}" '
                     f'stroke-width="2"><title>{tooltip(p, name)}</title></circle>')
    for p in sweep.REFERENCES:
        x, y = at(p)
        name = 'Search 1' if p == sweep.SEARCH else 'Search 2'
        parts.append(f'<path d="M{x:.1f},{y - 6:.1f} L{x + 6:.1f},{y:.1f} L{x:.1f},{y + 6:.1f} '
                     f'L{x - 6:.1f},{y:.1f} Z" fill="{FINALIST}" stroke="{SURFACE}" stroke-width="2">'
                     f'<title>{tooltip(p, name)}</title></path>')
    marks += [(x - 4.5, y - 4.5, x + 4.5, y + 4.5) for x, y in map(at, analysis)]

    def label(x, y, value, size=12, color=SECONDARY):
        """First spot clear of labels, marks and lines; else clear of labels and marks; else none."""
        spots = []
        for dx, dy, anchor in ((9, 4, 'start'), (-9, 4, 'end'), (0, -11, 'middle'), (0, 19, 'middle'),
                               (7, -8, 'start'), (-7, -8, 'end'), (7, 17, 'start'), (-7, 17, 'end')):
            area = box(x + dx, y + dy, value, size, anchor)
            # Labels may dip just below the baseline, still clear of the tick labels.
            if area[0] >= LEFT and area[2] <= RIGHT and area[1] >= TOP and area[3] <= BOTTOM + 10:
                spots.append((x + dx, y + dy, anchor, area))
        for strict in (True, False):
            for tx, ty, anchor, area in spots:
                if not any(overlaps(area, b) for b in placed + marks) and \
                        not (strict and any(crosses(area, line) for line in lines)):
                    placed.append(area)
                    text(tx, ty, value, size, anchor, color, halo=True)
                    return

    for p in [sweep.FIXED, *sweep.REFERENCES] + [p for p in lights if p != sweep.FIXED]:
        x, y = at(p)
        if p in sweep.REFERENCES:
            label(x, y, 'Search 1' if p == sweep.SEARCH else 'Search 2', 13, PRIMARY)
        else:
            value = f'{gate(p)} (fixed wear)' if p == sweep.FIXED else gate(p)
            label(x, y, value, 13 if p == sweep.FIXED else 12, PRIMARY if p == sweep.FIXED else SECONDARY)
    parts.append('</g></svg>')
    svg = '\n'.join(parts) + '\n'
    ElementTree.fromstring(svg)
    return svg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path, help='verified sweep directory')
    parser.add_argument('target', type=Path)
    args = parser.parse_args()
    sweep.check(args.out)
    result = json.loads((args.out / 'result.json').read_bytes())
    started = json.loads((args.out / 'started.json').read_bytes())
    with args.target.open('x') as stream:
        stream.write(render(result, started))


if __name__ == '__main__':
    main()
