"""Local, deterministic photo -> ASCII -> editable, safe SVG profile generator."""
from __future__ import annotations

import argparse
import math
import os
import re
import tempfile
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps
import yaml

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / 'config.yaml'
DEFAULT_OUTPUT = ROOT / 'output'
MAX_SECTIONS = 24
MAX_ROWS_PER_SECTION = 80
PALETTE = {'background': '#161b22', 'text': '#c9d1d9', 'key': '#ffa657',
           'value': '#a5d6ff', 'muted': '#616e7f', 'addition': '#3fb950', 'deletion': '#f85149'}
LIGHT_PALETTE = {'background': '#f6f8fa', 'text': '#24292f', 'key': '#953800',
                 'value': '#0969da', 'muted': '#6e7781', 'addition': '#1a7f37', 'deletion': '#cf222e'}
STAT_KEYS = ('public_repos', 'followers', 'stars_received', 'forks_received', 'contributions_year', 'commits_year')
STAT_MARKERS = re.compile(r'\{\{github\.([a-z_]+)\}\}')
COLOR_MARKERS = re.compile(r'\[\[([+-])([^\[\]]{1,1000})\]\]')


def clean_xml(s: object) -> str:
    """Remove forbidden XML 1.0 characters rather than generating broken SVGs."""
    return ''.join(ch for ch in str(s) if ch in '\t\n\r' or
                   0x20 <= ord(ch) <= 0xD7FF or 0xE000 <= ord(ch) <= 0xFFFD or
                   0x10000 <= ord(ch) <= 0x10FFFF)


def xml(s: object) -> str:
    return escape(clean_xml(s), {'"': '&quot;', "'": '&apos;'})


def number(value, minimum, maximum, default, *, integer=False):
    try:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError()
    except (ValueError, TypeError, OverflowError):
        result = default
    result = max(minimum, min(maximum, result))
    return int(round(result)) if integer else round(result, 4)


def hex_color(value, default):
    value = str(value)
    return value if re.fullmatch(r'#[0-9a-fA-F]{6}', value) else default


