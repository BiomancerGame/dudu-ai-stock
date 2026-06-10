"""菜单与导航 — 从 ``app.py`` 抽出。

仅包含纯逻辑/配置,不直接渲染,以便单元测试。
"""
from __future__ import annotations

import json
import os
from typing import Any

import streamlit as st

from core.logging_setup import get_logger

logger = get_logger(__name__)

MENU_CONFIG_PATH = os.path.join(".streamlit", "menu_config.json")

MENU_ITEMS: dict[str, dict[str, Any]] = {
    "nav_main_force": {"label": "💰 主力选股", "group": "stock_select", "default": True},
    "nav_low_price_bull": {"label": "🐂 低价擒牛", "group": "stock_select", "default": True},
    "nav_small_cap": {"label": "📊 小市值策略", "group": "stock_select", "default": True},
    "nav_profit_growth": {"label": "📈 净利增长", "group": "stock_select", "default": True},
    "nav_value_stock": {"label": "💎 低估值策略", "group": "stock_select", "default": True},
    "nav_sector_strategy": {"label": "🎯 智策板块", "group": "strategy", "default": True},
    "nav_longhubang": {"label": "🐉 智囊团游资龙虎榜", "group": "strategy", "default": True},
    "nav_news_flow": {"label": "📰 新闻流量", "group": "strategy", "default": True},
    "nav_macro_analysis": {"label": "🌏 宏观分析", "group": "strategy", "default": True},
    "nav_macro_cycle": {"label": "🧭 宏观周期", "group": "strategy", "default": True},
    "nav_portfolio": {"label": "📊 持仓分析", "group": "investment", "default": True},
    "nav_smart_monitor": {"label": "🤖 AI盯盘", "group": "investment", "default": True},
    "nav_monitor": {"label": "📡 实时监测", "group": "investment", "default": True},
    "nav_commonality": {"label": "🔗 共性追踪", "group": "strategy", "default": True},
    "nav_history": {"label": "📖 历史记录", "group": "common", "default": True},
}

MENU_GROUPS: list[tuple[str, str]] = [
    ("stock_select", "🎯 选股板块"),
    ("strategy", "📊 策略分析"),
    ("investment", "💼 投资管理"),
    ("common", "通用"),
]

PAGE_KEYS: list[str] = [
    "show_history", "show_monitor", "show_config", "show_other_config",
    "show_main_force", "show_sector_strategy", "show_longhubang",
    "show_portfolio", "show_smart_monitor", "show_low_price_bull",
    "show_small_cap", "show_profit_growth", "show_news_flow",
    "show_macro_cycle", "show_macro_analysis", "show_value_stock",
    "show_menu_config", "show_commonality",
]

VIEW_TO_PAGE_KEY: dict[str, str] = {
    "main_force": "show_main_force",
    "low_price_bull": "show_low_price_bull",
    "small_cap": "show_small_cap",
    "profit_growth": "show_profit_growth",
    "value_stock": "show_value_stock",
    "sector_strategy": "show_sector_strategy",
    "longhubang": "show_longhubang",
    "news_flow": "show_news_flow",
    "macro_analysis": "show_macro_analysis",
    "macro_cycle": "show_macro_cycle",
    "portfolio": "show_portfolio",
    "smart_monitor": "show_smart_monitor",
    "monitor": "show_monitor",
    "history": "show_history",
    "menu_config": "show_menu_config",
    "config": "show_config",
    "other_config": "show_other_config",
    "commonality": "show_commonality",
}


def load_menu_config() -> dict[str, bool]:
    """读取菜单启用配置。"""
    defaults = {key: item["default"] for key, item in MENU_ITEMS.items()}
    try:
        if os.path.exists(MENU_CONFIG_PATH):
            with open(MENU_CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            defaults.update({key: bool(saved.get(key, defaults[key])) for key in defaults})
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("读取菜单配置失败,使用默认值: %s", e)
    return defaults


def save_menu_config(menu_config: dict[str, bool]) -> None:
    """保存菜单启用配置。"""
    os.makedirs(os.path.dirname(MENU_CONFIG_PATH), exist_ok=True)
    with open(MENU_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(menu_config, f, ensure_ascii=False, indent=2)


def menu_enabled(menu_key: str, menu_config: dict[str, bool]) -> bool:
    return bool(menu_config.get(menu_key, MENU_ITEMS.get(menu_key, {}).get("default", True)))


def group_has_enabled(group_name: str, menu_config: dict[str, bool]) -> bool:
    return any(
        item["group"] == group_name and menu_enabled(key, menu_config)
        for key, item in MENU_ITEMS.items()
    )


def activate_page(page_key: str) -> None:
    st.session_state[page_key] = True
    for key in PAGE_KEYS:
        if key != page_key and key in st.session_state:
            del st.session_state[key]


def activate_home() -> None:
    for key in PAGE_KEYS:
        if key in st.session_state:
            del st.session_state[key]


def apply_view_from_query_params() -> None:
    view = st.query_params.get("view", "")
    if isinstance(view, list):
        view = view[0] if view else ""

    if view == "home":
        activate_home()
    elif view in VIEW_TO_PAGE_KEY:
        activate_page(VIEW_TO_PAGE_KEY[view])


def sidebar_nav_link(label: str, view: str, help_text: str | None = None) -> None:
    title = f' title="{help_text}"' if help_text else ""
    st.markdown(
        f'<a class="sidebar-nav-link" href="?view={view}" target="_self"{title}>{label}</a>',
        unsafe_allow_html=True,
    )
