#!/usr/bin/env python3
# Copyright (c) 2026 THOX.ai LLC. Licensed under the Apache License, Version 2.0.
"""txf_desktop_gen: build the ThoxOS Desktop themes from the TXF desktop tokens.

TXF 5.2 Desktop Customization requires that every desktop theme derive from one
token file (/usr/share/thox/txf/txf-tokens.json). This generator is that
derivation for the XFCE-based ThoxOS Desktop used by ThoxOS Ginux Edition. It
runs once at image build time and writes into a target root:

    usr/share/thox/txf/txf-tokens.json         the token file itself
    usr/share/thox/looks/<look>.json           look definitions read by thoxos-look
    usr/share/themes/ThoxOS-<Look>/            GTK 3 theme + xfwm4 window decorations
    usr/share/plank/themes/ThoxOS-<Dark|Light> dock themes
    usr/share/xfce4/terminal/colorschemes/     terminal palettes
    usr/share/backgrounds/thoxos/              wallpapers (dark, light, login)
    usr/share/plymouth/themes/thoxos/          boot splash
    usr/share/icons/hicolor/<n>x<n>/apps/      the THOX chip mark as an app icon
    usr/share/icons/ThoxOS-*                   folder recolor overlays on Papirus
    usr/share/xrdp/                            RDP login branding (24-bit BMP)

GTK themes are produced by remapping the colors of GTK's own Adwaita stylesheet
(extracted from libgtk-3 at build time and passed with --adwaita-dir): neutral
greys move onto the TXF zinc ramp, Adwaita blue moves onto TXF green. No color
outside the token file and the THOX document tokens is introduced.

Usage:
    txf_desktop_gen.py --tokens txf-tokens.json --adwaita-dir DIR --fonts-dir DIR \
        --papirus-dir /usr/share/icons --out ROOT
"""

from __future__ import annotations

import argparse
import colorsys
import json
import math
import os
import re
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

try:  # Pillow is only needed for raster output; the color logic is pure Python.
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - exercised only on hosts without Pillow
    Image = ImageDraw = ImageFont = None  # type: ignore[assignment]

FORBIDDEN_DEFAULT = ("#10B981", "#00FF88")
# Light-appearance text and border values are not in txf-tokens.json (its light
# set has only canvas, surface, elevated, action and softGreen). They come from
# the THOX document tokens (DS 2.x lock: paperText, paperTextSecondary,
# paperBorder) so Porcelain never invents a value.
LIGHT_SUPPLEMENT = {"fg": "#09090B", "fg2": "#52525B", "border": "#D4D4D8"}
SLOGAN = "Your AI. Your Data. Your Rules.™"
HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGBA_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(,\s*[0-9.]+\s*)?\)")


class GenError(Exception):
    """Generation failure with a message for the build log."""


# --------------------------------------------------------------------- colors

RGB = tuple[int, int, int]


def parse_hex(value: str) -> RGB:
    """'#RRGGBB' or '#RGB' to an (r, g, b) tuple."""
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", text):
        raise GenError(f"not a hex color: {value!r}")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def to_hex(rgb: RGB) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, round(c))) for c in rgb))


def luminance(rgb: RGB) -> float:
    """Relative luminance (WCAG 2.x)."""

    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: RGB, b: RGB) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(a: RGB, b: RGB, t: float) -> RGB:
    """Linear blend: t=0 gives a, t=1 gives b."""
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def hls(rgb: RGB) -> tuple[float, float, float]:
    return colorsys.rgb_to_hls(*(c / 255 for c in rgb))


