"""Generate a neofetch-inspired, editable SVG profile from a photo and YAML config."""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from xml.sax.saxutils import escape
from PIL import Image, ImageEnhance, ImageOps
import yaml

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / 'config.yaml'
DEFAULT_OUTPUT = ROOT / 'output'
MAX_SECTIONS = 24
MAX_ROWS_PER_SECTION = 80


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    with path.open(encoding='utf-8') as f:
        raw = yaml.safe_load(f) or {}
    return normalize_config(raw)


def normalize_config(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError('A configuração deve ser um objeto YAML/JSON.')
    conf = deepcopy(raw)
    conf.setdefault('profile', {})
    conf.setdefault('portrait', {})
    conf.setdefault('theme', {})
    conf.setdefault('sections', [])
    if not isinstance(conf['sections'], list) or len(conf['sections']) > MAX_SECTIONS:
        raise ValueError('sections deve ser uma lista com até 24 seções.')
    conf['profile'] = dict(conf['profile'] or {})
    conf['portrait'] = dict(conf['portrait'] or {})
    conf['theme'] = dict(conf['theme'] or {})
    conf['profile']['username'] = str(conf['profile'].get('username', 'seu-usuario'))[:80]
    conf['profile']['title'] = str(conf['profile'].get('title', 'github'))[:80]
    conf['profile']['photo'] = str(conf['profile'].get('photo', 'assets/retrato.png'))
    p = conf['portrait']
    p['columns'] = max(22, min(52, int(p.get('columns', 34))))
    p['rows'] = max(15, min(38, int(p.get('rows', 25))))
    p['contrast'] = max(.5, min(2.5, float(p.get('contrast', 1.25))))
    p['brightness'] = max(.5, min(2, float(p.get('brightness', 1))))
    p['invert'] = bool(p.get('invert', False))
    p['charset'] = str(p.get('charset', '@%#*+=-:,. '))[:64] or '@%#*+=-:,. '
    t = conf['theme']
    for key, default in [('background','#161b22'),('text','#c9d1d9'),('key','#ffa657'),('value','#a5d6ff'),('muted','#616e7f'),('addition','#3fb950'),('deletion','#f85149')]:
        value = str(t.get(key, default))
        if len(value) != 7 or value[0] != '#' or any(c not in '0123456789abcdefABCDEF' for c in value[1:]):
            value = default
        t[key] = value
    t['font_size'] = max(12, min(18, int(t.get('font_size', 15))))
    result = []
    for section in conf['sections']:
        if not isinstance(section, dict):
            raise ValueError('Seção inválida.')
        rows = section.get('rows', [])
        if not isinstance(rows, list) or len(rows) > MAX_ROWS_PER_SECTION:
            raise ValueError('Cada seção deve ter até 80 campos.')
        result.append({'title': str(section.get('title', ''))[:120], 'rows': [
            {'label': str(row.get('label', ''))[:120], 'value': str(row.get('value', ''))[:500]}
            for row in rows if isinstance(row, dict)
        ]})
    conf['sections'] = result
    return conf


def locate_photo(path_str: str) -> Path:
    path = (ROOT / path_str).resolve()
    if not path.is_relative_to(ROOT / 'assets'):
        raise ValueError('A foto deve ficar dentro da pasta assets/.')
    if not path.is_file():
        raise ValueError(f'Foto não encontrada: {path_str}')
    return path


def photo_to_ascii(path: Path, portrait: dict) -> list[str]:
    """Map luminance to monospaced characters, respecting the input alpha channel."""
    with Image.open(path) as source:
        src = ImageOps.exif_transpose(source).convert('RGBA')
    # Limit memory for enormous photos; respect the portrait crop and alpha.
    src.thumbnail((1600, 1600))
    w, h = int(portrait['columns']), int(portrait['rows'])
    # Center-crop to the intended character grid's approximate physical ratio.
    cell_ratio = .54  # glyph width/line height, for a 15px monospace font
    target_ratio = w * cell_ratio / h
    sw, sh = src.size
    if sw / sh > target_ratio:
        new_w = round(sh * target_ratio)
        left = (sw - new_w) // 2
        src = src.crop((left, 0, left + new_w, sh))
    else:
        new_h = round(sw / target_ratio)
        top = max(0, (sh - new_h) // 3)  # Favor face / hair rather than lower torso.
        top = min(top, sh - new_h)
        src = src.crop((0, top, sw, top + new_h))
    src = src.resize((w, h), Image.Resampling.LANCZOS)
    alpha = src.getchannel('A')
    gray = ImageOps.grayscale(src)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(portrait['contrast'])
    gray = ImageEnhance.Brightness(gray).enhance(portrait['brightness'])
    chars = portrait['charset']
    n = len(chars) - 1
    lines = []
    for y in range(h):
        line = []
        for x in range(w):
            if alpha.getpixel((x,y)) < 75:
                line.append(' ')
                continue
            lightness = gray.getpixel((x,y)) / 255
            # On a dark terminal, bright skin needs mid-density characters rather
            # than whitespace, so the face remains readable at small sizes.
            lightness = min(1.0, max(0.0, lightness * .84 - .13))
            if portrait['invert']:
                lightness = 1 - lightness
            idx = min(n, max(0, round(lightness * n)))
            line.append(chars[idx])
        lines.append(''.join(line).rstrip())
    return lines


def xml(s: object) -> str:
    return escape(str(s), {'"': '&quot;', "'": '&apos;'})


def render_svg(conf: dict, *, light: bool = False) -> str:
    conf = normalize_config(conf)
    t = dict(conf['theme'])
    if light:
        t.update(background='#f6f8fa',text='#24292f',key='#953800',value='#0969da',muted='#6e7781',addition='#1a7f37',deletion='#cf222e')
    lines = photo_to_ascii(locate_photo(conf['profile']['photo']), conf['portrait'])
    fs = t['font_size']
    step = 20 * fs / 15
    char_width = fs * .605
    left_w = max(332, 15 + conf['portrait']['columns'] * char_width + 10)
    right_x = round(left_w + 18)
    label_x = right_x + 18
    value_x = right_x + 310
    right_width = 640
    panel_right = right_x + right_width
    width = max(985, round(panel_right + 16))
    y = 30.0
    elements = []
    # Text wrapping uses conservative available character width; long fields grow the image vertically.
    max_len = max(12, int((width - value_x - 28) / char_width))

    def text(x, baseline, value, color, extra=''):
        elements.append(f'<text x="{x:.1f}" y="{baseline:.1f}" fill="{color}" {extra}>{xml(value)}</text>')

    user = f"{conf['profile']['username']}@{conf['profile']['title']}"
    text(right_x, y, user, t['text'])
    line_begin = right_x + max(155, min(310, len(user) * char_width + 13))
    elements.append(f'<path d="M {line_begin:.1f} {y-4:.1f} H {width-20}" stroke="{t["text"]}" stroke-width="1"/>')
    y += 20 * fs / 15

    for si, sec in enumerate(conf['sections']):
        title = sec['title'].strip()
        if si > 0:
            y += 13 * fs / 15
        if title:
            title_text = f'─ {title}'
            text(right_x, y, title_text, t['text'])
            line_begin = right_x + max(135, min(300, len(title_text) * char_width + 14))
            elements.append(f'<path d="M {line_begin:.1f} {y-4:.1f} H {width-20}" stroke="{t["text"]}" stroke-width="1"/>')
            y += step
        for row in sec['rows']:
            label = row['label']
            val = row['value']
            label_max = max(8, int((value_x - label_x - 24) / char_width))
            if len(label) > label_max:
                label = label[:label_max-1] + '…'
            text(right_x, y, '·', t['muted'])
            text(label_x, y, label + ':', t['key'])
            dot_start = label_x + (len(label)+2) * char_width
            if dot_start < value_x-8:
                dots = int((value_x - 10 - dot_start) / char_width)
                text(dot_start, y, '·' * max(0, dots), t['muted'])
            if not val:
                val = '—'
            # Split on natural word boundaries; multiline values are permitted.
            chunks = []
            for paragraph in val.splitlines() or ['']:
                import textwrap
                chunks.extend(textwrap.wrap(paragraph, width=max_len, break_long_words=True, break_on_hyphens=False) or [''])
            for idx, chunk in enumerate(chunks):
                text(value_x, y + idx*step, chunk, t['value'])
            y += step * max(1, len(chunks))
    bottom_y = y + 15
    portrait_bottom = 30 + (len(lines)-1) * step + 20
    height = max(530, int(max(bottom_y, portrait_bottom) + 4))

    portrait_el = []
    for row, line in enumerate(lines):
        portrait_el.append(f'<tspan x="15" y="{30+row*step:.1f}">{xml(line)}</tspan>')
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Perfil GitHub em estilo terminal">
<title>Perfil ASCII de {xml(conf['profile']['username'])}</title>
<rect width="100%" height="100%" rx="15" fill="{t['background']}"/>
<g font-family="'DejaVu Sans Mono', 'Liberation Mono', Consolas, monospace" font-size="{fs}" font-weight="400" xml:space="preserve">
<text fill="{t['text']}">{''.join(portrait_el)}</text>
{''.join(elements)}
</g></svg>'''
    return svg


def generate(conf: dict, directory: Path = DEFAULT_OUTPUT, both: bool = True) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    results = []
    for light in ([False, True] if both else [False]):
        target = directory / ('light_mode.svg' if light else 'dark_mode.svg')
        target.write_text(render_svg(conf, light=light), encoding='utf-8')
        results.append(target)
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gerar cartões SVG a partir de config.yaml')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--dark-only', action='store_true')
    a = parser.parse_args()
    for output in generate(load_config(a.config), a.out, both=not a.dark_only):
        print(output)
