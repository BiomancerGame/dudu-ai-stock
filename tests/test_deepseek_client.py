"""DeepSeek 客户端的重试/缓存/异常测试 (mock 不真发请求)。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import openai
import pytest

from core.errors import DeepSeekAPIError


def _make_response(content: str = "ok"):
    msg = MagicMock()
    msg.content = content
    msg.reasoning_content = None
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def test_call_api_strict_returns_content():
    from deepseek_client import DeepSeekClient

    client = DeepSeekClient(model="deepseek-chat")
    with patch.object(client.client.chat.completions, "create", return_value=_make_response("hello")):
        out = client.call_api_strict([{"role": "user", "content": "hi"}], temperature=0.0)
    assert out == "hello"


def test_call_api_legacy_swallows_error():
    """旧式 call_api 出错时返回字符串而非抛异常 (向后兼容)。"""
    from deepseek_client import DeepSeekClient

    client = DeepSeekClient(model="deepseek-chat")

    def _boom(*a, **k):
        # 构造可重试异常 - 模拟连接失败
        raise openai.APIConnectionError(request=MagicMock())

    with patch.object(client.client.chat.completions, "create", side_effect=_boom):
        out = client.call_api([{"role": "user", "content": "hi"}], temperature=0.1)
    assert out.startswith("API调用失败")


def test_call_api_strict_caches_result():
    """同样的 prompt 第二次直接命中缓存,不再调用底层 API。"""
    import uuid

    from deepseek_client import DeepSeekClient

    client = DeepSeekClient(model="deepseek-chat")
    # 每次运行用唯一内容,避免被磁盘上的 LLM 缓存污染
    msgs = [{"role": "user", "content": f"cache-test-{uuid.uuid4()}"}]

    create = MagicMock(return_value=_make_response("cached-value"))
    with patch.object(client.client.chat.completions, "create", create):
        a = client.call_api_strict(msgs, temperature=0.0)
        b = client.call_api_strict(msgs, temperature=0.0)
    assert a == b == "cached-value"
    assert create.call_count == 1  # 第二次走缓存
