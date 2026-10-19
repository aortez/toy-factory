#!/usr/bin/env python3
"""Small deterministic SVG of the validated exposure attribution; no dependencies."""

import argparse
from html import escape
import json
import math
from pathlib import Path
from xml.etree import ElementTree

import population_exposure as exposure

COLORS = ('#176b93', '#a94b18')


def render(result):
    cases = [result['cases'][key] for key in ('original', 'fewest')]
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="800" viewBox="0 0 1040 800" role="img">',
        '<title>Lower canopy accounts for the dawn energy gap</title>',
        '<desc>Four cell maps compare dawn light bands and fractional energy contributions. '
        'A phase chart shows that the exposure disadvantage reverses outside the focal dawn interval. '
        'Empty cells are dashes; zero means leaves are present but contribute zero.</desc>',
        '<rect width="1040" height="800" fill="white"/>',
        '<g font-family="sans-serif" font-size="14" fill="#152938">']

    def text(x, y, value, size=14, anchor='start', color='#152938'):
        parts.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" '
                     f'fill="{color}">{escape(str(value))}</text>')

    def line(x1, y1, x2, y2, color='#d3dbe0'):
        parts.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}"/>')

    text(30, 31, 'The dawn gap is concentrated in the lower canopy', 23)
    text(30, 57, 'Day 152, sun phases 1–32. Cell totals include every leaf sharing that cell.')
    text(257, 88, 'Useful light bands', 18, 'middle')
    text(752, 88, 'Energy contribution (numerator / 255)', 18, 'middle')
    all_cells = [c for case in cases for c in case['cells']]
    low_row, high_row = min(c['row'] for c in all_cells), max(c['row'] for c in all_cells)
    height = 280 / (high_row - low_row + 1)
    maxima = [max(c['periods'][0][key] / divisor for c in all_cells)
              for key, divisor in (('light_bands', 1), ('weighted_numerator', 255))]
    for metric, (key, divisor) in enumerate((('light_bands', 1), ('weighted_numerator', 255))):
        for policy, case in enumerate(cases):
            left = 67 + 245 * policy + 495 * metric
            top, width = 132, 56
            columns = sorted({c['column'] for c in case['cells']})
            exposure.score.require(len(columns) == 3, 'figure expects the three measured columns')
            by_cell = {(c['column'], c['row']): c for c in case['cells']}
            text(left + 84, 115, ('Original 19', 'Fewer-blocker 17')[policy], 16, 'middle')
            for row in range(low_row, high_row + 1):
                y = top + (row - low_row) * height
                text(left - 12, y + height / 2 + 5, row, anchor='end')
                for i, column in enumerate(columns):
                    x = left + i * width
                    cell = by_cell.get((column, row))
                    if cell is None:
                        text(x + width / 2, y + height / 2 + 5, '—', anchor='middle', color='#77838c')
                        continue
                    value = cell['periods'][0][key] / divisor
                    intensity = value / maxima[metric] if maxima[metric] else 0
                    # A single shared continuous scale per metric, independent of policy.
                    rgb = tuple(round(a + (b - a) * intensity) for a, b in zip((237, 244, 247), (23, 107, 147)))
                    color = '#%02x%02x%02x' % rgb
                    label = str(int(value)) if divisor == 1 else f'{value:.1f}'
                    parts.append(f'<rect x="{x + 1}" y="{y + 1}" width="{width - 2}" height="{height - 2}" fill="{color}">'
                                 f'<title>Column {column}, row {row}; {len(cell["ordinals"])} leaves; {label}</title></rect>')
                    text(x + width / 2, y + height / 2 + 5, label, anchor='middle',
                         color='white' if intensity > 0.6 else '#152938')
            # The fixed upper/lower split is between light-grid rows 6 and 7.
            split_y = top + (7 - low_row) * height
            line(left - 4, split_y, left + 168 + 4, split_y, '#152938')
            for i, column in enumerate(columns):
                text(left + i * width + width / 2, 434, column, anchor='middle')
            text(left + 84, 456, 'World grid column', anchor='middle')
    text(30, 482, 'Rows increase downward; line splits rows 0–6 / 7–13. Dash = no leaf. Zero = occupied, no contribution.')
    text(30, 521, 'Exposure by sun phase', 19)
    text(690, 521, 'Original 19', color=COLORS[0])
    text(830, 521, 'Fewer-blocker 17', color=COLORS[1])
    left, top, chart_width, chart_height = 80, 549, 880, 168
    values = [[p['light_bands'] for p in case['periods'][:4]] for case in cases]
    limit = max(200, math.ceil(max(max(v) for v in values) / 200) * 200)
    for value in range(0, limit + 1, 200):
        y = top + chart_height * (1 - value / limit)
        line(left, y, left + chart_width, y)
        text(left - 10, y + 5, value, anchor='end')
    text(left, top - 8, 'Summed light bands')
    for i, label in enumerate(('1–32 (dawn)', '33–64', '65–96', '97–128')):
        center = left + chart_width * (i + 0.5) / 4
        for policy in range(2):
            value = values[policy][i]
            bar_height = chart_height * value / limit
            x = center - 55 + 60 * policy
            y = top + chart_height - bar_height
            parts.append(f'<rect x="{x}" y="{y}" width="50" height="{bar_height}" fill="{COLORS[policy]}"/>')
            text(x + 25, y - 6, value, anchor='middle')
        text(center, 741, label, anchor='middle')
    text(30, 776, 'Phases 65–128 precede this dawn; 33–64 follow it. Noon = 64; sunset = 128. Night bins are zero.')
    parts.append('</g></svg>\n')
    result = '\n'.join(parts).encode()
    ElementTree.fromstring(result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('analysis', type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--out', type=Path)
    mode.add_argument('--check', type=Path)
    args = parser.parse_args()
    data = json.loads(args.analysis.read_bytes())
    exposure.score.require(data == exposure.diagnose(), 'figure input is not the verified derivation')
    raw = render(data)
    if args.check:
        exposure.score.require(args.check.read_bytes() == raw, 'figure differs')
    else:
        exposure.collect.write(args.out, raw)
