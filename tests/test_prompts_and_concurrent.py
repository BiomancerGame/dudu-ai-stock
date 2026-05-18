"""prompts 加载器 + 并发执行器测试。"""
from __future__ import annotations

import time

import pytest

from core.concurrent import run_parallel
from prompts import PromptNotFound, render


def test_render_known_prompt():
    out = render("technical_analysis", symbol="000001", name="平安银行", current_price=12.3,
                 change_percent=1.2, price=12.3, ma5="", ma10="", ma20="", ma60="",
                 rsi="", macd="", macd_signal="", bb_upper="", bb_lower="",
                 k_value="", d_value="", volume_ratio="")
    assert "000001" in out
    assert "平安银行" in out
    # 未提供的占位符应保持原样而不报错
    assert "{not_a_var}" not in out  # 没用过该名称


def test_render_missing_var_does_not_raise():
    out = render("technical_analysis", symbol="000001")
    assert "000001" in out
    assert "{name}" in out  # 缺失变量保留为字面量


def test_render_unknown_template_raises():
    with pytest.raises(PromptNotFound):
        render("__no_such_template__")


def test_run_parallel_collects_results():
    def slow(x: int) -> int:
        time.sleep(0.05)
        return x * 2

    out = run_parallel({
        "a": (slow, (1,)),
        "b": (slow, (2,)),
        "c": (slow, (3,)),
    }, max_workers=3)
    assert out == {"a": 2, "b": 4, "c": 6}


def test_run_parallel_captures_exception():
    def boom():
        raise RuntimeError("nope")

    out = run_parallel({"x": (boom, ())})
    assert isinstance(out["x"], RuntimeError)