def from_hls(h: float, l: float, s: float) -> RGB:
    r, g, b = colorsys.hls_to_rgb(h, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return round(r * 255), round(g * 255), round(b * 255)


@dataclass(frozen=True)
class Palette:
    """One appearance (dark or light) resolved from the tokens."""

    name: str
    canvas: RGB
    surface: RGB
    elevated: RGB
    border: RGB
    fg: RGB
    fg2: RGB
    primary: RGB  # brand green used for fills and selection
    accent: RGB  # green used for text and line-work on this canvas
    danger: RGB
    mesh: RGB
    space: RGB
    hosted: RGB
    soft_green: RGB


def load_tokens(path: Path) -> dict:
    try:
        tokens = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GenError(f"cannot read tokens {path}: {error}") from error
    if tokens.get("schema") != "thox.txf.desktop-tokens/v1":
        raise GenError(f"{path}: expected schema thox.txf.desktop-tokens/v1")
    for section in ("dark", "light", "chrome", "brandLocks", "type"):
        if section not in tokens:
            raise GenError(f"{path}: missing section {section!r}")
    return tokens


def palettes(tokens: dict) -> tuple[Palette, Palette]:
    d, l = tokens["dark"], tokens["light"]
    dark = Palette(
        name="dark",
        canvas=parse_hex(d["canvas"]),
        surface=parse_hex(d["surface"]),
        elevated=parse_hex(d["elevated"]),
        border=parse_hex(d["border"]),
        fg=parse_hex(d["fg"]),
        fg2=parse_hex(d["fg2"]),
        primary=parse_hex(d["primary"]),
        accent=parse_hex(d["accent"]),
        danger=parse_hex(d["danger"]),
        mesh=parse_hex(d["mesh"]),
        space=parse_hex(d["space"]),
        hosted=parse_hex(d["hosted"]),
        soft_green=parse_hex(l["softGreen"]),
    )
    light = Palette(
        name="light",
        canvas=parse_hex(l["canvas"]),
        surface=parse_hex(l["surface"]),
        elevated=parse_hex(l["elevated"]),
        border=parse_hex(LIGHT_SUPPLEMENT["border"]),
        fg=parse_hex(LIGHT_SUPPLEMENT["fg"]),
        fg2=parse_hex(LIGHT_SUPPLEMENT["fg2"]),
        primary=parse_hex(l["action"]),
        accent=parse_hex(l["action"]),
        danger=parse_hex(d["danger"]),
        mesh=parse_hex(d["mesh"]),
        space=parse_hex(d["space"]),
        hosted=parse_hex(d["hosted"]),
        soft_green=parse_hex(l["softGreen"]),
    )
    return dark, light


# Neutral anchors: (Adwaita lightness reference, TXF color). Adwaita greys are
# mapped monotonically onto the TXF zinc ramp so relative contrast survives.
def neutral_ramp(p: Palette) -> list[tuple[float, RGB]]:
    if p.name == "dark":
        return [
            (0.0, (0, 0, 0)),
            (hls(parse_hex("#1b1b1b"))[1], p.canvas),
            (hls(parse_hex("#2d2d2d"))[1], mix(p.canvas, p.surface, 0.55)),
            (hls(parse_hex("#353535"))[1], p.surface),
            (hls(parse_hex("#4a4a4a"))[1], p.elevated),
            (hls(parse_hex("#5b5b5b"))[1], p.border),
            (hls(parse_hex("#919190"))[1], p.fg2),
            (hls(parse_hex("#eeeeec"))[1], p.fg),
            (1.0, (255, 255, 255)),
        ]
    return [
        (0.0, (0, 0, 0)),
        (hls(parse_hex("#2e3436"))[1], p.fg),
        (hls(parse_hex("#929595"))[1], p.fg2),
        (hls(parse_hex("#cdc7c2"))[1], p.border),
        (hls(parse_hex("#dfdcd8"))[1], mix(p.border, p.elevated, 0.6)),
        (hls(parse_hex("#ebe9e7"))[1], p.elevated),
        (hls(parse_hex("#f6f5f4"))[1], p.canvas),
        (1.0, p.surface),
    ]


def map_neutral(rgb: RGB, ramp: Sequence[tuple[float, RGB]]) -> RGB:
    light = hls(rgb)[1]
    for (l0, c0), (l1, c1) in zip(ramp, ramp[1:]):
        if l0 <= light <= l1:
            t = 0.0 if l1 == l0 else (light - l0) / (l1 - l0)
            return mix(c0, c1, t)
    return ramp[-1][1]


def map_color(rgb: RGB, p: Palette, ramp: Sequence[tuple[float, RGB]]) -> RGB:
    """Map one Adwaita color into the TXF palette for appearance p."""
    h, l, s = hls(rgb)
    hue = h * 360
    if s < 0.15 or (max(rgb) - min(rgb)) < 18:
        return map_neutral(rgb, ramp)
    if 190 <= hue <= 240 or 70 <= hue <= 160:
        # Adwaita blue (accent, selection, links) and its success greens become
        # TXF green; keep the lightness offset from the Adwaita accent so hover,
        # pressed and backdrop shades stay distinguishable.
        reference = hls(parse_hex("#15539e" if p.name == "dark" else "#3584e4"))[1]
        gh, gl, gs = hls(p.primary)
        return from_hls(gh, gl + (l - reference), gs)
    if hue < 20 or hue >= 340:
        dh, dl, ds = hls(p.danger)
        return from_hls(dh, dl + (l - 0.45) * 0.6, ds)
    return rgb  # warnings (orange) keep their Adwaita values


def remap_css(css: str, p: Palette) -> str:
    ramp = neutral_ramp(p)

    def hex_sub(match: re.Match[str]) -> str:
        return to_hex(map_color(parse_hex(match.group(0)), p, ramp)).lower()

    def rgba_sub(match: re.Match[str]) -> str:
        rgb = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        alpha = match.group(4)
        if rgb in ((255, 255, 255), (0, 0, 0)):
            return match.group(0)
        r, g, b = map_color(rgb, p, ramp)
        return f"rgba({r}, {g}, {b}{alpha})" if alpha else f"rgb({r}, {g}, {b})"

    out = HEX_RE.sub(hex_sub, css)
    return RGBA_RE.sub(rgba_sub, out)


def gtk_overrides(p: Palette, sans: str) -> str:
    """Rules appended after the remapped Adwaita stylesheet."""
    sel = p.primary
    return f"""
/* ThoxOS Desktop overrides (TXF 5.2). Generated; do not edit by hand. */
@define-color theme_selected_bg_color {to_hex(sel)};
@define-color theme_unfocused_selected_bg_color {to_hex(mix(sel, p.surface, 0.35))};
@define-color accent_color {to_hex(p.accent)};
@define-color txf_canvas {to_hex(p.canvas)};
@define-color txf_surface {to_hex(p.surface)};
@define-color txf_elevated {to_hex(p.elevated)};
@define-color txf_border {to_hex(p.border)};
@define-color txf_primary {to_hex(p.primary)};
@define-color txf_soft_green {to_hex(p.soft_green)};
* {{ outline-color: alpha({to_hex(p.primary)}, 0.85); }}
entry:focus, entry:focus-within, spinbutton:focus {{
  border-color: {to_hex(p.primary)};
  box-shadow: inset 0 0 0 1px {to_hex(p.primary)};
}}
.thunar .sidebar row:selected, placessidebar row:selected {{
  background-color: {to_hex(p.soft_green if p.name == 'light' else mix(p.primary, p.surface, 0.55))};
  color: {to_hex(p.accent if p.name == 'light' else p.fg)};
}}
.xfce4-panel {{ font-family: "{sans}"; }}
"""


# ------------------------------------------------------------------- looks

@dataclass(frozen=True)
class Look:
    id: str
    name: str
    appearance: str  # dark or light
    theme_dir: str
    chrome: str  # traffic or mono
    dock_position: str
    wallpaper: str
    description: str


LOOKS = (
    Look("slate", "TXF Slate", "dark", "ThoxOS-Slate", "traffic", "bottom",
         "thoxos-dark.png", "Dark-first default: top bar, floating dock, authentic traffic lights"),
    Look("porcelain", "Porcelain", "light", "ThoxOS-Porcelain", "traffic", "bottom",
         "thoxos-light.png", "Light appearance: porcelain surfaces, TXF green line-work"),
    Look("console-pro", "Console Pro", "dark", "ThoxOS-ConsolePro", "mono", "left",
         "thoxos-dark.png", "Developer layout: left dock, TXF mono chrome with a green close glyph"),
)


def terminal_palette(p: Palette) -> dict[str, str]:
    """16-color terminal palette in the TXF syntax family, derived from tokens."""
    dark = p.name == "dark"
    base = p.canvas if dark else p.surface
    cyan = mix(p.mesh, p.accent, 0.5)

    def bright(c: RGB) -> RGB:
        return mix(c, (255, 255, 255), 0.25) if dark else mix(c, (0, 0, 0), 0.15)

    normal = [
        p.surface if dark else p.fg,
        p.danger,
        p.accent if dark else p.primary,
        p.hosted if dark else mix(p.hosted, (0, 0, 0), 0.35),
        p.mesh if dark else mix(p.mesh, (0, 0, 0), 0.3),
        p.space if dark else mix(p.space, (0, 0, 0), 0.3),
        cyan if dark else mix(cyan, (0, 0, 0), 0.3),
        p.fg2,
    ]
    brights = [p.border if dark else p.fg2] + [bright(c) for c in normal[1:7]] + [p.fg if dark else p.canvas]
    colors = normal + brights
    return {
        "background": to_hex(base),
        "foreground": to_hex(p.fg),
        "cursor": to_hex(p.primary),
        "palette": ";".join(to_hex(c) for c in colors),
        "bold": to_hex(p.fg),
        "selection_bg": to_hex(mix(p.primary, base, 0.55)),
    }


def look_definition(look: Look, p: Palette, tokens: dict) -> dict:
    t = tokens["type"]
    return {
        "schema": "thox.thoxos-desktop.look/v1",
        "id": look.id,
        "name": look.name,
        "appearance": look.appearance,
        "description": look.description,
        "gtk_theme": look.theme_dir,
        "xfwm_theme": look.theme_dir,
        "icon_theme": "ThoxOS-Papirus-Dark" if look.appearance == "dark" else "ThoxOS-Papirus-Light",
        "font": f"{t['sans']} 10",
        "mono_font": f"{t['mono']} 11",
        "title_font": f"{t['sans']} Semi-Bold 10",
        "button_layout": "CHM|",
        "wallpaper": f"/usr/share/backgrounds/thoxos/{look.wallpaper}",
        "dock": {
            "theme": "ThoxOS-Dark" if look.appearance == "dark" else "ThoxOS-Light",
            "position": look.dock_position,
            "icon_size": int(tokens["chrome"]["dockTile"]),
        },
        "terminal": terminal_palette(p),
        "panel": {
            "rgba": [round(c / 255, 4) for c in (p.canvas if p.name == "dark" else p.elevated)] + [0.96],
            "dark_mode": p.name == "dark",
        },
        "tokens": "/usr/share/thox/txf/txf-tokens.json",
    }


# ----------------------------------------------------------------- rasters

def require_pillow() -> None:
    if Image is None:
        raise GenError("Pillow (python3-pil) is required for raster output")


def font(fonts_dir: Path, family: str, size: int, weight: str = "Regular"):
    """Load Inter or JetBrains Mono from the Debian font packages.

    Static faces (Inter-Bold.otf, JetBrainsMono-Regular.ttf) are preferred;
    variable faces are used with a named instance when only those exist.
    """
    stem = {"Inter": "Inter", "JetBrains Mono": "JetBrainsMono"}[family]
    weight_name = weight.replace(" ", "").replace("-", "")
    static = [f"{stem}-{weight_name}{ext}" for ext in (".otf", ".ttf")]
    variable = [f"{stem}Variable.ttf", f"{stem}[wght].ttf", f"{stem}-VariableFont_wght.ttf"]
    found: dict[str, str] = {}
    for root, _dirs, files in os.walk(fonts_dir):
        for name in files:
            found.setdefault(name, os.path.join(root, name))
    for name in static:
        if name in found:
            return ImageFont.truetype(found[name], size)
    for name in variable:
        if name in found:
            face = ImageFont.truetype(found[name], size)
            try:
                face.set_variation_by_name(weight)
            except (OSError, ValueError, AttributeError):
                pass
            return face
    regular = [f"{stem}-Regular{ext}" for ext in (".otf", ".ttf")]
    for name in regular:
        if name in found:
            return ImageFont.truetype(found[name], size)
    raise GenError(f"font {family} {weight} not found under {fonts_dir}")


def draw_mark(img, x: float, y: float, size: float, color, width_ratio: float = 2 / 24) -> None:
    """The THOX chip mark (brand thox-mark-green.svg geometry, 24-unit grid)."""
    draw = ImageDraw.Draw(img)
    u = size / 24
    w = max(1, round(width_ratio * size))

    def pt(a: float, b: float) -> tuple[float, float]:
        return x + a * u, y + b * u

    draw.rounded_rectangle([pt(4, 4), pt(20, 20)], radius=2 * u, outline=color, width=w)
    draw.rounded_rectangle([pt(9, 9), pt(15, 15)], radius=1 * u, outline=color, width=w)
    pins = [((15, 2), (15, 4)), ((15, 20), (15, 22)), ((2, 15), (4, 15)), ((2, 9), (4, 9)),
            ((20, 15), (22, 15)), ((20, 9), (22, 9)), ((9, 2), (9, 4)), ((9, 20), (9, 22))]
    for a, b in pins:
        draw.line([pt(*a), pt(*b)], fill=color, width=w)
        for end in (a, b):  # round caps
            cx, cy = pt(*end)
            r = w / 2
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)


