"""ui.menu 测试 — 不依赖 streamlit 渲染。"""
from __future__ import annotations

import json

from ui.menu import (
    MENU_ITEMS,
    group_has_enabled,
    load_menu_config,
    menu_enabled,
    save_menu_config,
)


def test_load_menu_default_when_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    cfg = load_menu_config()
    assert set(cfg.keys()) == set(MENU_ITEMS.keys())
    assert all(isinstance(v, bool) for v in cfg.values())


def test_save_and_reload_menu(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    expected = {k: (i % 2 == 0) for i, k in enumerate(MENU_ITEMS.keys())}
    save_menu_config(expected)
    loaded = load_menu_config()
    for k, v in expected.items():
        assert loaded[k] == v


def test_menu_enabled_and_group():
    cfg = {k: True for k in MENU_ITEMS}
    cfg["nav_main_force"] = False
    assert menu_enabled("nav_main_force", cfg) is False
    assert menu_enabled("nav_history", cfg) is True
    assert group_has_enabled("common", cfg) is True
