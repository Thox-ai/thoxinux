"""Tests for the ThoxOS Desktop theme generator (desktop/generator/txf_desktop_gen.py)."""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "generator"))

import txf_desktop_gen as gen  # noqa: E402

TOKENS = ROOT / "desktop" / "tokens" / "txf-tokens.json"


@pytest.fixture(scope="module")
def palettes():
    return gen.palettes(gen.load_tokens(TOKENS))


def test_tokens_hold_the_brand_locks():
    tokens = gen.load_tokens(TOKENS)
    assert tokens["brandLocks"]["brandGreen"] == "#05A451"
    assert tokens["dark"]["primary"] == "#05A451"
    assert set(tokens["brandLocks"]["forbidden"]) == {"#10B981", "#00FF88"}


def test_rejects_other_schemas(tmp_path):
    bad = tmp_path / "t.json"
    bad.write_text(json.dumps({"schema": "something/else"}))
    with pytest.raises(gen.GenError, match="schema"):
        gen.load_tokens(bad)


def test_hex_round_trip():
    assert gen.parse_hex("#05a451") == (5, 164, 81)
    assert gen.parse_hex("#abc") == (170, 187, 204)
    assert gen.to_hex((5, 164, 81)) == "#05A451"
    with pytest.raises(gen.GenError):
        gen.parse_hex("#12345")


def test_adwaita_blue_becomes_txf_green(palettes):
    dark, light = palettes
    for p, blue in ((dark, "#15539e"), (light, "#3584e4")):
        mapped = gen.map_color(gen.parse_hex(blue), p, gen.neutral_ramp(p))
        assert mapped == p.primary  # the reference accent lands exactly on the token
        hue = gen.hls(mapped)[0] * 360
        assert 140 <= hue <= 155


def test_neutrals_map_monotonically_onto_the_zinc_ramp(palettes):
    dark, _ = palettes
    ramp = gen.neutral_ramp(dark)
    greys = ["#1b1b1b", "#2d2d2d", "#353535", "#5b5b5b", "#919190", "#eeeeec"]
    mapped = [gen.luminance(gen.map_color(gen.parse_hex(g), dark, ramp)) for g in greys]
    assert mapped == sorted(mapped)
    assert gen.map_color(gen.parse_hex("#353535"), dark, ramp) == dark.surface
    assert gen.map_color(gen.parse_hex("#eeeeec"), dark, ramp) == dark.fg


def test_remap_css_rewrites_hex_and_rgba(palettes):
    dark, _ = palettes
    css = "a { color: #15539e; background: rgba(53, 53, 53, 0.5); border: 1px solid #1b1b1b; } b { color: white; }"
    out = gen.remap_css(css, dark)
    assert "#15539e" not in out and "#05a451" in out
    assert "rgba(24, 24, 27, 0.5)" in out  # #353535 -> surface #18181B, alpha kept
    assert "color: white" in out


def test_body_text_meets_aa(palettes):
    assert gen.check_contrast(*palettes) == []


def test_terminal_palette_has_sixteen_colors(palettes):
    for p in palettes:
        scheme = gen.terminal_palette(p)
        colors = scheme["palette"].split(";")
        assert len(colors) == 16
        assert all(c.startswith("#") and len(c) == 7 for c in colors)
        assert scheme["cursor"] == gen.to_hex(p.primary)


def test_look_definitions_cover_the_three_txf_looks(palettes):
    tokens = gen.load_tokens(TOKENS)
    dark, light = palettes
    ids = [look.id for look in gen.LOOKS]
    assert ids == ["slate", "porcelain", "console-pro"]
    for look in gen.LOOKS:
        p = dark if look.appearance == "dark" else light
        d = gen.look_definition(look, p, tokens)
        assert d["schema"] == "thox.thoxos-desktop.look/v1"
        assert d["button_layout"] == "CHM|"  # traffic lights on the left
        assert d["dock"]["icon_size"] == 46
        assert len(d["panel"]["rgba"]) == 4
    console = next(look for look in gen.LOOKS if look.id == "console-pro")
    assert console.dock_position == "left" and console.chrome == "mono"


def test_brand_lock_scan_finds_forbidden_values(tmp_path):
    (tmp_path / "ok.css").write_text("a { color: #05A451 }")
    (tmp_path / "bad.css").write_text("a { color: #10b981 }")
    (tmp_path / "txf-tokens.json").write_text('{"forbidden": ["#10B981"]}')
    assert gen.check_brand_locks(tmp_path, ["#10B981", "#00FF88"]) == ["bad.css"]


def test_bmp_writer_produces_a_24_bit_bitmap(tmp_path):
    pil = pytest.importorskip("PIL.Image")
    img = pil.new("RGB", (3, 2), (5, 164, 81))
    out = tmp_path / "x.bmp"
    gen.write_bmp24(img, out)
    data = out.read_bytes()
    assert data[:2] == b"BM"
    width, height, _planes, bits = struct.unpack("<iiHH", data[18:30])
    assert (width, height, bits) == (3, 2, 24)
    assert data[54:57] == bytes([81, 164, 5])  # BGR order
    assert len(data) == 54 + 2 * 12  # rows padded to 4 bytes


def test_icon_dir_section():
    assert "Size=48" in gen.icon_dir_section("48x48/places")
    assert "Size=128" in gen.icon_dir_section("128x128/places")


def test_full_generation_with_stub_adwaita(tmp_path):
    pytest.importorskip("PIL.Image")
    fonts = Path("/usr/share/fonts")
    found = {p.name for p in fonts.rglob("*") if p.is_file()} if fonts.is_dir() else set()
    if not ({"Inter-Regular.otf", "InterVariable.ttf", "Inter-Regular.ttf"} & found):
        pytest.skip("Inter not installed on this machine")
    if not ({"JetBrainsMono-Regular.ttf", "JetBrainsMono[wght].ttf"} & found):
        pytest.skip("JetBrains Mono not installed on this machine")
    adw = tmp_path / "adw"
    adw.mkdir()
    for name in ("gtk-contained.css", "gtk-contained-dark.css"):
        (adw / name).write_text("@define-color theme_selected_bg_color #15539e;\n* { color: #eeeeec; }\n")
    out = tmp_path / "root"
    manifest = gen.generate(TOKENS, adw, fonts, None, out, "ThoxOS Desktop")
    assert manifest["looks"] == ["slate", "porcelain", "console-pro"]
    for theme in ("ThoxOS-Slate", "ThoxOS-Porcelain", "ThoxOS-ConsolePro"):
        assert (out / f"usr/share/themes/{theme}/gtk-3.0/gtk.css").is_file()
        assert (out / f"usr/share/themes/{theme}/xfwm4/themerc").is_file()
        assert (out / f"usr/share/themes/{theme}/xfwm4/close-active.png").is_file()
        # A theme settings.ini that sets prefer-dark makes GTK 3 reload the theme forever.
        assert not (out / f"usr/share/themes/{theme}/gtk-3.0/settings.ini").exists()
    assert (out / "usr/share/plymouth/themes/thoxos/thoxos.script").is_file()
    xfwm = (out / "etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml").read_text()
    assert '<property name="vblank_mode" type="string" value="off"/>' in xfwm
    panel = (out / "etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml").read_text()
    assert 'value="whiskermenu"' in panel and 'value="genmon"' in panel
