"""Consistency checks for the ThoxOS Desktop overlay: launchers, dock and icons."""

from __future__ import annotations

import configparser
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "desktop" / "overlay"
APPS = OVERLAY / "usr" / "share" / "applications"
sys.path.insert(0, str(ROOT / "desktop" / "generator"))

import txf_desktop_gen as gen  # noqa: E402

# Launchers the dock and menu may point at that Debian packages install.
SYSTEM_APPS = {"thunar.desktop", "xfce4-terminal.desktop", "firefox-esr.desktop"}


def entries():
    for path in sorted(APPS.glob("*.desktop")):
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.optionxform = str
        parser.read(path, encoding="utf-8")
        yield path, parser["Desktop Entry"]


def test_thoxos_launchers_use_their_own_generated_icons():
    generated = set(gen.APP_ICONS) | {"thoxos-mark"}
    icons = {}
    for path, entry in entries():
        if path.name.startswith("thoxos-"):
            assert entry["Icon"] in generated, f"{path.name} uses {entry['Icon']}"
            icons[path.name] = entry["Icon"]
    # Every ThoxOS launcher is distinguishable in the dock and the menu.
    assert len(set(icons.values())) == len(icons)


def test_launchers_never_use_terminal_hold():
    for path, entry in entries():
        assert "--hold" not in entry["Exec"], f"{path.name}: use thoxos-hold instead of --hold"
        for tool in re.findall(r"\b(thoxos-[a-z-]+)\b", entry["Exec"]):
            assert (ROOT / "desktop" / "bin" / tool).is_file() or tool == "thoxos-ginux", f"{tool} not shipped"


def test_dock_items_resolve_to_launchers():
    dconf = (OVERLAY / "etc" / "dconf" / "db" / "local.d" / "10-thoxos-dock").read_text()
    items = re.findall(r"'([^']+\.dockitem)'", dconf)
    assert items, "dock has no items"
    launchers = OVERLAY / "etc" / "skel" / ".config" / "plank" / "dock1" / "launchers"
    assert {p.name for p in launchers.glob("*.dockitem")} == set(items)
    for item in items:
        target = re.search(r"Launcher=file://(\S+)", (launchers / item).read_text()).group(1)
        name = Path(target).name
        assert (APPS / name).is_file() or name in SYSTEM_APPS, f"{item} points at {target}"


def test_menu_favorites_resolve():
    rc = (OVERLAY / "etc" / "xdg" / "xfce4" / "panel" / "whiskermenu-1.rc").read_text()
    favorites = re.search(r"^favorites=(.*)$", rc, flags=re.M).group(1).split(",")
    for name in favorites:
        assert (APPS / name).is_file() or name in SYSTEM_APPS, name
