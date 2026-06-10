#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票名称 → 代码 自动解析模块。

支持：
- 6位纯数字直接当代码用
- 5位纯数字当港股代码用
- 纯英文字母当美股代码用
- 中文名称通过 Tushare / Akshare 模糊搜索匹配代码
"""
from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple

from dotenv import load_dotenv
load_dotenv()

# 缓存全量股票列表（进程生命周期内只拉一次）
_stock_list_cache: Optional[list] = None


def resolve_stock_input(text: str) -> Tuple[str, str]:
    """将用户输入解析为 (代码, 显示名称)。

    Returns:
        (symbol, display_name)
        - 如果能解析，返回 ("600509", "天富能源")
        - 如果已经是代码，返回 ("600509", "600509")
        - 如果无法解析，返回 (原文, 原文)
    """
    text = text.strip()
    if not text:
        return (text, text)

    # 1. 纯6位数字 → A股代码
    if re.fullmatch(r'\d{6}', text):
        return (text, text)

    # 2. 纯5位数字 → 港股代码
    if re.fullmatch(r'\d{5}', text):
        return (text, text)

    # 3. 纯英文字母（1-5位）→ 美股代码
    if re.fullmatch(r'[A-Za-z]{1,5}', text):
        return (text.upper(), text.upper())

    # 4. 包含中文字符 → 当作股票名称搜索
    if _contains_chinese(text):
        result = search_stock_by_name(text)
        if result:
            return result  # (code, name)
        # 找不到就原样返回
        return (text, text)

    # 5. 其它格式原样返回
    return (text, text)


def resolve_stock_list(inputs: List[str]) -> List[Tuple[str, str]]:
    """批量解析股票输入。"""
    return [resolve_stock_input(s) for s in inputs]


def search_stock_by_name(name: str) -> Optional[Tuple[str, str]]:
    """通过股票名称搜索代码。

    Returns:
        (code, name) 或 None
    """
    stock_list = _get_stock_list()
    if not stock_list:
        return None

    # 精确匹配
    for code, sname in stock_list:
        if sname == name:
            return (code, sname)

    # 包含匹配
    candidates = []
    for code, sname in stock_list:
        if name in sname or sname in name:
            candidates.append((code, sname))

    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        # 优先精确长度匹配
        for code, sname in candidates:
            if sname == name:
                return (code, sname)
        # 返回第一个
        return candidates[0]

    return None


def search_stock_candidates(name: str, max_results: int = 10) -> List[Tuple[str, str]]:
    """模糊搜索股票，返回多个候选。"""
    stock_list = _get_stock_list()
    if not stock_list:
        return []

    candidates = []
    for code, sname in stock_list:
        if name in sname or sname in name:
            candidates.append((code, sname))
        if len(candidates) >= max_results:
            break
    return candidates


def _get_stock_list() -> list:
    """获取全量A股列表 (代码, 名称)，带缓存。"""
    global _stock_list_cache
    if _stock_list_cache is not None:
        return _stock_list_cache

    stock_list = []

    # 方案1：Tushare
    stock_list = _load_from_tushare()

    # 方案2：Akshare 备用
    if not stock_list:
        stock_list = _load_from_akshare()

    if stock_list:
        _stock_list_cache = stock_list
        print(f"[股票名称解析] ✅ 已加载 {len(stock_list)} 只股票映射")
    else:
        print("[股票名称解析] ⚠️ 无法加载股票列表，名称搜索不可用")
        _stock_list_cache = []

    return _stock_list_cache


def _load_from_tushare() -> list:
    """从 Tushare 加载股票列表。"""
    try:
        token = os.getenv('TUSHARE_TOKEN', '')
        if not token:
            return []
        import tushare as ts
        ts.set_token(token)
        pro = ts.pro_api()
        df = pro.stock_basic(exchange='', list_status='L', fields='symbol,name')
        if df is not None and not df.empty:
            return list(zip(df['symbol'].tolist(), df['name'].tolist()))
    except Exception as e:
        print(f"[股票名称解析] Tushare加载失败: {e}")
    return []


def _load_from_akshare() -> list:
    """从 Akshare 加载股票列表。"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            return list(zip(df['代码'].tolist(), df['名称'].tolist()))
    except Exception as e:
        print(f"[股票名称解析] Akshare加载失败: {e}")
    return []


def _contains_chinese(text: str) -> bool:
    """判断是否包含中文字符。"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))
