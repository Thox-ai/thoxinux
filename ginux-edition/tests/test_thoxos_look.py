"""Tests for the ThoxOS Desktop look switcher (desktop/bin/thoxos-look)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop" / "generator"))
import txf_desktop_gen as gen  # noqa: E402


def load_look(monkeypatch, looks_dir: Path, conf: Path):
    monkeypatch.setenv("THOXOS_LOOKS_DIR", str(looks_dir))
    monkeypatch.setenv("THOXOS_DESKTOP_CONF", str(conf))
    path = ROOT / "desktop" / "bin" / "thoxos-look"
    loader = importlib.machinery.SourceFileLoader("thoxos_look", str(path))
    spec = importlib.util.spec_from_loader("thoxos_look", loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules["thoxos_look"] = module
    loader.exec_module(module)
    return module


@pytest.fixture
def looks_dir(tmp_path):
    tokens = gen.load_tokens(ROOT / "desktop" / "tokens" / "txf-tokens.json")
    dark, light = gen.palettes(tokens)
    d = tmp_path / "looks"
    d.mkdir()
    for look in gen.LOOKS:
        p = dark if look.appearance == "dark" else light
        (d / f"{look.id}.json").write_text(json.dumps(gen.look_definition(look, p, tokens)))
    return d


class FakeRun:
    """Records commands; answers xfconf -l and xrandr like a live XFCE session."""

    def __init__(self, fail_prefix: str = ""):
        self.calls: list[list[str]] = []
        self.fail_prefix = fail_prefix

    def __call__(self, argv):
        argv = list(argv)
        self.calls.append(argv)
        out = ""
        if argv[:3] == ["xfconf-query", "-c", "xfce4-desktop"] and "-l" in argv:
            out = "/backdrop/screen0/monitorrdp0/workspace0/last-image\n/backdrop/screen0/monitorrdp0/workspace0/image-style\n"
        elif argv[:2] == ["xrandr", "--listmonitors"]:
            out = "Monitors: 1\n 0: +*rdp0 1920/508x1080/286+0+0  rdp0\n"
        code = 1 if self.fail_prefix and " ".join(argv).startswith(self.fail_prefix) else 0
        return subprocess.CompletedProcess(argv, code, out, "boom" if code else "")


def test_plan_sets_theme_wallpaper_dock_and_panel(monkeypatch, tmp_path, looks_dir):
    mod = load_look(monkeypatch, looks_dir, tmp_path / "desktop.conf")
    looks = mod.load_looks(looks_dir)
    steps = mod.plan(looks["console-pro"], FakeRun())
    flat = [" ".join(s) for s in steps]
    assert any("/Net/ThemeName" in s and "ThoxOS-ConsolePro" in s for s in flat)
    assert any("/general/button_layout" in s and "CHM|" in s for s in flat)
    assert any("position left" in s for s in flat)
    assert any("monitorrdp0/workspace0/last-image" in s and "thoxos-dark.png" in s for s in flat)
    rgba = next(s for s in steps if "/panels/panel-1/background-rgba" in s)
    assert rgba.count("double") == 4


def test_porcelain_is_light(monkeypatch, tmp_path, looks_dir):
    mod = load_look(monkeypatch, looks_dir, tmp_path / "desktop.conf")
    steps = [" ".join(s) for s in mod.plan(mod.load_looks(looks_dir)["porcelain"], FakeRun())]
    assert any("ThoxOS-Papirus-Light" in s for s in steps)
    assert any("thoxos-light.png" in s for s in steps)
    assert any("/panels/dark-mode" in s and s.endswith("false") for s in steps)


def test_set_remembers_choice_and_apply_uses_it(monkeypatch, tmp_path, looks_dir):
    mod = load_look(monkeypatch, looks_dir, tmp_path / "desktop.conf")
    env = {"HOME": str(tmp_path / "home")}
    run = FakeRun()
    assert mod.main(["set", "porcelain"], env, run) == 0
    assert (tmp_path / "home/.config/thoxos/look").read_text().strip() == "porcelain"
    assert mod.chosen_look(mod.load_looks(looks_dir), env, tmp_path / "desktop.conf") == "porcelain"


def test_system_default_applies_until_user_chooses(monkeypatch, tmp_path, looks_dir):
    conf = tmp_path / "desktop.conf"
    conf.write_text("DEFAULT_LOOK=console-pro\n")
    mod = load_look(monkeypatch, looks_dir, conf)
    looks = mod.load_looks(looks_dir)
    env = {"HOME": str(tmp_path / "home")}
    assert mod.chosen_look(looks, env, conf) == "console-pro"
    conf.write_text("DEFAULT_LOOK=not-a-look\n")
    assert mod.chosen_look(looks, env, conf) == "slate"


def test_set_system_default_rewrites_only_its_line(monkeypatch, tmp_path, looks_dir):
    conf = tmp_path / "desktop.conf"
    conf.write_text("# keep me\nDEFAULT_LOOK=slate\nOTHER=1\n")
    mod = load_look(monkeypatch, looks_dir, conf)
    mod.set_system_default("porcelain", conf)
    text = conf.read_text()
    assert "# keep me" in text and "OTHER=1" in text and "DEFAULT_LOOK=porcelain" in text
    assert text.count("DEFAULT_LOOK=") == 1


def test_off_stops_session_apply(monkeypatch, tmp_path, looks_dir):
    mod = load_look(monkeypatch, looks_dir, tmp_path / "desktop.conf")
    env = {"HOME": str(tmp_path / "home")}
    run = FakeRun()
    assert mod.main(["off"], env, run) == 0
    assert mod.main(["apply"], env, run) == 0
    assert run.calls == []
    assert mod.main(["on"], env, run) == 0
    assert mod.main(["apply", "--quiet"], env, run) == 0
    assert run.calls


def test_failed_steps_are_counted_not_fatal(monkeypatch, tmp_path, looks_dir, capsys):
    mod = load_look(monkeypatch, looks_dir, tmp_path / "desktop.conf")
    run = FakeRun(fail_prefix="gsettings")
    code = mod.apply(mod.load_looks(looks_dir)["slate"], run)
    assert code == 3
    assert "3 step(s) failed" in capsys.readouterr().out


def test_unknown_look_is_an_error(monkeypatch, tmp_path, looks_dir, capsys):
    mod = load_look(monkeypatch, looks_dir, tmp_path / "desktop.conf")
    assert mod.main(["set", "aqua"], {"HOME": str(tmp_path)}, FakeRun()) == 2
    assert "usage" in capsys.readouterr().err


def test_rejects_foreign_look_files(monkeypatch, tmp_path):
    d = tmp_path / "looks"
    d.mkdir()
    (d / "x.json").write_text(json.dumps({"schema": "other", "id": "x"}))
    mod = load_look(monkeypatch, d, tmp_path / "desktop.conf")
    with pytest.raises(mod.LookError):
        mod.load_looks(d)
