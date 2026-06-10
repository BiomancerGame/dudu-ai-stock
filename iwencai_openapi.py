"""
问财新版 OpenAPI 客户端 (SkillHub 2.0)

替代失效的 pywencai (老接口 get-robot-data 已被官方废弃)。
新接口地址: https://openapi.iwencai.com/v1/query2data
需要 API Key, 在 https://www.iwencai.com/skillhub 免费申请。

环境变量:
    IWENCAI_API_KEY: 问财 OpenAPI 的 Bearer Token
    IWENCAI_BASE_URL: 可选,默认 https://openapi.iwencai.com
"""

import os
import secrets
from typing import List, Dict, Optional

import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


IWENCAI_BASE_URL = os.environ.get("IWENCAI_BASE_URL", "https://openapi.iwencai.com")
IWENCAI_API_KEY = os.environ.get("IWENCAI_API_KEY", "").strip()


def is_available() -> bool:
    """检测是否配置了 API Key"""
    return bool(IWENCAI_API_KEY)


def _claw_headers(skill_id: str = "stock-pick") -> dict:
    """SkillHub 2.0 必须的 X-Claw 鉴权头"""
    return {
        "X-Claw-Call-Type": "normal",
        "X-Claw-Skill-Id": skill_id,
        "X-Claw-Skill-Version": "2.0.0",
        "X-Claw-Plugin-Id": "none",
        "X-Claw-Plugin-Version": "none",
        "X-Claw-Trace-Id": secrets.token_hex(32),
    }


def query2data(query: str, page: int = 1, limit: int = 100,
               timeout: int = 30) -> Optional[List[Dict]]:
    """
    问财 NL 数据查询 (结构化字段返回)。

    Args:
        query: 自然语言查询语句,如 "2026年2月22日以来主力资金净流入排名,市值50-200亿"
        page: 页码,从 1 开始
        limit: 每页条数,实测可调到 100
        timeout: 单次请求超时(秒)

    Returns:
        List[Dict] 每条记录为一只股票;失败返回 None
    """
    if not IWENCAI_API_KEY:
        print("[iwencai-openapi] ❌ 未配置 IWENCAI_API_KEY,跳过")
        return None

    headers = {
        "Authorization": f"Bearer {IWENCAI_API_KEY}",
        "Content-Type": "application/json",
        **_claw_headers(),
    }
    payload = {
        "query": query,
        "page": str(page),
        "limit": str(limit),
        "is_cache": "1",
        "expand_index": "true",
    }

    url = f"{IWENCAI_BASE_URL}/v1/query2data"
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        print(f"[iwencai-openapi] ❌ 网络异常: {e}")
        return None

    if r.status_code != 200:
        print(f"[iwencai-openapi] ❌ HTTP {r.status_code}: {r.text[:200]}")
        return None

    try:
        data = r.json()
    except ValueError:
        print(f"[iwencai-openapi] ❌ 响应非 JSON: {r.text[:200]}")
        return None

    if data.get("status_code", 0) != 0:
        print(f"[iwencai-openapi] ❌ 业务错误: {data.get('status_msg', '')}")
        return None

    return data.get("datas") or []


def query_to_dataframe(query: str, max_pages: int = 2, page_size: int = 100) -> Optional[pd.DataFrame]:
    """
    自动翻页拉取并合并为 DataFrame。

    Args:
        query: 自然语言查询
        max_pages: 最多拉取的页数 (默认 2 = 200 条)
        page_size: 每页条数 (默认 100)

    Returns:
        合并后的 DataFrame,失败返回 None
    """
    all_rows: List[Dict] = []
    for page in range(1, max_pages + 1):
        rows = query2data(query, page=page, limit=page_size)
        if rows is None:
            # 第一页就失败 => 彻底失败;后续页失败 => 用前面的数据
            if page == 1:
                return None
            break
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break  # 已到尾页

    if not all_rows:
        return None
    return pd.DataFrame(all_rows)


if __name__ == "__main__":
    # 简单自测
    print(f"API Key 配置: {'已配置' if is_available() else '未配置'}")
    if is_available():
        df = query_to_dataframe(
            "2026年2月22日以来主力资金净流入排名,市值50-200亿,非科创非st",
            max_pages=1,
        )
        if df is not None:
            print(f"✅ 成功获取 {len(df)} 只股票")
            print(df.head(3))
            print("列名:", list(df.columns)[:15])
        else:
            print("❌ 获取失败")
