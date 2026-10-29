"""Tests for the top-bar AI route chip (desktop/bin/thoxos-ai-chip)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_chip():
    path = ROOT / "desktop" / "bin" / "thoxos-ai-chip"
    loader = importlib.machinery.SourceFileLoader("thoxos_ai_chip", str(path))
    spec = importlib.util.spec_from_loader("thoxos_ai_chip", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["thoxos_ai_chip"] = module
    loader.exec_module(module)
    return module


def runner(code):
    return lambda argv, **kw: subprocess.CompletedProcess(argv, code)


def test_relay_active_means_hosted():
    chip = load_chip()
    assert chip.route(run=runner(0), probe=lambda: True) == "HOSTED"


def test_local_listener_means_local():
    chip = load_chip()
    assert chip.route(run=runner(3), probe=lambda: True) == "LOCAL"


def test_nothing_means_off():
    chip = load_chip()
    assert chip.route(run=runner(3), probe=lambda: False) == "AI OFF"


def test_markup_uses_token_colors(tmp_path):
    chip = load_chip()
    palette = chip.colors(str(ROOT / "desktop" / "tokens" / "txf-tokens.json"))
    assert palette["primary"] == "#05A451" and palette["hosted"] == "#FBBF24"
    local = chip.markup("LOCAL", palette)
    assert "background='#05A451'" in local and "<tool>" in local
    hosted = chip.markup("HOSTED", palette)
    assert "background='#FBBF24'" in hosted
    assert chip.colors(str(tmp_path / "missing.json"))["primary"] == "#05A451"
