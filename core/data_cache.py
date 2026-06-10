"""数据层缓存 — 缓存外部 API 获取的股票数据。

按 (函数名, 参数) 哈希缓存到 ``data/data_cache``,
避免短时间内重复请求外部数据源。

用法:
    from core.data_cache import cached

    @cached(ttl=600)  # 10分钟
    def get_financial_data(symbol):
        ...
"""
from __future__ import annotations

import hashlib
import json
import os
import functools
from typing import Any, Callable

try:
    import diskcache
except ImportError:  # pragma: no cover
    diskcache = None  # type: ignore

_CACHE_DIR = os.path.join("data", "data_cache")
os.makedirs(_CACHE_DIR, exist_ok=True)

_data_cache: Any
if diskcache is not None:
    _data_cache = diskcache.Cache(_CACHE_DIR, size_limit=256 * 1024 * 1024)
else:
    class _NoopCache:
        def get(self, key, default=None): return default
        def set(self, *_a, **_k): return False
        def __contains__(self, _k): return False
    _data_cache = _NoopCache()


def _make_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """生成缓存键。"""
    payload = json.dumps(
        {"fn": func_name, "a": [str(a) for a in args], "kw": {k: str(v) for k, v in sorted(kwargs.items())}},
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cached(ttl: int = 300):
    """装饰器：缓存函数返回值，ttl 为秒数。

    仅缓存非 None 且非 error 的结果。
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = _make_key(func.__qualname__, args, kwargs)
            hit = _data_cache.get(key)
            if hit is not None:
                return hit
            result = func(*args, **kwargs)
            # 不缓存 None 或包含 error 的结果
            if result is not None:
                if isinstance(result, dict) and "error" in result:
                    return result
                _data_cache.set(key, result, expire=ttl)
            return result
        return wrapper
    return decorator


def invalidate_all():
    """清除全部数据缓存。"""
    if hasattr(_data_cache, 'clear'):
        _data_cache.clear()
