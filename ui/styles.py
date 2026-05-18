"""注入全局 CSS — 从 ``ui/styles.css`` 加载。"""
from __future__ import annotations

import os
from functools import lru_cache

import streamlit as st

_CSS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles.css")


@lru_cache(maxsize=1)
def _load_css() -> str:
    with open(_CSS_PATH, "r", encoding="utf-8") as f:
        return f.read()


def inject_styles() -> None:
    """把全局样式注入到当前 Streamlit 页面。"""
    st.markdown(f"<style>\n{_load_css()}\n</style>", unsafe_allow_html=True)
