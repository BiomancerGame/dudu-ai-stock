"""通用并发执行器 — 多 agent 并行触发。

Streamlit 单进程下,IO 密集的 LLM 调用用线程池并行可显著缩短总耗时
(3 个 agent 串行 30s -> 并行约 12s)。

用法:
    from core.concurrent import run_parallel
    results = run_parallel({
        "tech": (agents.technical_analyst_agent, (info, data, ind)),
        "fund": (agents.fundamental_analyst_agent, (info, fin, q)),
    }, max_workers=4)
    # results = {"tech": <return>, "fund": <return>} 或 {"tech": Exception(...)}
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from core.logging_setup import get_logger

logger = get_logger(__name__)


def run_parallel(
    tasks: dict[str, tuple[Callable[..., Any], tuple, dict] | tuple[Callable[..., Any], tuple]],
    *,
    max_workers: int = 4,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """并行执行带名字的可调用集合。

    每个 task 值可以是 ``(fn, args)`` 或 ``(fn, args, kwargs)``。
    返回 ``{name: result_or_exception}``。
    """
    out: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {}
        for name, spec in tasks.items():
            if len(spec) == 2:
                fn, args = spec  # type: ignore[misc]
                kwargs: dict = {}
            else:
                fn, args, kwargs = spec  # type: ignore[misc]
            futures[ex.submit(fn, *args, **kwargs)] = name

        for fut in as_completed(futures):
            name = futures[fut]
            try:
                out[name] = fut.result()
            except Exception as e:
                logger.exception("并行任务 %s 失败", name)
                if raise_on_error:
                    raise
                out[name] = e
    return out