def normalize_config(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError('Configuração deve ser um objeto YAML/JSON.')
    conf = deepcopy(raw)
    for key in ('profile', 'portrait', 'theme', 'layout', 'github'):
        if not isinstance(conf.get(key, {}), dict):
            raise ValueError(f'{key} deve ser um objeto.')
        conf.setdefault(key, {})
    sections = conf.get('sections', [])
    if not isinstance(sections, list) or len(sections) > MAX_SECTIONS:
        raise ValueError(f'sections deve conter até {MAX_SECTIONS} seções.')
    profile = conf['profile']
    for key, default in (('username', 'seu-usuario'), ('title', 'github')):
        profile[key] = clean_xml(profile.get(key, default))[:80]
    profile['photo'] = str(profile.get('photo', 'assets/retrato_fiel.png'))[:240]

    p = conf['portrait']
    for key, low, high, default, integer in (
        ('columns', 22, 120, 94, True), ('rows', 15, 90, 72, True),
        ('contrast', .5, 3.0, 1.8, False), ('brightness', .5, 2.0, 1.0, False),
        ('zoom', 1., 5., 3.0, False), ('center_x', 0., 1., .5, False),
        ('center_y', 0., 1., .23, False), ('edge_strength', 0., 1.5, .85, False),
        ('sharpness', 0., 3., 1.8, False), ('local_contrast', 0., 1., .3, False),
        ('font_scale', .35, 1.2, .46, False), ('auto_focus', 0., 1., .35, False)):
        p[key] = number(p.get(key, default), low, high, default, integer=integer)
    p['invert'] = p.get('invert', False) is True
    p['mode'] = p.get('mode', 'portrait') if p.get('mode') in ('portrait', 'classic', 'edges', 'dither') else 'portrait'
    charset = clean_xml(p.get('charset', '@%#WMB8$&'))[:96] or '@%#WMB8$&'
    p['charset'] = ''.join(ch for ch in charset if ch not in '\t\n\r') or '@%#WMB8$&'

    t = conf['theme']
    for key, default in PALETTE.items():
        t[key] = hex_color(t.get(key, default), default)
    t['font_size'] = number(t.get('font_size', 15), 10, 23, 15, integer=True)
    light = t.setdefault('light', {})
    if not isinstance(light, dict):
        raise ValueError('theme.light deve ser um objeto.')
    for key, default in LIGHT_PALETTE.items():
        light[key] = hex_color(light.get(key, default), default)

    layout = conf['layout']
    for key, low, high, default in (
        ('padding', 8, 70, 16), ('portrait_x', 0, 100, 15), ('top', 18, 85, 30),
        ('column_gap', 4, 100, 18), ('left_min_width', 150, 680, 332),
        ('right_width', 420, 1150, 640), ('label_width', 160, 550, 292),
        ('line_height', 1., 2.5, 1.33), ('section_gap', 0, 50, 13),
        ('min_height', 200, 1300, 530)):
        layout[key] = number(layout.get(key, default), low, high, default, integer=True if key != 'line_height' else False)

    gh = conf['github']
    gh['auto_update'] = gh.get('auto_update', False) is True
    cached = gh.get('cached', {})
    if not isinstance(cached, dict):
        cached = {}
    gh['cached'] = {k: (number(v, 0, 1e12, 0, integer=True) if v is not None else None)
                    for k, v in cached.items() if k in STAT_KEYS}
    if gh.get('updated_at'):
        gh['updated_at'] = clean_xml(gh['updated_at'])[:50]

    result = []
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError('Seção inválida.')
        rows = section.get('rows', [])
        if not isinstance(rows, list) or len(rows) > MAX_ROWS_PER_SECTION:
            raise ValueError(f'Cada seção deve conter até {MAX_ROWS_PER_SECTION} campos.')
        converted = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('Campo inválido.')
            converted.append({'label': clean_xml(row.get('label', ''))[:120],
                              'value': clean_xml(row.get('value', ''))[:800]})
        result.append({'title': clean_xml(section.get('title', ''))[:120], 'rows': converted})
    conf['sections'] = result
    return conf


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    with Path(path).open(encoding='utf-8') as f:
        return normalize_config(yaml.safe_load(f) or {})


def locate_photo(path_str: str) -> Path:
    path = (ROOT / path_str).resolve()
    if not path.is_relative_to((ROOT / 'assets').resolve()):
        raise ValueError('A foto deve ficar dentro da pasta assets/.')
    if not path.is_file():
        raise ValueError(f'Foto não encontrada: {path_str}')
    return path


def _alpha_bbox(img: Image.Image, threshold: int = 18):
    alpha = img.getchannel('A')
    bbox = alpha.point(lambda px: 255 if px >= threshold else 0).getbbox()
    return bbox or (0, 0, img.width, img.height)


def _estimate_focus_point(img: Image.Image, portrait: dict):
    """Estimate the most informative region (face/hair/features) for a nicer crop."""
    small = ImageOps.exif_transpose(img).convert('RGBA').resize((120, 120), Image.Resampling.LANCZOS)
    alpha = small.getchannel('A')
    gray = ImageOps.grayscale(small)
    gray = ImageOps.autocontrast(gray)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    total = 0.0
    sx = 0.0
    sy = 0.0
    for y in range(small.height):
        bias_y = 1.08 - 0.35 * (y / max(1, small.height - 1))
        for x in range(small.width):
            a = alpha.getpixel((x, y)) / 255.0
            if a < 0.05:
                continue
            light = gray.getpixel((x, y)) / 255.0
            edge = edges.getpixel((x, y)) / 255.0
            weight = a * bias_y * (0.18 + (1.0 - light) * 0.72 + edge * 1.25)
            total += weight
            sx += x * weight
            sy += y * weight
    if total <= 0:
        return portrait.get('center_x', 0.5), portrait.get('center_y', 0.43)
    return sx / total / max(1, small.width - 1), sy / total / max(1, small.height - 1)


def crop_rectangle(size, portrait, *, subject_box=None, focus_point=None):
    """Crop in original pixels, preserving aspect and optionally using a smarter focus box/point."""
    sw, sh = size
    ratio = portrait['columns'] * .57 / portrait['rows']
    bx0, by0, bx1, by1 = subject_box or (0, 0, sw, sh)
    bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)
    if bw / bh > ratio:
        crop_h, crop_w = bh, bh * ratio
    else:
        crop_w, crop_h = bw, bw / ratio
    crop_w /= portrait['zoom']
    crop_h /= portrait['zoom']

    auto_focus = portrait.get('auto_focus', 0.0)
    base_fx, base_fy = focus_point or (0.5, 0.43)
    manual_fx = portrait['center_x']
    manual_fy = portrait['center_y']
    fx = manual_fx * (1 - auto_focus) + base_fx * auto_focus
    fy = manual_fy * (1 - auto_focus) + base_fy * auto_focus

    target_x = bx0 + max(0.0, min(1.0, fx)) * bw
    target_y = by0 + max(0.0, min(1.0, fy)) * bh
    left = max(0., min(sw - crop_w, target_x - crop_w / 2))
    top = max(0., min(sh - crop_h, target_y - crop_h / 2))
    return (int(round(left)), int(round(top)), int(round(left + crop_w)), int(round(top + crop_h)))