def wallpaper(p: Palette, size: tuple[int, int], fonts_dir: Path, caption: Optional[str] = None):
    require_pillow()
    w, h = size
    img = Image.new("RGB", size, p.canvas)
    draw = ImageDraw.Draw(img)
    dot = mix(p.canvas, p.border, 0.45 if p.name == "dark" else 0.35)
    step = 48
    for yy in range(step, h, step):
        for xx in range(step, w, step):
            draw.point((xx, yy), fill=dot)
    # Large, faint chip watermark anchored bottom-right, partly off canvas.
    mark_color = mix(p.canvas, p.primary, 0.10 if p.name == "dark" else 0.16)
    mark = h * 0.78
    draw_mark(img, w - mark * 0.78, h - mark * 0.80, mark, mark_color, width_ratio=1.1 / 24)
    # Hairline crosshairs (design-preview corner treatment).
    hair = mix(p.canvas, p.border, 0.6)
    for cx, cy in ((w * 0.08, h * 0.86), (w * 0.93, h * 0.12)):
        draw.line([(cx - 28, cy), (cx + 28, cy)], fill=hair, width=1)
        draw.line([(cx, cy - 28), (cx, cy + 28)], fill=hair, width=1)
    if caption:
        # Centered: greeters scale the image to cover the screen, which crops
        # the sides of a 16:9 image on 16:10 and 4:3 displays.
        f = font(fonts_dir, "JetBrains Mono", max(12, h // 90))
        draw.text((w / 2, h * 0.95), caption, font=f, fill=mix(p.canvas, p.fg2, 0.55), anchor="ms")
    return img


def window_button(kind: str, state: str, chrome: str, p: Palette, tokens: dict, height: int = 30):
    """One xfwm4 button pixmap (20 px wide) with a 12 px circle."""
    require_pillow()
    scale = 4  # supersample for smooth circles
    w, h = 20 * scale, height * scale
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    lock = {"close": tokens["chrome"]["lockClose"], "hide": tokens["chrome"]["lockMin"],
            "maximize": tokens["chrome"]["lockZoom"], "maximize-toggled": tokens["chrome"]["lockZoom"]}
    if kind not in lock:
        return img.resize((20, height), Image.LANCZOS)  # menu/shade/stick: blank
    inactive_fill = mix(p.surface, p.border, 0.9) if p.name == "dark" else p.border
    if chrome == "traffic":
        fill = parse_hex(lock[kind]) if state != "inactive" else inactive_fill
    else:  # mono: zinc controls
        fill = mix(p.border, p.fg2, 0.25) if state != "inactive" else inactive_fill
    if state == "pressed":
        fill = mix(fill, (0, 0, 0), 0.25)
    r = 6 * scale
    cx, cy = w / 2, h / 2
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
    glyph_color = None
    if state in ("prelight", "pressed"):
        glyph_color = (0, 0, 0, 150) if chrome == "traffic" else p.fg
    if chrome == "mono" and kind == "close" and state != "inactive":
        glyph_color = p.primary  # the green close glyph
    if glyph_color is not None:
        g = 2.6 * scale
        lw = max(1, round(1.4 * scale))
        if kind == "close":
            draw.line([(cx - g, cy - g), (cx + g, cy + g)], fill=glyph_color, width=lw)
            draw.line([(cx - g, cy + g), (cx + g, cy - g)], fill=glyph_color, width=lw)
        elif kind == "hide":
            draw.line([(cx - g - 0.5 * scale, cy), (cx + g + 0.5 * scale, cy)], fill=glyph_color, width=lw)
        else:
            draw.line([(cx - g, cy), (cx + g, cy)], fill=glyph_color, width=lw)
            draw.line([(cx, cy - g), (cx, cy + g)], fill=glyph_color, width=lw)
    return img.resize((20, height), Image.LANCZOS)


def write_xfwm4_theme(dest: Path, look: Look, p: Palette, tokens: dict) -> None:
    require_pillow()
    height = int(tokens["chrome"]["topbarHeight"])
    radius = int(tokens["chrome"]["windowRadius"])
    d = dest / "xfwm4"
    d.mkdir(parents=True, exist_ok=True)
    title_bg = p.surface if p.name == "dark" else p.elevated
    title_bg_inactive = mix(title_bg, p.canvas, 0.5)
    border = p.border
    for state, bg in (("active", title_bg), ("inactive", title_bg_inactive)):
        for i in range(1, 6):
            img = Image.new("RGBA", (4, height), bg + (255,))
            ImageDraw.Draw(img).line([(0, height - 1), (4, height - 1)], fill=mix(bg, border, 0.7))
            img.save(d / f"title-{i}-{state}.png")
        for side in ("left", "right"):
            img = Image.new("RGBA", (1, 4), border + (255,))
            img.save(d / f"{side}-{state}.png")
        Image.new("RGBA", (4, 1), border + (255,)).save(d / f"bottom-{state}.png")
        for corner in ("bottom-left", "bottom-right"):
            Image.new("RGBA", (1, 1), border + (255,)).save(d / f"{corner}-{state}.png")
        for corner in ("top-left", "top-right"):
            s = 4
            img = Image.new("RGBA", (radius * s, height * s), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            box = [0, 0, radius * 2 * s, height * s + radius * s] if corner == "top-left" else \
                [-radius * s, 0, radius * s, height * s + radius * s]
            draw.rounded_rectangle(box, radius=radius * s, fill=bg + (255,), outline=border + (255,), width=s)
            img = img.resize((radius, height), Image.LANCZOS)
            img.save(d / f"{corner}-{state}.png")
    for kind in ("close", "hide", "maximize", "maximize-toggled", "menu", "shade", "stick",
                 "shade-toggled", "stick-toggled"):
        for state in ("active", "inactive", "prelight", "pressed"):
            window_button(kind, state, look.chrome, p, tokens, height).save(d / f"{kind}-{state}.png")
    fg = to_hex(p.fg)
    themerc = f"""# {look.theme_dir} xfwm4 theme, generated from {tokens.get('designSystem', 'TXF')} desktop tokens.
button_offset=6
button_spacing=0
title_vertical_offset_active=0
title_vertical_offset_inactive=0
title_horizontal_offset=0
full_width_title=true
title_alignment=center
title_shadow_active=false
title_shadow_inactive=false
active_text_color={fg}
inactive_text_color={to_hex(p.fg2)}
active_text_shadow_color={to_hex(p.canvas)}
inactive_text_shadow_color={to_hex(p.canvas)}
shadow_delta_height=2
shadow_delta_width=0
shadow_delta_x=0
shadow_delta_y=-5
shadow_opacity=40
show_app_icon=false
"""
    (d / "themerc").write_text(themerc, encoding="utf-8")


def write_gtk_theme(dest: Path, look: Look, p: Palette, tokens: dict, adwaita_dir: Path) -> None:
    source = adwaita_dir / ("gtk-contained-dark.css" if p.name == "dark" else "gtk-contained.css")
    try:
        css = source.read_text(encoding="utf-8")
    except OSError as error:
        raise GenError(f"cannot read Adwaita stylesheet {source}: {error}") from error
    gtk3 = dest / "gtk-3.0"
    gtk3.mkdir(parents=True, exist_ok=True)
    header = (f"/* {look.theme_dir}: GTK 3 theme for ThoxOS Desktop ({look.name}).\n"
              f"   Generated by txf_desktop_gen.py from txf-tokens.json and GTK's Adwaita\n"
              f"   stylesheet (LGPL-2.1+, The GTK Team). Do not edit by hand. */\n")
    (gtk3 / "gtk.css").write_text(header + remap_css(css, p) + gtk_overrides(p, tokens["type"]["sans"]),
                                  encoding="utf-8")
    # No gtk-3.0/settings.ini: GTK 3 reloads the theme whenever the theme's own
    # settings.ini sets gtk-application-prefer-dark-theme, which re-reads the
    # file and loops forever (xfce4-session and xfwm4 spun at full CPU in
    # VALIDATION D-07). gtk.css is already dark or light per look.
    index = f"""[Desktop Entry]
Type=X-GNOME-Metatheme
Name={look.theme_dir}
Comment=ThoxOS Desktop {look.name} (TXF 5.2)
Encoding=UTF-8

[X-GNOME-Metatheme]
GtkTheme={look.theme_dir}
MetacityTheme={look.theme_dir}
IconTheme={'ThoxOS-Papirus-Dark' if p.name == 'dark' else 'ThoxOS-Papirus-Light'}
"""
    (dest / "index.theme").write_text(index, encoding="utf-8")


def plank_rgba(rgb: RGB, alpha: int) -> str:
    return f"{rgb[0]};;{rgb[1]};;{rgb[2]};;{alpha}"


def write_plank_theme(dest: Path, p: Palette) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    fill = p.surface if p.name == "dark" else p.surface
    text = f"""# ThoxOS dock theme ({p.name}), generated from txf-tokens.json.
[PlankTheme]
TopRoundness=14
BottomRoundness=14
LineWidth=1
OuterStrokeColor={plank_rgba(p.border, 230)}
FillStartColor={plank_rgba(fill, 235)}
FillEndColor={plank_rgba(fill, 235)}
InnerStrokeColor={plank_rgba(mix(fill, p.fg, 0.06), 160)}

[PlankDockTheme]
HorizPadding=6
TopPadding=6
BottomPadding=6
ItemPadding=8
IndicatorSize=4
IconShadowSize=0
UrgentBounceHeight=1.66
LaunchBounceHeight=0.0
FadeOpacity=1.0
ClickTime=180
UrgentBounceTime=600
LaunchBounceTime=0
ActiveTime=180
SlideTime=180
FadeTime=120
HideTime=180
GlowSize=0
GlowTime=0
GlowPulseTime=2000
UrgentHueShift=0
ItemMoveTime=180
CascadeHide=true
"""
    (dest / "dock.theme").write_text(text, encoding="utf-8")


def write_terminal_scheme(dest: Path, look_name: str, scheme: dict[str, str]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        "[Scheme]\n"
        f"Name=ThoxOS {look_name}\n"
        f"ColorForeground={scheme['foreground']}\n"
        f"ColorBackground={scheme['background']}\n"
        f"ColorCursor={scheme['cursor']}\n"
        "ColorCursorUseDefault=FALSE\n"
        f"ColorBold={scheme['bold']}\n"
        "ColorBoldUseDefault=FALSE\n"
        f"ColorSelectionBackground={scheme['selection_bg']}\n"
        "ColorSelectionUseDefault=FALSE\n"
        f"ColorPalette={scheme['palette']}\n",
        encoding="utf-8")


def write_bmp24(img, path: Path) -> None:
    """Uncompressed 24-bit BMP (the format xrdp's login screen reads)."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    row_pad = (4 - (w * 3) % 4) % 4
    pixels = rgb.tobytes()
    rows = []
    for y in range(h - 1, -1, -1):
        row = pixels[y * w * 3:(y + 1) * w * 3]
        bgr = bytearray(row)
        bgr[0::3], bgr[2::3] = row[2::3], row[0::3]
        rows.append(bytes(bgr) + b"\0" * row_pad)
    data = b"".join(rows)
    header = struct.pack("<2sIHHI", b"BM", 54 + len(data), 0, 0, 54)
    info = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(data), 2835, 2835, 0, 0)
    path.write_bytes(header + info + data)


def write_plymouth(dest: Path, p: Palette, fonts_dir: Path, footer: str) -> None:
    require_pillow()
    dest.mkdir(parents=True, exist_ok=True)
    mark = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    draw_mark(mark, 0, 0, 160, p.primary)
    mark.save(dest / "mark.png")
    f = font(fonts_dir, "Inter", 18)
    for name, text, face, color in (
        ("slogan.png", SLOGAN, f, p.fg2),
        ("footer.png", footer, font(fonts_dir, "JetBrains Mono", 13), mix(p.canvas, p.fg2, 0.6)),
    ):
        box = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), text, font=face)
        img = Image.new("RGBA", (box[2] - box[0] + 4, box[3] - box[1] + 6), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((2 - box[0], 2 - box[1]), text, font=face, fill=color)
        img.save(dest / name)
    Image.new("RGBA", (240, 2), mix(p.canvas, p.border, 0.8) + (255,)).save(dest / "track.png")
    Image.new("RGBA", (240, 2), p.primary + (255,)).save(dest / "fill.png")
    r, g, b = (c / 255 for c in p.canvas)
    (dest / "thoxos.plymouth").write_text(
        "[Plymouth Theme]\nName=ThoxOS\nDescription=ThoxOS Desktop boot splash (TXF 5.2)\n"
        "ModuleName=script\n\n[script]\nImageDir=/usr/share/plymouth/themes/thoxos\n"
        "ScriptFile=/usr/share/plymouth/themes/thoxos/thoxos.script\n", encoding="utf-8")
    script = f"""# ThoxOS boot splash: chip mark, hairline progress bar, slogan, base truth.
Window.SetBackgroundTopColor({r:.4f}, {g:.4f}, {b:.4f});
Window.SetBackgroundBottomColor({r:.4f}, {g:.4f}, {b:.4f});
cx = Window.GetX() + Window.GetWidth() / 2;
cy = Window.GetY() + Window.GetHeight() / 2;

mark.image = Image("mark.png");
mark.sprite = Sprite(mark.image);
mark.sprite.SetPosition(cx - mark.image.GetWidth() / 2, cy - mark.image.GetHeight() / 2 - 60, 1);

track.image = Image("track.png");
track.sprite = Sprite(track.image);
track.sprite.SetPosition(cx - track.image.GetWidth() / 2, cy + 50, 1);
fill.image = Image("fill.png");
fill.sprite = Sprite();
fill.sprite.SetPosition(cx - track.image.GetWidth() / 2, cy + 50, 2);

slogan.image = Image("slogan.png");
slogan.sprite = Sprite(slogan.image);
slogan.sprite.SetPosition(cx - slogan.image.GetWidth() / 2, cy + 74, 1);

footer.image = Image("footer.png");
footer.sprite = Sprite(footer.image);
footer.sprite.SetPosition(cx - footer.image.GetWidth() / 2, Window.GetY() + Window.GetHeight() - 48, 1);

fun progress_callback(duration, progress) {{
    width = Math.Int(track.image.GetWidth() * progress);
    if (width < 1) width = 1;
    fill.sprite.SetImage(fill.image.Scale(width, fill.image.GetHeight()));
}}
Plymouth.SetBootProgressFunction(progress_callback);

fun display_normal_callback() {{
    prompt.sprite.SetOpacity(0);
}}
fun display_password_callback(prompt_text, bullets) {{
    prompt.image = Image.Text(prompt_text + " " + bullets, {p.fg[0] / 255:.3f}, {p.fg[1] / 255:.3f}, {p.fg[2] / 255:.3f});
    prompt.sprite = Sprite(prompt.image);
    prompt.sprite.SetPosition(cx - prompt.image.GetWidth() / 2, cy + 110, 3);
    prompt.sprite.SetOpacity(1);
}}
prompt.sprite = Sprite();
Plymouth.SetDisplayNormalFunction(display_normal_callback);
Plymouth.SetDisplayPasswordFunction(display_password_callback);
"""
    (dest / "thoxos.script").write_text(script, encoding="utf-8")


APP_ICONS = ("thoxos-ginux", "thoxos-system", "thoxos-ask", "thoxos-about", "thoxos-looks", "thoxos-doctor")


def app_icon(kind: str, size: int, p: Palette, light: Palette):
    """A ThoxOS launcher icon: TXF surface tile with a green glyph on a 24-unit grid.

    Each ThoxOS entry gets its own glyph so dock and launcher items stay
    distinguishable: chip (ThoxOS on Ginux), power (system boot), speech
    bubble (Ask THOX), info (About), split disc (Looks), pulse (Doctor).
    """
    s = 4
    big = size * s
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    inset = big * 0.04
    draw.rounded_rectangle([inset, inset, big - inset, big - inset], radius=big * 0.22,
                           fill=p.surface + (255,), outline=p.border + (255,), width=max(1, round(big * 0.018)))
    u = big / 24
    green = p.primary + (255,)
    w = max(1, round((2.4 if size < 32 else 1.9) * u))

    def pt(a: float, b: float) -> tuple[float, float]:
        return a * u, b * u

    def cap(a: float, b: float, r: float = w / 2) -> None:
        cx, cy = pt(a, b)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=green)

    if kind == "thoxos-ginux":
        draw_mark(img, big * 0.2, big * 0.2, big * 0.6, green, width_ratio=(2.6 if size < 32 else 2.2) / 24)
    elif kind == "thoxos-system":
        draw.arc([pt(6.5, 6.5), pt(17.5, 17.5)], start=-60, end=240, fill=green, width=w)
        draw.line([pt(12, 5), pt(12, 11.5)], fill=green, width=w)
        cap(12, 5)
        cap(12, 11.5)
    elif kind == "thoxos-ask":
        draw.rounded_rectangle([pt(5, 6), pt(19, 16)], radius=3 * u, outline=green, width=w)
        draw.polygon([pt(8.5, 15.2), pt(8.5, 19.5), pt(12.5, 15.2)], fill=green)
        for x in (9, 12, 15):
            cap(x, 11, 1.25 * u)
    elif kind == "thoxos-about":
        draw.ellipse([pt(5, 5), pt(19, 19)], outline=green, width=w)
        cap(12, 8.6, 1.3 * u)
        draw.line([pt(12, 11.3), pt(12, 15.6)], fill=green, width=w)
        cap(12, 11.3)
        cap(12, 15.6)
    elif kind == "thoxos-looks":
        box = [pt(6, 6), pt(18, 18)]
        draw.pieslice(box, start=90, end=270, fill=light.canvas + (255,))
        draw.pieslice(box, start=270, end=90, fill=green)
        draw.ellipse(box, outline=p.border + (255,), width=max(1, round(u * 0.8)))
    elif kind == "thoxos-doctor":
        line = [pt(4, 12.5), pt(8, 12.5), pt(10, 8), pt(13, 17), pt(15, 10.5), pt(16.5, 12.5), pt(20, 12.5)]
        draw.line(line, fill=green, width=w, joint="curve")
        cap(4, 12.5)
        cap(20, 12.5)
    else:
        raise GenError(f"unknown app icon {kind}")
    return img.resize((size, size), Image.LANCZOS)


def write_app_icons(root: Path, p: Palette, light: Optional[Palette] = None) -> None:
    require_pillow()
    light = light or p
    for size in (16, 22, 24, 32, 48, 64, 128, 256):
        d = root / f"usr/share/icons/hicolor/{size}x{size}/apps"
        d.mkdir(parents=True, exist_ok=True)
        s = 4
        img = Image.new("RGBA", (size * s, size * s), (0, 0, 0, 0))
        draw_mark(img, 0, 0, size * s, p.primary, width_ratio=2.2 / 24 if size < 32 else 2 / 24)
        img.resize((size, size), Image.LANCZOS).save(d / "thoxos-mark.png")
        for kind in APP_ICONS:
            app_icon(kind, size, p, light).save(d / f"{kind}.png")
    pixmaps = root / "usr/share/pixmaps"
    pixmaps.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / "usr/share/icons/hicolor/256x256/apps/thoxos-mark.png", pixmaps / "thoxos-mark.png")


def icon_dir_section(directory: str) -> str:
    """index.theme section for a Papirus size directory such as '48x48/places'."""
    match = re.match(r"(\d+)x\d+", directory)
    size = int(match.group(1)) if match else 48
    return f"[{directory}]\nContext=Places\nSize={size}\nType=Fixed\n"


def write_icon_overlays(root: Path, papirus_dir: Optional[Path], dark: Palette, light: Palette) -> list[str]:
    """ThoxOS-Papirus-{Dark,Light}: Papirus with folder icons recolored to TXF green.

    Papirus places/*/folder*.svg use a blue body (#5294e2) and a darker blue
    back (#4877b1). Those two values are swapped for TXF greens; everything
    else inherits from Papirus. Returns the list of generated theme names.
    """
    made: list[str] = []
    if papirus_dir is None:
        return made
    for name, base, p in (("ThoxOS-Papirus-Dark", "Papirus-Dark", dark),
                          ("ThoxOS-Papirus-Light", "Papirus-Light", light)):
        src_root = papirus_dir / "Papirus"
        if not src_root.is_dir():
            continue
        dest = root / f"usr/share/icons/{name}"
        dirs: list[str] = []
        for size_dir in sorted(src_root.iterdir()):
            places = size_dir / "places"
            if not places.is_dir():
                continue
            if not re.match(r"\d+x\d+$", size_dir.name):
                continue
            for svg in places.glob("folder*.svg"):
                if svg.is_symlink():
                    continue
                text = svg.read_text(encoding="utf-8", errors="replace")
                if "#5294e2" not in text.lower():
                    continue
                body = to_hex(mix(p.primary, (255, 255, 255), 0.12)).lower()
                back = to_hex(mix(p.primary, (0, 0, 0), 0.22)).lower()
                text = re.sub("#5294e2", body, text, flags=re.I)
                text = re.sub("#4877b1", back, text, flags=re.I)
                out = dest / size_dir.name / "places" / svg.name
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(text, encoding="utf-8")
                rel = f"{size_dir.name}/places"
                if rel not in dirs:
                    dirs.append(rel)
            # Generic names (folder.svg, user-home.svg, folder-documents.svg)
            # are symlinks to folder-blue-*.svg. Without the same links here
            # they resolve in the inherited Papirus theme and stay blue.
            out_places = dest / size_dir.name / "places"
            if not out_places.is_dir():
                continue
            links = [l for l in places.iterdir() if l.is_symlink() and l.suffix == ".svg"]
            for _ in range(3):  # links to links resolve over passes
                for link in links:
                    target = os.readlink(link)
                    made_link = out_places / link.name
                    if "/" in target or made_link.is_symlink() or not (out_places / target).is_file():
                        continue
                    made_link.symlink_to(target)
        if not dirs:
            continue
        sections = "\n".join(icon_dir_section(d) for d in dirs)
        (dest / "index.theme").write_text(
            f"[Icon Theme]\nName={name}\nComment=Papirus with TXF green folders (generated)\n"
            f"Inherits={base},Papirus,hicolor\nDirectories={','.join(dirs)}\n\n{sections}",
            encoding="utf-8")
        made.append(name)
    return made


# ------------------------------------------------------------ xfconf defaults

def xml_prop(name: str, kind: str, value) -> str:
    if kind == "bool":
        value = "true" if value else "false"
    text = str(value).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    return f'    <property name="{name}" type="{kind}" value="{text}"/>'


def write_xfconf_defaults(root: Path, default: dict) -> None:
    """System default XFCE channels (/etc/xdg/xfce4/xfconf) for new users."""
    d = root / "etc/xdg/xfce4/xfconf/xfce-perchannel-xml"
    d.mkdir(parents=True, exist_ok=True)
    head = '<?xml version="1.0" encoding="UTF-8"?>\n'
    (d / "xsettings.xml").write_text(head + "\n".join([
        '<channel name="xsettings" version="1.0">',
        '  <property name="Net" type="empty">',
        xml_prop("ThemeName", "string", default["gtk_theme"]),
        xml_prop("IconThemeName", "string", default["icon_theme"]),
        '  </property>',
        '  <property name="Gtk" type="empty">',
        xml_prop("FontName", "string", default["font"]),
        xml_prop("MonospaceFontName", "string", default["mono_font"]),
        xml_prop("ShellShowsMenubar", "bool", True),
        xml_prop("ShellShowsAppmenu", "bool", True),
        xml_prop("DecorationLayout", "string", "close,minimize,maximize:"),
        '  </property>',
        '  <property name="Xft" type="empty">',
        xml_prop("Antialias", "int", 1),
        xml_prop("HintStyle", "string", "hintslight"),
        xml_prop("RGBA", "string", "rgb"),
        '  </property>',
        '</channel>', ""]), encoding="utf-8")
    (d / "xfwm4.xml").write_text(head + "\n".join([
        '<channel name="xfwm4" version="1.0">',
        '  <property name="general" type="empty">',
        xml_prop("theme", "string", default["xfwm_theme"]),
        xml_prop("button_layout", "string", default["button_layout"]),
        xml_prop("title_alignment", "string", "center"),
        xml_prop("title_font", "string", default["title_font"]),
        xml_prop("use_compositing", "bool", True),
        # RDP sessions have no vblank source; waiting for one costs CPU for nothing.
        xml_prop("vblank_mode", "string", "off"),
        xml_prop("show_frame_shadow", "bool", True),
        # Plank's window spans the screen width; a dock shadow outlines that
        # invisible window as a line across the desktop. The top bar has a
        # hairline border instead of a shadow.
        xml_prop("show_dock_shadow", "bool", False),
        xml_prop("workspace_count", "int", 2),
        xml_prop("placement_ratio", "int", 100),
        '  </property>',
        '</channel>', ""]), encoding="utf-8")
    t = default["terminal"]
    (d / "xfce4-terminal.xml").write_text(head + "\n".join([
        '<channel name="xfce4-terminal" version="1.0">',
        xml_prop("font-name", "string", default["mono_font"]),
        xml_prop("font-use-system", "bool", False),
        xml_prop("color-foreground", "string", t["foreground"]),
        xml_prop("color-background", "string", t["background"]),
        xml_prop("color-cursor", "string", t["cursor"]),
        xml_prop("color-cursor-use-default", "bool", False),
        xml_prop("color-palette", "string", t["palette"]),
        xml_prop("misc-menubar-default", "bool", False),
        xml_prop("misc-default-geometry", "string", "100x30"),
        xml_prop("scrolling-bar", "string", "TERMINAL_SCROLLBAR_NONE"),
        '</channel>', ""]), encoding="utf-8")
    (d / "xfce4-desktop.xml").write_text(head + "\n".join([
        '<channel name="xfce4-desktop" version="1.0">',
        '  <property name="desktop-icons" type="empty">',
        xml_prop("style", "int", 0),
        '  </property>',
        '  <property name="backdrop" type="empty">',
        '    <property name="screen0" type="empty">',
        *[f'      <property name="monitor{m}" type="empty"><property name="workspace0" type="empty">'
          f'<property name="last-image" type="string" value="{default["wallpaper"]}"/>'
          f'<property name="image-style" type="int" value="5"/></property></property>'
          for m in ("rdp0", "Virtual-1", "Virtual1", "default", "0")],
        '    </property>',
        '  </property>',
        '</channel>', ""]), encoding="utf-8")
    rgba = default["panel"]["rgba"]
    rgba_xml = "\n".join(f'          <value type="double" value="{v}"/>' for v in rgba)
    (d / "xfce4-panel.xml").write_text(head + f"""<channel name="xfce4-panel" version="1.0">
  <property name="configver" type="int" value="2"/>
  <property name="panels" type="array">
    <value type="int" value="1"/>
    <property name="dark-mode" type="bool" value="{'true' if default['panel']['dark_mode'] else 'false'}"/>
    <property name="panel-1" type="empty">
      <property name="position" type="string" value="p=6;x=0;y=0"/>
      <property name="length" type="double" value="100"/>
      <property name="position-locked" type="bool" value="true"/>
      <property name="size" type="uint" value="30"/>
      <property name="icon-size" type="uint" value="16"/>
      <property name="background-style" type="uint" value="1"/>
      <property name="background-rgba" type="array">
{rgba_xml}
      </property>
      <property name="plugin-ids" type="array">
        <value type="int" value="1"/>
        <value type="int" value="2"/>
        <value type="int" value="3"/>
        <value type="int" value="4"/>
        <value type="int" value="5"/>
        <value type="int" value="6"/>
        <value type="int" value="7"/>
      </property>
    </property>
  </property>
  <property name="plugins" type="empty">
    <property name="plugin-1" type="string" value="whiskermenu">
      <property name="button-icon" type="string" value="thoxos-mark"/>
      <property name="show-button-title" type="bool" value="false"/>
    </property>
    <property name="plugin-2" type="string" value="appmenu">
      <property name="bold-application-name" type="bool" value="true"/>
      <property name="compact-mode" type="bool" value="false"/>
      <property name="expand" type="bool" value="false"/>
    </property>
    <property name="plugin-3" type="string" value="separator">
      <property name="expand" type="bool" value="true"/>
      <property name="style" type="uint" value="0"/>
    </property>
    <property name="plugin-4" type="string" value="genmon"/>
    <property name="plugin-5" type="string" value="systray">
      <property name="square-icons" type="bool" value="true"/>
      <property name="icon-size" type="int" value="16"/>
    </property>
    <property name="plugin-6" type="string" value="clock">
      <property name="mode" type="uint" value="2"/>
      <property name="digital-layout" type="uint" value="3"/>
      <property name="digital-time-format" type="string" value="%a %b %-d  %-I:%M %p"/>
      <property name="digital-time-font" type="string" value="{default['font'].rsplit(' ', 1)[0]} Semi-Bold 10"/>
    </property>
    <property name="plugin-7" type="string" value="actions">
      <property name="appearance" type="uint" value="0"/>
      <property name="items" type="array">
        <value type="string" value="+logout"/>
        <value type="string" value="-lock-screen"/>
        <value type="string" value="-switch-user"/>
        <value type="string" value="-separator"/>
        <value type="string" value="-suspend"/>
        <value type="string" value="-hibernate"/>
        <value type="string" value="-hybrid-sleep"/>
        <value type="string" value="-separator"/>
        <value type="string" value="-shutdown"/>
        <value type="string" value="-restart"/>
        <value type="string" value="-separator"/>
        <value type="string" value="-logout-dialog"/>
      </property>
    </property>
  </property>
</channel>
""", encoding="utf-8")


# ------------------------------------------------------------------ checks

def check_brand_locks(root: Path, forbidden: Iterable[str]) -> list[str]:
    """Paths of generated text files that contain a forbidden brand hex."""
    bad = [f.lower() for f in forbidden]
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in (".png", ".bmp", ".svgz"):
            continue
        if path.name == "txf-tokens.json":  # declares the forbidden values itself
            continue
        try:
            text = path.read_text(encoding="utf-8").lower()
        except (UnicodeDecodeError, OSError):
            continue
        if any(b in text for b in bad):
            hits.append(str(path.relative_to(root)))
    return hits


def check_contrast(dark: Palette, light: Palette) -> list[str]:
    """WCAG AA (4.5:1) for body text on the main surfaces of both appearances."""
    problems = []
    for p in (dark, light):
        for bg_name in ("canvas", "surface", "elevated"):
            bg = getattr(p, bg_name)
            ratio = contrast(p.fg, bg)
            if ratio < 4.5:
                problems.append(f"{p.name} fg on {bg_name}: {ratio:.2f}")
    return problems


# -------------------------------------------------------------------- main

def generate(tokens_path: Path, adwaita_dir: Path, fonts_dir: Path, papirus_dir: Optional[Path],
             out: Path, footer: str) -> dict:
    tokens = load_tokens(tokens_path)
    dark, light = palettes(tokens)
    problems = check_contrast(dark, light)
    if problems:
        raise GenError("contrast below AA: " + "; ".join(problems))
    by_appearance = {"dark": dark, "light": light}

    txf = out / "usr/share/thox/txf"
    txf.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tokens_path, txf / "txf-tokens.json")
    looks_dir = out / "usr/share/thox/looks"
    looks_dir.mkdir(parents=True, exist_ok=True)
    for look in LOOKS:
        p = by_appearance[look.appearance]
        theme = out / "usr/share/themes" / look.theme_dir
        write_gtk_theme(theme, look, p, tokens, adwaita_dir)
        write_xfwm4_theme(theme, look, p, tokens)
        definition = look_definition(look, p, tokens)
        (looks_dir / f"{look.id}.json").write_text(json.dumps(definition, indent=2) + "\n", encoding="utf-8")
        write_terminal_scheme(out / f"usr/share/xfce4/terminal/colorschemes/thoxos-{look.id}.theme",
                              look.name, definition["terminal"])
    for p, name in ((dark, "ThoxOS-Dark"), (light, "ThoxOS-Light")):
        write_plank_theme(out / "usr/share/plank/themes" / name, p)
    default_look = json.loads((looks_dir / "slate.json").read_text(encoding="utf-8"))
    write_xfconf_defaults(out, default_look)

    bg = out / "usr/share/backgrounds/thoxos"
    bg.mkdir(parents=True, exist_ok=True)
    wallpaper(dark, (2560, 1440), fonts_dir).save(bg / "thoxos-dark.png", optimize=True)
    wallpaper(light, (2560, 1440), fonts_dir).save(bg / "thoxos-light.png", optimize=True)
    login = wallpaper(dark, (1920, 1080), fonts_dir, caption="ThoxOS Desktop on Debian 13 (Trixie)")
    login.save(bg / "thoxos-login.png", optimize=True)

    xrdp = out / "usr/share/xrdp"
    xrdp.mkdir(parents=True, exist_ok=True)
    # xrdp login logo: 250x110 (the ls_logo box), on the light login panel.
    logo = Image.new("RGB", (250, 110), light.canvas)
    draw_mark(logo, 22, 20, 70, light.primary)
    ImageDraw.Draw(logo).text((104, 33), "ThoxOS", font=font(fonts_dir, "Inter", 32, "Bold"), fill=light.fg)
    write_bmp24(logo, xrdp / "thoxos-logo.bmp")
    write_bmp24(wallpaper(dark, (1920, 1080), fonts_dir), xrdp / "thoxos-login-bg.bmp")

    write_plymouth(out / "usr/share/plymouth/themes/thoxos", dark, fonts_dir, footer)
    (out / "usr/share/pixmaps").mkdir(parents=True, exist_ok=True)
    write_app_icons(out, dark, light)
    icon_themes = write_icon_overlays(out, papirus_dir, dark, light)

    hits = check_brand_locks(out, tokens["brandLocks"].get("forbidden", FORBIDDEN_DEFAULT))
    if hits:
        raise GenError("forbidden brand colors in generated files: " + ", ".join(hits[:10]))
    manifest = {
        "schema": "thox.thoxos-desktop.generated/v1",
        "designSystem": tokens.get("designSystem"),
        "looks": [look.id for look in LOOKS],
        "default": "slate",
        "iconThemes": icon_themes,
        "brandLockCheck": "pass",
    }
    (txf / "generated.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tokens", type=Path, required=True)
    parser.add_argument("--adwaita-dir", type=Path, required=True,
                        help="directory holding gtk-contained.css and gtk-contained-dark.css")
    parser.add_argument("--fonts-dir", type=Path, default=Path("/usr/share/fonts"))
    parser.add_argument("--papirus-dir", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--footer", default="ThoxOS Desktop · Debian 13 · kernel 6.12")
    args = parser.parse_args(argv)
    try:
        manifest = generate(args.tokens, args.adwaita_dir, args.fonts_dir, args.papirus_dir, args.out, args.footer)
    except GenError as error:
        print(f"txf_desktop_gen: {error}", file=sys.stderr)
        return 1
    print(f"txf_desktop_gen: wrote looks {', '.join(manifest['looks'])}; icon themes {manifest['iconThemes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
