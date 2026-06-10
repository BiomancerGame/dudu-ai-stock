#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票形态识别模块 — 纯 Python 实现，无额外依赖。

识别两大类形态：
1. K线组合形态（Candlestick Patterns）：锤子线、吞没、十字星、晨星/暮星等
2. 图表形态（Chart Patterns）：双顶/双底、头肩、三角形收敛、支撑/阻力位等

用法:
    from pattern_recognition import PatternRecognizer
    recognizer = PatternRecognizer()
    result = recognizer.analyze("000001")
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from stock_data import stock_data_fetcher


class PatternRecognizer:
    """股票形态识别器。"""

    def __init__(self, period: str = "6mo"):
        self.period = period
        self.fetcher = stock_data_fetcher

    def analyze(self, symbol: str) -> Dict:
        """对一只股票进行完整形态分析，返回结构化结果。"""
        result = {
            "symbol": symbol,
            "candlestick_patterns": [],
            "chart_patterns": [],
            "support_resistance": {},
            "trend_info": {},
            "pattern_score": 0,
            "summary": "未获取到足够行情数据",
        }
        try:
            df = self.fetcher.get_stock_data(symbol, period=self.period)
            if isinstance(df, dict) or df is None or df.empty or len(df) < 60:
                return result

            df = self.fetcher.calculate_technical_indicators(df.copy())
            if isinstance(df, dict) or df is None or df.empty:
                return result

            # 1. K线组合形态
            candle_patterns = self._detect_candlestick_patterns(df)
            result["candlestick_patterns"] = candle_patterns

            # 2. 图表形态
            chart_patterns = self._detect_chart_patterns(df)
            result["chart_patterns"] = chart_patterns

            # 3. 支撑/阻力位
            sr = self._find_support_resistance(df)
            result["support_resistance"] = sr

            # 4. 趋势信息
            trend = self._analyze_trend(df)
            result["trend_info"] = trend

            # 5. 综合评分
            score = self._calculate_score(candle_patterns, chart_patterns, trend)
            result["pattern_score"] = score

            # 6. 摘要
            result["summary"] = self._build_summary(
                candle_patterns, chart_patterns, sr, trend, score
            )

            return result
        except Exception as e:
            result["summary"] = f"形态分析失败: {e}"
            return result

    # ==================== K线组合形态 ====================

    def _detect_candlestick_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """检测最近 5 根 K 线中的经典形态。"""
        patterns: List[Dict] = []
        if len(df) < 5:
            return patterns

        recent = df.iloc[-5:].copy()
        o = recent["Open"].values
        h = recent["High"].values
        l = recent["Low"].values  # noqa: E741
        c = recent["Close"].values

        # --- 单根 K 线形态（最后 1 根）---
        body = abs(c[-1] - o[-1])
        upper_shadow = h[-1] - max(c[-1], o[-1])
        lower_shadow = min(c[-1], o[-1]) - l[-1]
        total_range = h[-1] - l[-1]

        if total_range > 0:
            body_ratio = body / total_range

            # 十字星 Doji
            if body_ratio < 0.1:
                patterns.append({
                    "name": "十字星",
                    "name_en": "Doji",
                    "type": "neutral",
                    "signal": "趋势可能反转，需结合前后K线确认",
                    "strength": 1,
                })

            # 锤子线 Hammer（下影线长、实体小、出现在下跌后）
            if (lower_shadow > body * 2
                    and upper_shadow < body * 0.5
                    and body_ratio < 0.35):
                # 判断是否在下跌趋势中
                if c[-1] < c[-3]:
                    patterns.append({
                        "name": "锤子线",
                        "name_en": "Hammer",
                        "type": "bullish",
                        "signal": "底部反转信号，多方开始抵抗",
                        "strength": 2,
                    })

            # 射击之星 Shooting Star（上影线长、出现在上涨后）
            if (upper_shadow > body * 2
                    and lower_shadow < body * 0.5
                    and body_ratio < 0.35):
                if c[-1] > c[-3]:
                    patterns.append({
                        "name": "射击之星",
                        "name_en": "Shooting Star",
                        "type": "bearish",
                        "signal": "顶部反转信号，上方抛压沉重",
                        "strength": 2,
                    })

        # --- 双根 K 线形态（最后 2 根）---
        body_prev = abs(c[-2] - o[-2])
        body_curr = abs(c[-1] - o[-1])

        # 看涨吞没 Bullish Engulfing
        if (o[-2] > c[-2]  # 前一根阴线
                and c[-1] > o[-1]  # 当前阳线
                and c[-1] > o[-2]  # 当前收盘 > 前收开盘
                and o[-1] < c[-2]  # 当前开盘 < 前收收盘
                and body_curr > body_prev * 1.2):
            patterns.append({
                "name": "看涨吞没",
                "name_en": "Bullish Engulfing",
                "type": "bullish",
                "signal": "强烈看涨信号，多方完全吞没空方",
                "strength": 3,
            })

        # 看跌吞没 Bearish Engulfing
        if (c[-2] > o[-2]  # 前一根阳线
                and o[-1] > c[-1]  # 当前阴线
                and o[-1] > c[-2]  # 当前开盘 > 前收收盘
                and c[-1] < o[-2]  # 当前收盘 < 前收开盘
                and body_curr > body_prev * 1.2):
            patterns.append({
                "name": "看跌吞没",
                "name_en": "Bearish Engulfing",
                "type": "bearish",
                "signal": "强烈看跌信号，空方完全压制多方",
                "strength": 3,
            })

        # 看涨孕线 Bullish Harami
        if (o[-2] > c[-2]  # 前阴线
                and c[-1] > o[-1]  # 当前阳线
                and o[-1] > c[-2] and c[-1] < o[-2]  # 当前在前一根实体内
                and body_curr < body_prev * 0.5):
            patterns.append({
                "name": "看涨孕线",
                "name_en": "Bullish Harami",
                "type": "bullish",
                "signal": "下跌趋势中出现犹豫，可能反转",
                "strength": 2,
            })

        # 看跌孕线 Bearish Harami
        if (c[-2] > o[-2]  # 前阳线
                and o[-1] > c[-1]  # 当前阴线
                and c[-1] > o[-2] and o[-1] < c[-2]  # 当前在前一根实体内
                and body_curr < body_prev * 0.5):
            patterns.append({
                "name": "看跌孕线",
                "name_en": "Bearish Harami",
                "type": "bearish",
                "signal": "上涨趋势中出现犹豫，可能反转",
                "strength": 2,
            })

        # --- 三根 K 线形态 ---
        # 晨星 Morning Star
        if (len(df) >= 3
                and o[-3] > c[-3]  # 第1根阴线
                and abs(c[-2] - o[-2]) < abs(c[-3] - o[-3]) * 0.3  # 第2根小实体
                and c[-1] > o[-1]  # 第3根阳线
                and c[-1] > (o[-3] + c[-3]) / 2):  # 收盘超过第1根实体中点
            patterns.append({
                "name": "晨星",
                "name_en": "Morning Star",
                "type": "bullish",
                "signal": "经典底部反转形态，可靠性较高",
                "strength": 3,
            })

        # 暮星 Evening Star
        if (len(df) >= 3
                and c[-3] > o[-3]  # 第1根阳线
                and abs(c[-2] - o[-2]) < abs(c[-3] - o[-3]) * 0.3  # 第2根小实体
                and o[-1] > c[-1]  # 第3根阴线
                and c[-1] < (o[-3] + c[-3]) / 2):  # 收盘低于第1根实体中点
            patterns.append({
                "name": "暮星",
                "name_en": "Evening Star",
                "type": "bearish",
                "signal": "经典顶部反转形态，可靠性较高",
                "strength": 3,
            })

        # 三白兵 Three White Soldiers
        if (c[-3] > o[-3] and c[-2] > o[-2] and c[-1] > o[-1]
                and c[-2] > c[-3] and c[-1] > c[-2]
                and o[-2] > o[-3] and o[-1] > o[-2]):
            patterns.append({
                "name": "三白兵",
                "name_en": "Three White Soldiers",
                "type": "bullish",
                "signal": "连续三根阳线递增，强势上攻信号",
                "strength": 3,
            })

        # 三黑鸦 Three Black Crows
        if (o[-3] > c[-3] and o[-2] > c[-2] and o[-1] > c[-1]
                and c[-2] < c[-3] and c[-1] < c[-2]
                and o[-2] < o[-3] and o[-1] < o[-2]):
            patterns.append({
                "name": "三黑鸦",
                "name_en": "Three Black Crows",
                "type": "bearish",
                "signal": "连续三根阴线递减，强势下跌信号",
                "strength": 3,
            })

        return patterns

    # ==================== 图表形态 ====================

    def _detect_chart_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """检测近期的图表形态。"""
        patterns: List[Dict] = []
        if len(df) < 30:
            return patterns

        close = df["Close"].values.astype(float)

        # W底（双重底）
        w = self._detect_double_bottom(close)
        if w:
            patterns.append(w)

        # M头（双重顶）
        m = self._detect_double_top(close)
        if m:
            patterns.append(m)

        # 头肩底
        hs_bottom = self._detect_head_shoulders_bottom(close)
        if hs_bottom:
            patterns.append(hs_bottom)

        # 头肩顶
        hs_top = self._detect_head_shoulders_top(close)
        if hs_top:
            patterns.append(hs_top)

        # 三角形收敛
        tri = self._detect_triangle(df)
        if tri:
            patterns.append(tri)

        # 箱体震荡
        box = self._detect_box_range(close)
        if box:
            patterns.append(box)

        return patterns

    def _find_local_extrema(self, data: np.ndarray, order: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        """找局部极值点索引。"""
        maxima = []
        minima = []
        for i in range(order, len(data) - order):
            if all(data[i] >= data[i - j] for j in range(1, order + 1)) and \
               all(data[i] >= data[i + j] for j in range(1, order + 1)):
                maxima.append(i)
            if all(data[i] <= data[i - j] for j in range(1, order + 1)) and \
               all(data[i] <= data[i + j] for j in range(1, order + 1)):
                minima.append(i)
        return np.array(maxima), np.array(minima)

    def _detect_double_bottom(self, close: np.ndarray) -> Dict | None:
        """检测W底（双重底）— 最近60根K线。"""
        window = close[-60:]
        _, minima = self._find_local_extrema(window, order=5)

        if len(minima) < 2:
            return None

        # 取最近两个谷底
        b1, b2 = minima[-2], minima[-1]
        v1, v2 = window[b1], window[b2]

        # 两个底部价格相近（误差 < 3%）
        if abs(v1 - v2) / max(v1, v2) > 0.03:
            return None
        # 两底间距 >= 10 根 K 线
        if b2 - b1 < 10:
            return None
        # 颈线（两底之间的最高点）
        neckline = max(window[b1:b2 + 1])
        # 当前价格需在颈线附近或之上
        current = window[-1]
        if current < neckline * 0.97:
            return None

        breakthrough = current > neckline
        return {
            "name": "W底（双重底）",
            "name_en": "Double Bottom",
            "type": "bullish",
            "signal": f"底部价位约{v1:.2f}，颈线位{neckline:.2f}，" +
                      ("已突破颈线，看涨确认" if breakthrough else "接近颈线，等待突破确认"),
            "strength": 3 if breakthrough else 2,
            "key_levels": {"底部": round(float(v1), 2), "颈线": round(float(neckline), 2)},
        }

    def _detect_double_top(self, close: np.ndarray) -> Dict | None:
        """检测M头（双重顶）— 最近60根K线。"""
        window = close[-60:]
        maxima, _ = self._find_local_extrema(window, order=5)

        if len(maxima) < 2:
            return None

        t1, t2 = maxima[-2], maxima[-1]
        v1, v2 = window[t1], window[t2]

        if abs(v1 - v2) / max(v1, v2) > 0.03:
            return None
        if t2 - t1 < 10:
            return None

        neckline = min(window[t1:t2 + 1])
        current = window[-1]
        if current > neckline * 1.03:
            return None

        breakdown = current < neckline
        return {
            "name": "M头（双重顶）",
            "name_en": "Double Top",
            "type": "bearish",
            "signal": f"顶部价位约{v1:.2f}，颈线位{neckline:.2f}，" +
                      ("已跌破颈线，看跌确认" if breakdown else "接近颈线，警惕破位"),
            "strength": 3 if breakdown else 2,
            "key_levels": {"顶部": round(float(v1), 2), "颈线": round(float(neckline), 2)},
        }

    def _detect_head_shoulders_bottom(self, close: np.ndarray) -> Dict | None:
        """检测头肩底。"""
        window = close[-80:] if len(close) >= 80 else close
        _, minima = self._find_local_extrema(window, order=5)

        if len(minima) < 3:
            return None

        ls, head, rs = minima[-3], minima[-2], minima[-1]
        v_ls, v_head, v_rs = window[ls], window[head], window[rs]

        # 头部最低，两肩高于头部且相近
        if not (v_head < v_ls and v_head < v_rs):
            return None
        if abs(v_ls - v_rs) / max(v_ls, v_rs) > 0.05:
            return None

        neckline = max(window[ls:rs + 1])
        current = window[-1]
        breakthrough = current > neckline

        return {
            "name": "头肩底",
            "name_en": "Head and Shoulders Bottom",
            "type": "bullish",
            "signal": f"左肩{v_ls:.2f}，头部{v_head:.2f}，右肩{v_rs:.2f}，颈线{neckline:.2f}，" +
                      ("已突破颈线，反转确认" if breakthrough else "等待突破颈线确认"),
            "strength": 3 if breakthrough else 2,
            "key_levels": {"头部": round(float(v_head), 2), "颈线": round(float(neckline), 2)},
        }

    def _detect_head_shoulders_top(self, close: np.ndarray) -> Dict | None:
        """检测头肩顶。"""
        window = close[-80:] if len(close) >= 80 else close
        maxima, _ = self._find_local_extrema(window, order=5)

        if len(maxima) < 3:
            return None

        ls, head, rs = maxima[-3], maxima[-2], maxima[-1]
        v_ls, v_head, v_rs = window[ls], window[head], window[rs]

        if not (v_head > v_ls and v_head > v_rs):
            return None
        if abs(v_ls - v_rs) / max(v_ls, v_rs) > 0.05:
            return None

        neckline = min(window[ls:rs + 1])
        current = window[-1]
        breakdown = current < neckline

        return {
            "name": "头肩顶",
            "name_en": "Head and Shoulders Top",
            "type": "bearish",
            "signal": f"左肩{v_ls:.2f}，头部{v_head:.2f}，右肩{v_rs:.2f}，颈线{neckline:.2f}，" +
                      ("已跌破颈线，反转确认" if breakdown else "警惕跌破颈线"),
            "strength": 3 if breakdown else 2,
            "key_levels": {"头部": round(float(v_head), 2), "颈线": round(float(neckline), 2)},
        }

    def _detect_triangle(self, df: pd.DataFrame) -> Dict | None:
        """检测三角形收敛（近30根K线高点递降、低点递升）。"""
        if len(df) < 30:
            return None

        window = df.iloc[-30:]
        highs = window["High"].values.astype(float)
        lows = window["Low"].values.astype(float)

        # 分成3段比较
        seg = len(highs) // 3
        h_segments = [highs[i * seg:(i + 1) * seg].max() for i in range(3)]
        l_segments = [lows[i * seg:(i + 1) * seg].min() for i in range(3)]

        highs_descending = h_segments[0] > h_segments[1] > h_segments[2]
        lows_ascending = l_segments[0] < l_segments[1] < l_segments[2]

        if highs_descending and lows_ascending:
            # 对称三角形
            return {
                "name": "三角形收敛",
                "name_en": "Symmetrical Triangle",
                "type": "neutral",
                "signal": f"高点递降({h_segments[0]:.2f}→{h_segments[2]:.2f})，"
                          f"低点递升({l_segments[0]:.2f}→{l_segments[2]:.2f})，"
                          "波动收窄，即将选择方向突破",
                "strength": 2,
                "key_levels": {
                    "上轨": round(float(h_segments[2]), 2),
                    "下轨": round(float(l_segments[2]), 2),
                },
            }
        elif highs_descending and not lows_ascending:
            # 下降三角形
            support_level = min(l_segments)
            return {
                "name": "下降三角形",
                "name_en": "Descending Triangle",
                "type": "bearish",
                "signal": f"高点持续下移，支撑位{support_level:.2f}，偏空形态",
                "strength": 2,
                "key_levels": {"支撑": round(float(support_level), 2)},
            }
        elif not highs_descending and lows_ascending:
            # 上升三角形
            resistance_level = max(h_segments)
            return {
                "name": "上升三角形",
                "name_en": "Ascending Triangle",
                "type": "bullish",
                "signal": f"低点持续上移，压力位{resistance_level:.2f}，偏多形态",
                "strength": 2,
                "key_levels": {"压力": round(float(resistance_level), 2)},
            }

        return None

    def _detect_box_range(self, close: np.ndarray) -> Dict | None:
        """检测箱体震荡（近30根K线振幅 < 10%）。"""
        window = close[-30:]
        high = window.max()
        low = window.min()
        amplitude = (high - low) / low

        if amplitude < 0.10:
            current = window[-1]
            mid = (high + low) / 2
            position = "上半区" if current > mid else "下半区"
            return {
                "name": "箱体震荡",
                "name_en": "Box Range",
                "type": "neutral",
                "signal": f"近30日在{low:.2f}-{high:.2f}区间震荡（振幅{amplitude * 100:.1f}%），"
                          f"当前处于{position}",
                "strength": 1,
                "key_levels": {
                    "箱顶": round(float(high), 2),
                    "箱底": round(float(low), 2),
                },
            }
        return None

    # ==================== 支撑/阻力 ====================

    def _find_support_resistance(self, df: pd.DataFrame) -> Dict:
        """基于近期极值计算关键支撑/阻力位。"""
        close = df["Close"].values.astype(float)
        maxima, minima = self._find_local_extrema(close[-60:], order=5)

        current_price = float(close[-1])
        supports = sorted(set(round(float(close[-60:][i]), 2) for i in minima))
        resistances = sorted(set(round(float(close[-60:][i]), 2) for i in maxima))

        # 过滤：支撑位 < 当前价，阻力位 > 当前价
        supports = [s for s in supports if s < current_price][-3:]  # 最近3个
        resistances = [r for r in resistances if r > current_price][:3]  # 最近3个

        # MA 支撑/阻力
        latest = df.iloc[-1]
        ma_levels = {}
        for ma_name in ["MA5", "MA10", "MA20", "MA60"]:
            val = latest.get(ma_name)
            if pd.notna(val):
                ma_levels[ma_name] = round(float(val), 2)

        return {
            "current_price": round(current_price, 2),
            "supports": supports,
            "resistances": resistances,
            "ma_levels": ma_levels,
        }

    # ==================== 趋势分析 ====================

    def _analyze_trend(self, df: pd.DataFrame) -> Dict:
        """分析趋势方向和强度。"""
        close = df["Close"].values.astype(float)
        latest = df.iloc[-1]

        # 短/中/长期趋势
        def _trend_direction(data, n):
            if len(data) < n:
                return "数据不足"
            change = (data[-1] - data[-n]) / data[-n] * 100
            if change > 5:
                return "上涨"
            elif change < -5:
                return "下跌"
            return "横盘"

        # 均线排列
        ma5 = latest.get("MA5")
        ma10 = latest.get("MA10")
        ma20 = latest.get("MA20")
        ma60 = latest.get("MA60")

        ma_arrangement = "无法判断"
        if pd.notna(ma5) and pd.notna(ma10) and pd.notna(ma20):
            if ma5 > ma10 > ma20:
                ma_arrangement = "多头排列"
            elif ma5 < ma10 < ma20:
                ma_arrangement = "空头排列"
            else:
                ma_arrangement = "交叉缠绕"

        # 价格与均线关系
        price_vs_ma = []
        current = float(close[-1])
        for name, val in [("MA5", ma5), ("MA10", ma10), ("MA20", ma20), ("MA60", ma60)]:
            if pd.notna(val):
                val_f = float(val)
                if current > val_f:
                    price_vs_ma.append(f"站上{name}")
                else:
                    price_vs_ma.append(f"跌破{name}")

        return {
            "short_term": _trend_direction(close, 5),
            "mid_term": _trend_direction(close, 20),
            "long_term": _trend_direction(close, 60),
            "ma_arrangement": ma_arrangement,
            "price_vs_ma": price_vs_ma,
            "recent_change_5d": round(float((close[-1] - close[-6]) / close[-6] * 100), 2) if len(close) > 5 else 0,
            "recent_change_20d": round(float((close[-1] - close[-21]) / close[-21] * 100), 2) if len(close) > 20 else 0,
        }

    # ==================== 评分 ====================

    def _calculate_score(self, candle: List, chart: List, trend: Dict) -> int:
        """综合形态评分（0-100）。"""
        score = 50  # 基准分

        # K线形态加/减分
        for p in candle:
            s = p.get("strength", 1)
            if p["type"] == "bullish":
                score += s * 5
            elif p["type"] == "bearish":
                score -= s * 5

        # 图表形态加/减分
        for p in chart:
            s = p.get("strength", 1)
            if p["type"] == "bullish":
                score += s * 6
            elif p["type"] == "bearish":
                score -= s * 6

        # 趋势加分
        if trend.get("ma_arrangement") == "多头排列":
            score += 10
        elif trend.get("ma_arrangement") == "空头排列":
            score -= 10

        return max(0, min(100, score))

    # ==================== 摘要 ====================

    def _build_summary(self, candle, chart, sr, trend, score) -> str:
        """生成简短中文摘要。"""
        parts = []

        # 趋势
        ma_arr = trend.get("ma_arrangement", "")
        if ma_arr:
            parts.append(f"均线{ma_arr}")

        # K线形态
        bullish_candles = [p["name"] for p in candle if p["type"] == "bullish"]
        bearish_candles = [p["name"] for p in candle if p["type"] == "bearish"]
        if bullish_candles:
            parts.append(f"看涨K线: {'、'.join(bullish_candles)}")
        if bearish_candles:
            parts.append(f"看跌K线: {'、'.join(bearish_candles)}")

        # 图表形态
        for p in chart:
            parts.append(p["name"])

        # 支撑阻力
        if sr.get("supports"):
            parts.append(f"支撑位: {sr['supports'][-1]}")
        if sr.get("resistances"):
            parts.append(f"阻力位: {sr['resistances'][0]}")

        # 评分
        if score >= 70:
            level = "强势形态"
        elif score >= 55:
            level = "偏多形态"
        elif score >= 45:
            level = "中性形态"
        elif score >= 30:
            level = "偏空形态"
        else:
            level = "弱势形态"
        parts.append(f"综合评分{score}分（{level}）")

        return "；".join(parts) if parts else "无明显形态信号"


def format_pattern_for_ai(result: Dict) -> str:
    """将形态识别结果格式化为 AI 可读的文本。"""
    lines = []

    lines.append(f"【形态综合评分】{result.get('pattern_score', 0)}/100")
    lines.append(f"【形态摘要】{result.get('summary', '无')}")
    lines.append("")

    # K线形态
    candles = result.get("candlestick_patterns", [])
    if candles:
        lines.append("【K线组合形态】")
        for p in candles:
            direction = {"bullish": "看涨", "bearish": "看跌", "neutral": "中性"}.get(p["type"], "")
            lines.append(f"  - {p['name']}({p['name_en']}) [{direction}] 强度:{p['strength']}/3")
            lines.append(f"    信号: {p['signal']}")
    else:
        lines.append("【K线组合形态】近期无明显K线形态")

    lines.append("")

    # 图表形态
    charts = result.get("chart_patterns", [])
    if charts:
        lines.append("【图表形态】")
        for p in charts:
            direction = {"bullish": "看涨", "bearish": "看跌", "neutral": "中性"}.get(p["type"], "")
            lines.append(f"  - {p['name']}({p['name_en']}) [{direction}] 强度:{p['strength']}/3")
            lines.append(f"    信号: {p['signal']}")
            if p.get("key_levels"):
                levels_str = ", ".join(f"{k}:{v}" for k, v in p["key_levels"].items())
                lines.append(f"    关键价位: {levels_str}")
    else:
        lines.append("【图表形态】近期无明显图表形态")

    lines.append("")

    # 支撑/阻力
    sr = result.get("support_resistance", {})
    if sr:
        lines.append(f"【当前价格】{sr.get('current_price', 'N/A')}")
        lines.append(f"【支撑位】{sr.get('supports', [])}")
        lines.append(f"【阻力位】{sr.get('resistances', [])}")
        ma = sr.get("ma_levels", {})
        if ma:
            ma_str = ", ".join(f"{k}:{v}" for k, v in ma.items())
            lines.append(f"【均线位置】{ma_str}")

    lines.append("")

    # 趋势
    trend = result.get("trend_info", {})
    if trend:
        lines.append(f"【趋势方向】短期:{trend.get('short_term','N/A')} | "
                      f"中期:{trend.get('mid_term','N/A')} | 长期:{trend.get('long_term','N/A')}")
        lines.append(f"【均线排列】{trend.get('ma_arrangement', 'N/A')}")
        lines.append(f"【价格位置】{', '.join(trend.get('price_vs_ma', []))}")
        lines.append(f"【近5日涨幅】{trend.get('recent_change_5d', 0)}%")
        lines.append(f"【近20日涨幅】{trend.get('recent_change_20d', 0)}%")

    return "\n".join(lines)
