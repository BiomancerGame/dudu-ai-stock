"""AI 调用缓存。

按 (model, messages, temperature) 哈希缓存到 ``data/llm_cache``,
避免重复花费 API 费用。

用法:
    from core.cache import llm_cache, make_key
    key = make_key(model, messages, temperature)
    if (hit := llm_cache.get(key)) is not None:
        return hit
    ...
    llm_cache.set(key, result, expire=3600)
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

try:
    import diskcache
except ImportError:  # pragma: no cover
    diskcache = None  # type: ignore

_CACHE_DIR = os.path.join("data", "llm_cache")
os.makedirs(_CACHE_DIR, exist_ok=True)

llm_cache: Any
if diskcache is not None:
    llm_cache = diskcache.Cache(_CACHE_DIR, size_limit=512 * 1024 * 1024)
else:  # 退化为 no-op
    class _NoopCache:
        def get(self, *_a, **_k): return None
        def set(self, *_a, **_k): return False
        def __contains__(self, _k): return False
    llm_cache = _NoopCache()


def make_key(model: str, messages: list[dict], temperature: float) -> str:
    payload = json.dumps(
        {"m": model, "msgs": messages, "t": temperature},
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
