"""Real image captcha generation.

The previous captcha was a **plaintext SVG**: the answer was embedded verbatim in
the response body (``<text ...>AB12</text>``), so any script could read the code
and the challenge protected nothing. This renders a distorted PNG instead, so the
answer never appears in the response payload.
"""
from __future__ import annotations

import io
import random
from typing import Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Ambiguous characters (0/O, 1/I/L) are excluded so humans can read it.
ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
LENGTH = 4
WIDTH, HEIGHT = 120, 40
BG = (248, 250, 252)      # 浅底：深色底+深字根本看不清

_FONT_CANDIDATES = (
    '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
    '/System/Library/Fonts/Supplemental/Arial.ttf',
    '/Library/Fonts/Arial.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
)

_rng = random.SystemRandom()


def _load_font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def random_code(length: int = LENGTH) -> str:
    return ''.join(_rng.choice(ALPHABET) for _ in range(length))


def render_captcha(code: str, width: int = WIDTH, height: int = HEIGHT) -> bytes:
    """Render ``code`` as distorted PNG bytes."""
    img = Image.new('RGB', (width, height), BG)
    draw = ImageDraw.Draw(img)

    # noise: crossing lines
    for _ in range(6):
        draw.line(
            [( _rng.randint(0, width), _rng.randint(0, height)),
             ( _rng.randint(0, width), _rng.randint(0, height))],
            fill=(_rng.randint(120, 180), _rng.randint(125, 185), _rng.randint(135, 195)),
            width=1,
        )
    # noise: specks
    for _ in range(140):
        draw.point((_rng.randint(0, width - 1), _rng.randint(0, height - 1)),
                   fill=(_rng.randint(150, 205), _rng.randint(155, 210), _rng.randint(165, 215)))

    font = _load_font(26)
    step = max(1, (width - 16) // max(1, len(code)))
    for i, char in enumerate(code):
        tile = Image.new('RGBA', (32, 38), (0, 0, 0, 0))
        tile_draw = ImageDraw.Draw(tile)
        tile_draw.text(
            (6, 4), char, font=font,
            fill=(_rng.randint(15, 70), _rng.randint(20, 75), _rng.randint(35, 95)),
        )
        tile = tile.rotate(_rng.uniform(-28, 28), resample=Image.BICUBIC, expand=False)
        img.paste(tile, (8 + i * step, 1), tile)

    img = img.filter(ImageFilter.SMOOTH)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def generate_captcha(length: int = LENGTH) -> Tuple[str, bytes]:
    code = random_code(length)
    return code, render_captcha(code)
