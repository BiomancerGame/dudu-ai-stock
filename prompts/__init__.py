"""Prompt 外置加载器 — 把硬编码 prompt 逐步迁出代码。

用法:
    from prompts import render
    text = render("technical_analysis", stock_info=info, indicators=ind)

约定:
- ``prompts/<name>.md`` 是模板文件,使用 Python ``str.format_map`` 渲染
- 占位符语法 ``{var}``,需要字面量大括号请写 ``{{`` ``}}``
- 加载结果会被 LRU 缓存,运行期改动需重启进程
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

_DIR = os.path.dirname(os.path.abspath(__file__))


class PromptNotFound(KeyError):
    pass


@lru_cache(maxsize=128)
def load(template: str) -> str:
    path = os.path.join(_DIR, f"{template}.md")
    if not os.path.exists(path):
        raise PromptNotFound(template)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def render(template: str, /, **kwargs: Any) -> str:
    """渲染模板。``template`` 是 ``prompts/<template>.md`` 的文件名(不含扩展名)。

    第一参数为 positional-only,避免与模板里的 ``{template}`` 占位符冲突。
    """
    text = load(template)

    class _Safe(dict):
        def __missing__(self, key: str) -> str:  # type: ignore[override]
            return f"{{{key}}}"

    return text.format_map(_Safe(kwargs))
