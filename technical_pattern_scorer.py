#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技术形态评分模块

用于主力选股候选池的技术形态加分，不作为硬性过滤条件。
"""

from typing import Dict, List, Optional

import pandas as pd

from stock_data import StockDataFetcher


class TechnicalPatternScorer:
    """基于日线行情计算趋势、突破、量能等形态评分。"""

    def __init__(self, period: str = "6mo"):
        self.period = period
        self.fetcher = StockDataFetcher()

    def score_stock(self, symbol: str) -> Dict:
        """返回单只股票的形态评分结果。"""
        result = {
            "symbol": symbol,
            "pattern_score": 0,
            "pattern_level": "无数据",
            "pattern_tags": [],
            "pattern_summary": "未获取到足够行情数据",
            "pattern_details": {},
        }

        try:
            clean_symbol = self._clean_symbol(symbol)
            df = self.fetcher.get_stock_data(clean_symbol, period=self.period)
            if isinstance(df, dict) or df is None or df.empty or len(df) < 60:
                return result

            df = self.fetcher.calculate_technical_indicators(df.copy())
            if isinstance(df, dict) or df is None or df.empty:
                return result

            score, tags, details = self._calculate_pattern_score(df)
            result.update({
                "symbol": clean_symbol,
                "pattern_score": score,
                "pattern_level": self._score_level(score),
                "pattern_tags": tags,
                "pattern_summary": "、".join(tags) if tags else "形态信号不明显",
                "pattern_details": details,
            })
            return result
        except Exception as e:
            result["pattern_summary"] = f"形态评分失败: {e}"
            return result

    def score_dataframe(self, df: pd.DataFrame, code_col: str = "股票代码") -> pd.DataFrame:
        """为候选股票 DataFrame 增加形态评分字段。"""
        if df is None or df.empty or code_col not in df.columns:
            return df

        enriched_df = df.copy()
        scores: List[Optional[int]] = []
        levels: List[str] = []
        summaries: List[str] = []
        tags_list: List[str] = []

        for _, row in enriched_df.iterrows():
            score_result = self.score_stock(str(row.get(code_col, "")))
            scores.append(score_result.get("pattern_score"))
            levels.append(score_result.get("pattern_level", "无数据"))
            summaries.append(score_result.get("pattern_summary", ""))
            tags_list.append("、".join(score_result.get("pattern_tags", [])))

        enriched_df["形态评分"] = scores
        enriched_df["形态等级"] = levels
        enriched_df["形态标签"] = tags_list
        enriched_df["形态摘要"] = summaries
        return enriched_df

    def _calculate_pattern_score(self, df: pd.DataFrame) -> tuple:
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        close = float(latest["Close"])
        prev_close = float(prev["Close"])
        score = 0
        tags: List[str] = []
        details = {}

        ma5 = latest.get("MA5")
        ma10 = latest.get("MA10")
        ma20 = latest.get("MA20")
        ma60 = latest.get("MA60")

        if pd.notna(ma5) and pd.notna(ma10) and pd.notna(ma20) and ma5 > ma10 > ma20:
            score += 18
            tags.append("短期均线多头")

        if pd.notna(ma20) and pd.notna(ma60) and close > ma20 > ma60:
            score += 14
            tags.append("中期趋势向上")

        high_20 = df["Close"].iloc[-21:-1].max()
        high_60 = df["Close"].iloc[-61:-1].max()
        if pd.notna(high_20) and close > high_20:
            score += 18
            tags.append("突破20日高点")
        if pd.notna(high_60) and close > high_60:
            score += 12
            tags.append("突破60日高点")

        vol_ratio = latest.get("Volume_ratio")
        if pd.notna(vol_ratio) and vol_ratio >= 1.5:
            score += 14
            tags.append("明显放量")
        elif pd.notna(vol_ratio) and vol_ratio >= 1.2:
            score += 8
            tags.append("温和放量")

        macd = latest.get("MACD")
        macd_signal = latest.get("MACD_signal")
        macd_hist = latest.get("MACD_histogram")
        prev_hist = prev.get("MACD_histogram")
        if pd.notna(macd) and pd.notna(macd_signal) and macd > macd_signal:
            score += 8
            tags.append("MACD偏强")
        if pd.notna(macd_hist) and pd.notna(prev_hist) and macd_hist > prev_hist:
            score += 6
            tags.append("MACD动能改善")

        if pd.notna(ma20):
            distance_ma20 = abs(close - ma20) / ma20
            if distance_ma20 <= 0.03 and close >= ma20 and close > prev_close:
                score += 10
                tags.append("回踩MA20企稳")
            details["距离MA20"] = self._round_value(distance_ma20 * 100)

        rsi = latest.get("RSI")
        if pd.notna(rsi):
            if 45 <= rsi <= 70:
                score += 8
                tags.append("RSI健康")
            elif rsi > 80:
                score -= 8
                tags.append("RSI过热")

        details.update({
            "收盘价": round(close, 2),
            "MA5": self._round_value(ma5),
            "MA10": self._round_value(ma10),
            "MA20": self._round_value(ma20),
            "MA60": self._round_value(ma60),
            "量比": self._round_value(vol_ratio),
            "RSI": self._round_value(rsi),
        })

        return max(0, min(100, int(score))), tags, details

    def _score_level(self, score: int) -> str:
        if score >= 75:
            return "强势形态"
        if score >= 55:
            return "形态良好"
        if score >= 35:
            return "形态一般"
        if score > 0:
            return "弱信号"
        return "无明显形态"

    def _clean_symbol(self, symbol: str) -> str:
        if "." in symbol:
            return symbol.split(".")[0]
        return symbol.strip()

    def _round_value(self, value):
        if pd.isna(value):
            return None
        try:
            return round(float(value), 2)
        except Exception:
            return value