def prepare_gray_image(path: Path, portrait: dict):
    with Image.open(path) as source:
        if source.width * source.height > 28_000_000:
            raise ValueError('Imagem maior que 28 megapixels.')
        src = ImageOps.exif_transpose(source).convert('RGBA')
    src.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
    subject_box = _alpha_bbox(src) if src.getchannel('A').getbbox() else (0, 0, src.width, src.height)
    focus_point = _estimate_focus_point(src, portrait)
    src = src.crop(crop_rectangle(src.size, portrait, subject_box=subject_box, focus_point=focus_point))
    w, h = portrait['columns'], portrait['rows']
    src = src.resize((w * 4, h * 4), Image.Resampling.LANCZOS)
    alpha = src.getchannel('A').resize((w, h), Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(src)
    if portrait['sharpness']:
        gray = ImageEnhance.Sharpness(gray).enhance(1 + portrait['sharpness'])
    if portrait['local_contrast']:
        equalized = ImageOps.equalize(gray)
        gray = Image.blend(gray, equalized, portrait['local_contrast'])
    gray = ImageOps.autocontrast(gray, cutoff=.5)
    gray = ImageEnhance.Contrast(gray).enhance(portrait['contrast'])
    gray = ImageEnhance.Brightness(gray).enhance(portrait['brightness'])
    edge_map = gray.filter(ImageFilter.FIND_EDGES)
    edge_map = ImageEnhance.Contrast(edge_map).enhance(2.1)
    if portrait['mode'] == 'edges':
        gray = ImageChops.subtract(gray, ImageEnhance.Brightness(edge_map).enhance(.28 * portrait['edge_strength']))
    gray = gray.resize((w, h), Image.Resampling.LANCZOS)
    edge_map = edge_map.resize((w, h), Image.Resampling.LANCZOS)
    return gray, alpha, edge_map


def _orientation_char(gray: Image.Image, x: int, y: int):
    left = gray.getpixel((max(0, x - 1), y))
    right = gray.getpixel((min(gray.width - 1, x + 1), y))
    up = gray.getpixel((x, max(0, y - 1)))
    down = gray.getpixel((x, min(gray.height - 1, y + 1)))
    dx = right - left
    dy = down - up
    ax = abs(dx)
    ay = abs(dy)
    if ax > ay * 1.7:
        return '|'
    if ay > ax * 1.7:
        return '-'
    return '/' if dx * dy > 0 else '\\'


def _tone_char(light: float, chars: str) -> str:
    light = max(0.0, min(1.0, light))
    # Gentle gamma so skin remains readable while dark hair keeps texture.
    idx = int(round((light ** 0.92) * (len(chars) - 1)))
    return chars[max(0, min(len(chars) - 1, idx))]


def photo_to_ascii(path: Path, portrait: dict) -> list[str]:
    """Face-oriented ASCII conversion with smart crop and richer per-cell detail."""
    p = normalize_config({'portrait': portrait})['portrait']
    if p['mode'] == 'portrait':
        return [''.join(ch for ch, _ in row).rstrip() for row in portrait_cells(path, p)]
    gray, alpha, edge_map = prepare_gray_image(path, p)
    chars = p['charset']
    levels = len(chars) - 1
    errors = [0.] * (p['columns'] + 2)
    lines = []
    for y in range(p['rows']):
        line = []
        nxt = [0.] * (p['columns'] + 2)
        for x in range(p['columns']):
            if alpha.getpixel((x, y)) < 70:
                line.append(' ' )
                continue
            light = gray.getpixel((x, y)) / 255
            edge = edge_map.getpixel((x, y)) / 255
            tone = max(0.0, min(1.0, light * 0.9 + 0.1 - edge * 0.18))
            if p['invert']:
                tone = 1 - tone
            if p['mode'] == 'dither' and levels:
                tone = max(0, min(1, tone + errors[x+1]))
                ch = _tone_char(tone, chars)
                ix = chars.index(ch)
                err = tone - (ix / levels)
                if x + 1 < p['columns']:
                    errors[x+2] += err * (7/16)
                if x:
                    nxt[x] += err * (3/16)
                nxt[x+1] += err * (5/16)
                if x + 1 < p['columns']:
                    nxt[x+2] += err * (1/16)
            elif p['mode'] == 'edges':
                threshold = max(0.14, 0.34 - p['edge_strength'] * 0.08)
                if edge >= threshold and 0.05 < tone < 0.97:
                    ch = _orientation_char(gray, x, y)
                elif tone < 0.24 or (tone < 0.34 and y < p['rows'] * 0.68):
                    ch = '.'
                else:
                    ch = ' '
            else:
                ch = _tone_char(tone, chars)
            line.append(ch)
        lines.append(''.join(line).rstrip())
        errors = nxt
    return lines




def portrait_cells(path: Path, portrait: dict) -> tuple[tuple[tuple[str, int], ...], ...]:
    """Detailed, *real ASCII* portrait: each cell is a character and source luminance.

    There is no photographic image element in the exported SVG. All colors and glyphs
    are rendered using <text>/<tspan>, with higher sampling density and local contrast.
    """
    p = normalize_config({'portrait': portrait})['portrait']
    photo = Path(path).resolve()
    return _portrait_cells_cached(str(photo), photo.stat().st_mtime_ns, tuple(sorted(p.items())))


@lru_cache(maxsize=24)
def _portrait_cells_cached(photo_path: str, photo_mtime_ns: int, p_items: tuple):
    p = dict(p_items)
    with Image.open(photo_path) as file:
        if file.width * file.height > 28_000_000:
            raise ValueError('Imagem maior que 28 megapixels.')
        src = ImageOps.exif_transpose(file).convert('RGBA')
    src.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
    # The entire crop is used. Do not automatically zoom into the hair or shirt.
    area = crop_rectangle(src.size, p, subject_box=(0, 0, *src.size), focus_point=(.5, .5))
    src = src.crop(area)
    columns, rows = p['columns'], p['rows']
    src = src.resize((columns * 3, rows * 3), Image.Resampling.LANCZOS)
    alpha = src.getchannel('A').resize((columns, rows), Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(src)
    if p['sharpness']:
        gray = gray.filter(ImageFilter.UnsharpMask(radius=1.25, percent=int(48 * p['sharpness']), threshold=2))
    if p['local_contrast']:
        enhanced = ImageOps.equalize(gray)
        gray = Image.blend(gray, enhanced, min(0.55, p['local_contrast'] * .65))
    gray = ImageOps.autocontrast(gray, cutoff=.4)
    gray = ImageEnhance.Contrast(gray).enhance(p['contrast'])
    gray = ImageEnhance.Brightness(gray).enhance(p['brightness'])
    gray = gray.resize((columns, rows), Image.Resampling.LANCZOS)
    edge = gray.filter(ImageFilter.FIND_EDGES)
    # Deterministic variation of similarly dense characters; the tonal information
    # is carried by the glyph color instead of an embedded image or unreadable symbols.
    chars = ''.join(c for c in p['charset'] if c not in ' \n\r\t') or '@'
    # Bound per-cell detail so previews remain fast on laptops.
    cells = []
    for y in range(rows):
        line = []
        for x in range(columns):
            a = alpha.getpixel((x, y)) / 255.0
            if a < .22:
                line.append((' ', 0))
                continue
            level = gray.getpixel((x, y)) / 255.0
            # Lift darker locks slightly without washing out eyes and lips.
            level = max(0., min(1., level ** .82))
            if p['invert']:
                level = 1. - level
            detail = edge.getpixel((x, y)) / 255.
            if p['edge_strength']:
                level = max(0., min(1., level + (detail - .15) * .12 * p['edge_strength']))
            ink = int(round(max(0., min(1., (.28 + .73 * level) * min(1.0, a * 1.6))) * 255))
            symbol = chars[(x * 7 + y * 13) % len(chars)]
            line.append((symbol, ink))
        cells.append(tuple(line))
    return tuple(cells)


def portrait_svg_text(cells, *, x: float, top: float, font_size: float, step: float, palette: dict, light: bool):
    """Turn character grid into colored SVG text, never raster <image> tags."""
    bg = tuple(int(palette['background'][i:i + 2], 16) for i in (1, 3, 5))
    fg = tuple(int(palette['text'][i:i + 2], 16) for i in (1, 3, 5))
    result = []
    for idx, row in enumerate(cells):
        spans = []
        for ch, ink in row:
            if ch == ' ':
                spans.append(' ')
                continue
            source = ink / 255.
            strength = source if not light else max(0.10, min(1., 1.28 - source))
            color = '#%02x%02x%02x' % tuple(round(a + (b - a) * strength) for a, b in zip(bg, fg))
            spans.append(f'<tspan fill="{color}">{xml(ch)}</tspan>')
        result.append(f'<text x="{x:.1f}" y="{top + idx * step:.2f}">{"".join(spans)}</text>')
    return f'<g font-size="{font_size:.2f}">{"".join(result)}</g>'


def resolve_stats(value, cached):
    def replacement(match):
        key = match.group(1)
        data = cached.get(key)
        if key not in STAT_KEYS or data is None:
            return '—'
        return f'{data:,}'.replace(',', '.')
    return STAT_MARKERS.sub(replacement, value)


def colored_characters(value: str, t: dict):
    """Return character-color tuples; [[+text]] and [[-text]] enable inline accents."""
    pos = 0
    output = []
    for match in COLOR_MARKERS.finditer(value):
        output.extend((c, t['value']) for c in value[pos:match.start()])
        output.extend((c, t['addition'] if match.group(1) == '+' else t['deletion']) for c in match.group(2))
        pos = match.end()
    output.extend((c, t['value']) for c in value[pos:])
    return output


def wrapped_color_lines(chars, width):
    lines = []
    chunks = []
    for item in chars:
        if item[0] == '\n':
            chunks.append([])
        elif item[0] != '\r':
            if not chunks:
                chunks.append([])
            chunks[-1].append(item)
    for par in chunks or [[]]:
        if not par:
            lines.append([])
        while par:
            if len(par) <= width:
                lines.append(par)
                break
            split = width
            for i in range(width, max(0, width//2), -1):
                if par[i-1][0] == ' ':
                    split = i
                    break
            part = par[:split]
            while part and part[-1][0] == ' ':
                part.pop()
            lines.append(part)
            par = par[split:]
            while par and par[0][0] == ' ':
                par = par[1:]
    return lines or [[]]




def render_portrait_svg(conf: dict, *, light: bool = False) -> str:
    """Standalone portrait SVG for zooming in and judging facial likeness."""
    c = normalize_config(conf)
    palette = dict(c['theme'])
    if light:
        palette.update(palette['light'])
    p = c['portrait']
    fs = 10.6 if p['mode'] == 'portrait' else max(9., palette['font_size'] * p['font_scale'])
    step = fs * 1.12
    w = math.ceil(p['columns'] * fs * .605 + 28)
    h = math.ceil((p['rows'] - 1) * step + 38)
    if p['mode'] == 'portrait':
        chars = portrait_svg_text(portrait_cells(locate_photo(c['profile']['photo']), p),
                                  x=14, top=21, font_size=fs, step=step, palette=palette, light=light)
    else:
        lines = photo_to_ascii(locate_photo(c['profile']['photo']), p)
        spans = ''.join(f'<tspan x="14" y="{21+i*step:.2f}">{xml(line)}</tspan>'
                        for i, line in enumerate(lines))
        chars = f'<text x="14" fill="{palette["text"]}" font-size="{fs}">{spans}</text>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="Retrato em caracteres ASCII">'
            f'<rect width="100%" height="100%" rx="12" fill="{palette["background"]}"/>'
            f'<g font-family="\'DejaVu Sans Mono\', \'Liberation Mono\', Consolas, monospace" '
            f'font-weight="400" xml:space="preserve">{chars}</g></svg>')


def render_svg(conf: dict, *, light: bool = False) -> str:
    conf = normalize_config(conf)
    t = dict(conf['theme'])
    if light:
        t.update(t['light'])
    lay = conf['layout']
    portrait_mode = conf['portrait']['mode'] == 'portrait'
    path = locate_photo(conf['profile']['photo'])
    cells = portrait_cells(path, conf['portrait']) if portrait_mode else None
    lines = [] if portrait_mode else photo_to_ascii(path, conf['portrait'])
    fs = t['font_size']
    step = fs * lay['line_height']
    char_width = fs * .605
    if portrait_mode:
        portrait_fs = round(max(5., fs * conf['portrait']['font_scale']), 3)
        portrait_step = portrait_fs * 1.08
    else:
        portrait_fs = round(max(8., fs * conf['portrait']['font_scale']), 3)
        portrait_step = step
    portrait_char_width = portrait_fs * .605
    portrait_x = lay['portrait_x']
    left_w = max(lay['left_min_width'], portrait_x + conf['portrait']['columns'] * portrait_char_width + lay['padding'])
    right_x = left_w + lay['column_gap']
    label_x = right_x + 18
    value_x = label_x + lay['label_width']
    width = int(max(520, right_x + lay['right_width'] + lay['padding']))
    max_len = max(8, int((width - value_x - 2*lay['padding']) / char_width))
    y = float(lay['top'])
    elements = []

    def text_at(x, yy, value, color):
        elements.append(f'<text x="{x:.1f}" y="{yy:.1f}" fill="{color}">{xml(value)}</text>')

    def line_at(start, yy):
        if start < width - lay['padding'] - 8:
            elements.append(f'<path d="M {start:.1f} {yy-4:.1f} H {width-lay["padding"]}" stroke="{t["text"]}" stroke-width="1"/>')

    user = f"{conf['profile']['username']}@{conf['profile']['title']}"
    text_at(right_x, y, user, t['text'])
    line_at(right_x + len(user)*char_width + 14, y)
    y += step
    for si, sec in enumerate(conf['sections']):
        title = sec['title'].strip()
        if si:
            y += lay['section_gap']
        if title:
            heading = '─ ' + title
            text_at(right_x, y, heading, t['text'])
            line_at(right_x + len(heading)*char_width + 14, y)
            y += step
        for row in sec['rows']:
            label = row['label']
            maximum = max(4, int((value_x - label_x - 18)/char_width))
            if len(label) > maximum:
                label = label[:maximum-1] + '…'
            text_at(right_x, y, '·', t['muted'])
            text_at(label_x, y, label + ':', t['key'])
            start = label_x + (len(label)+2)*char_width
            if start < value_x - char_width:
                text_at(start, y, '·' * min(160, int((value_x - start - 4)/char_width)), t['muted'])
            val = resolve_stats(row['value'], conf['github']['cached']) or '—'
            segments = wrapped_color_lines(colored_characters(val, t), max_len)
            for line_i, fragment in enumerate(segments):
                spans = []
                for ch, color in fragment:
                    if spans and spans[-1][0] == color:
                        spans[-1][1].append(ch)
                    else:
                        spans.append((color, [ch]))
                payload = ''.join(f'<tspan fill="{col}">{xml("".join(chars))}</tspan>' for col, chars in spans)
                elements.append(f'<text x="{value_x:.1f}" y="{y+line_i*step:.1f}">{payload}</text>')
            y += max(1, len(segments)) * step
    count = len(cells) if portrait_mode else len(lines)
    height = max(lay['min_height'], math.ceil(max(y + 20, lay['top'] + (count - 1) * portrait_step + 26)))
    if portrait_mode:
        portrait_payload = portrait_svg_text(cells, x=portrait_x, top=lay['top'], font_size=portrait_fs,
                                             step=portrait_step, palette=t, light=light)
    else:
        spans = ''.join(f'<tspan x="{portrait_x}" y="{lay["top"]+i*portrait_step:.1f}">{xml(line)}</tspan>'
                        for i, line in enumerate(lines))
        portrait_payload = f'<text fill="{t["text"]}" font-size="{portrait_fs:.2f}">{spans}</text>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="Perfil GitHub em estilo terminal">'
            f'<title>Perfil ASCII de {xml(conf["profile"]["username"])}</title>'
            f'<rect width="100%" height="100%" rx="15" fill="{t["background"]}"/>'
            f'<g font-family="\'DejaVu Sans Mono\', \'Liberation Mono\', Consolas, monospace" '
            f'font-size="{fs}" font-weight="400" xml:space="preserve">'
            f'{portrait_payload}{"".join(elements)}</g></svg>')


def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.temp-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_config(conf: dict, path: Path = DEFAULT_CONFIG):
    atomic_write(path, yaml.safe_dump(normalize_config(conf), allow_unicode=True, sort_keys=False).encode('utf-8'))


def generate(conf: dict, directory: Path = DEFAULT_OUTPUT, both: bool = True) -> list[Path]:
    conf = normalize_config(conf)
    # Render both fully before touching any output file.
    variants = [(False, 'dark_mode.svg')] + ([(True, 'light_mode.svg')] if both else [])
    svg_files = [(directory / name, render_svg(conf, light=light).encode('utf-8')) for light, name in variants]
    svg_files.append((directory / 'portrait_only.svg', render_portrait_svg(conf).encode('utf-8')))
    for path, svg in svg_files:
        atomic_write(path, svg)
    return [p for p, _ in svg_files]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gerar cartões SVG a partir de config.yaml')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--dark-only', action='store_true')
    parser.add_argument('--refresh-stats', action='store_true', help='Reconsultar GitHub antes de gerar SVG')
    options = parser.parse_args()
    config = load_config(options.config)
    if options.refresh_stats and config['github']['auto_update']:
        from github_stats import fetch_stats
        config['github'].update(fetch_stats(config['profile']['username']))
        write_config(config, options.config)
    for output in generate(config, options.out, both=not options.dark_only):
        print(output)
