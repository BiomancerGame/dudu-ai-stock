#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CANSLIM / RPS 选股分析模块 — 适配A股市场。

基于威廉·欧奈尔（William O'Neil）的 CANSLIM 选股法则，
计算7大组件评分并生成综合得分。

组件:
  C - Current Earnings    当季盈利增长
  A - Annual Growth       年度增长
  N - New Highs           新高/新突破
  S - Supply/Demand       供需关系（量能）
  L - Leadership/RS       相对强度排名（RPS）
  I - Institutional       机构持仓
  M - Market Direction    市场方向

用法:
    from canslim_analyzer import CANSLIMAnalyzer
    analyzer = CANSLIMAnalyzer()
    result = analyzer.analyze("000001")
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from stock_data import stock_data_fetcher


# 组件权重（欧奈尔原始权重）
COMPONENT_WEIGHTS = {
    "C": 0.15,
    "A": 0.20,
    "N": 0.15,
    "S": 0.15,
    "L": 0.20,
    "I": 0.10,
    "M": 0.05,
}

# 评级区间
RATING_BANDS = [
    (90, 100, "Exceptional+", "极优", "所有组件近乎满分，强力买入信号"),
    (80, 89, "Exceptional", "优秀", "基本面与动量俱佳，可积极建仓"),
    (70, 79, "Strong", "强势", "整体达标，可标准仓位介入"),
    (60, 69, "Above Average", "中上", "多数组件合格，回调时可关注"),
    (50, 59, "Average", "一般", "部分组件偏弱，暂列观察"),
    (0, 49, "Below Average", "偏弱", "不符合CANSLIM标准，回避"),
]


class CANSLIMAnalyzer:
    """CANSLIM 选股分析器，适配A股。"""

    def __init__(self, period: str = "1y"):
        self.period = period
        self.fetcher = stock_data_fetcher

    def analyze(self, symbol: str, financial_data: Dict = None,
                fund_flow_data: Dict = None) -> Dict:
        """对一只股票进行 CANSLIM 7维度评分分析。"""
        result = {
            "symbol": symbol,
            "components": {},
            "composite_score": 0,
            "rating": "",
            "rating_cn": "",
            "rating_desc": "",
            "rps_rank": 0,
            "details": {},
            "summary": "",
        }

        try:
            # 获取股票历史行情
            stock_data = self.fetcher.get_stock_data(symbol, self.period)
            if stock_data is None or isinstance(stock_data, dict):
                result["summary"] = "无法获取历史行情数据"
                return result

            df = stock_data.copy()
            if not isinstance(df.index, pd.DatetimeIndex):
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
                    df.set_index('Date', inplace=True)

            # 获取大盘数据用于 RPS 计算
            market_df = self._get_market_index_data()

            # 计算各组件
            c_score, c_detail = self._calc_c_component(symbol, financial_data)
            a_score, a_detail = self._calc_a_component(symbol, financial_data)
            n_score, n_detail = self._calc_n_component(df)
            s_score, s_detail = self._calc_s_component(df)
            l_score, l_detail = self._calc_l_component(df, market_df)
            i_score, i_detail = self._calc_i_component(symbol, fund_flow_data)
            m_score, m_detail = self._calc_m_component(market_df)

            components = {
                "C": {"score": c_score, "name": "当季盈利", "detail": c_detail},
                "A": {"score": a_score, "name": "年度增长", "detail": a_detail},
                "N": {"score": n_score, "name": "新高突破", "detail": n_detail},
                "S": {"score": s_score, "name": "供需关系", "detail": s_detail},
                "L": {"score": l_score, "name": "相对强度(RPS)", "detail": l_detail},
                "I": {"score": i_score, "name": "机构持仓", "detail": i_detail},
                "M": {"score": m_score, "name": "市场方向", "detail": m_detail},
            }

            # 计算综合得分
            composite = sum(
                components[k]["score"] * COMPONENT_WEIGHTS[k]
                for k in COMPONENT_WEIGHTS
            )
            composite = round(composite, 1)

            # 确定评级
            rating, rating_cn, rating_desc = self._get_rating(composite)

            # RPS 排名（从 L 组件提取）
            rps_rank = l_detail.get("rps_rank", 0)

            result.update({
                "components": components,
                "composite_score": composite,
                "rating": rating,
                "rating_cn": rating_cn,
                "rating_desc": rating_desc,
                "rps_rank": rps_rank,
                "details": {
                    "weights": COMPONENT_WEIGHTS,
                    "bear_market_warning": m_score == 0,
                },
                "summary": f"CANSLIM综合评分: {composite}/100 ({rating_cn})",
            })

        except Exception as e:
            result["summary"] = f"CANSLIM分析异常: {str(e)}"
            import traceback
            traceback.print_exc()

        return result

    # ───────── C: Current Earnings ─────────

    def _calc_c_component(self, symbol: str, financial_data: Dict = None) -> Tuple[float, Dict]:
        """当季每股收益/营收增长评估。"""
        detail = {"eps_growth": None, "revenue_growth": None, "description": ""}

        try:
            if financial_data and financial_data.get("financial_ratios"):
                ratios = financial_data["financial_ratios"]
                # 尝试获取净利润同比增长
                profit_growth_str = ratios.get("净利润同比增长", "N/A")
                revenue_growth_str = ratios.get("营业收入同比增长", "N/A")

                profit_growth = self._parse_percent(profit_growth_str)
                revenue_growth = self._parse_percent(revenue_growth_str)

                detail["eps_growth"] = profit_growth
                detail["revenue_growth"] = revenue_growth

                if profit_growth is not None:
                    score = self._score_growth(profit_growth, thresholds=[50, 30, 18, 10, 0])
                    # 营收加速加分
                    if revenue_growth is not None and revenue_growth > 25:
                        score = min(100, score + 10)
                    detail["description"] = f"净利润同比增长{profit_growth:.1f}%，营收增长{revenue_growth if revenue_growth else 'N/A'}%"
                    return score, detail

            # 尝试从利润表计算
            if financial_data and financial_data.get("income_statement"):
                income = financial_data["income_statement"]
                if len(income) >= 2:
                    # 取最近两期比较
                    detail["description"] = "从利润表推算增长"
                    return 50, detail  # 默认中性

        except Exception as e:
            detail["description"] = f"计算异常: {e}"

        detail["description"] = "无财务增长数据，使用默认值"
        return 40, detail  # 无数据给保守分

    # ───────── A: Annual Growth ─────────

    def _calc_a_component(self, symbol: str, financial_data: Dict = None) -> Tuple[float, Dict]:
        """3年年度增长（EPS CAGR）评估。"""
        detail = {"cagr": None, "roe": None, "description": ""}

        try:
            if financial_data and financial_data.get("financial_ratios"):
                ratios = financial_data["financial_ratios"]
                roe_str = ratios.get("净资产收益率(ROE)", "N/A")
                roe = self._parse_percent(roe_str)
                detail["roe"] = roe

                profit_growth_str = ratios.get("净利润同比增长", "N/A")
                profit_growth = self._parse_percent(profit_growth_str)

                # 综合评估：ROE + 增速
                score = 40  # 基础分
                if roe is not None:
                    if roe >= 20:
                        score += 30
                    elif roe >= 15:
                        score += 20
                    elif roe >= 10:
                        score += 10

                if profit_growth is not None:
                    if profit_growth >= 30:
                        score += 30
                    elif profit_growth >= 20:
                        score += 20
                    elif profit_growth >= 10:
                        score += 10

                score = min(100, score)
                detail["description"] = f"ROE={roe if roe else 'N/A'}%，净利润增速={profit_growth if profit_growth else 'N/A'}%"
                return score, detail

        except Exception as e:
            detail["description"] = f"计算异常: {e}"

        detail["description"] = "无年度增长数据"
        return 40, detail

    # ───────── N: New Highs / Newness ─────────

    def _calc_n_component(self, df: pd.DataFrame) -> Tuple[float, Dict]:
        """距52周新高距离 + 突破确认。"""
        detail = {"distance_from_high": None, "breakout": False, "description": ""}

        try:
            if len(df) < 20:
                detail["description"] = "数据不足"
                return 30, detail

            close = df['Close'].values
            high_52w = df['High'].max()
            current_price = close[-1]

            # 距52周高点的距离
            distance = (high_52w - current_price) / high_52w * 100
            detail["distance_from_high"] = round(distance, 2)

            # 判断是否近期突破
            recent_high_20 = df['High'].iloc[-20:].max()
            prev_high_20 = df['High'].iloc[-40:-20].max() if len(df) >= 40 else df['High'].iloc[:-20].max()
            breakout = recent_high_20 > prev_high_20 and distance < 10

            # 放量突破加分
            vol_recent = df['Volume'].iloc[-5:].mean()
            vol_avg = df['Volume'].iloc[-60:].mean() if len(df) >= 60 else df['Volume'].mean()
            volume_confirm = vol_recent > vol_avg * 1.3

            detail["breakout"] = breakout
            detail["volume_confirm"] = volume_confirm

            # 评分
            if distance <= 5 and breakout and volume_confirm:
                score = 100
            elif distance <= 5 and breakout:
                score = 90
            elif distance <= 10 and breakout:
                score = 80
            elif distance <= 10:
                score = 70
            elif distance <= 15:
                score = 60
            elif distance <= 20:
                score = 50
            elif distance <= 30:
                score = 35
            else:
                score = 20

            status = "放量突破新高" if breakout and volume_confirm else (
                "突破前高" if breakout else f"距52周高点 {distance:.1f}%"
            )
            detail["description"] = status
            return score, detail

        except Exception as e:
            detail["description"] = f"计算异常: {e}"
            return 30, detail

    # ───────── S: Supply / Demand ─────────

    def _calc_s_component(self, df: pd.DataFrame) -> Tuple[float, Dict]:
        """量能供需分析（上涨日成交量 vs 下跌日成交量）。"""
        detail = {"up_down_ratio": None, "accumulation": False, "description": ""}

        try:
            lookback = min(60, len(df) - 1)
            if lookback < 10:
                detail["description"] = "数据不足"
                return 40, detail

            recent = df.iloc[-lookback:]
            close = recent['Close'].values
            volume = recent['Volume'].values

            # 计算涨跌日成交量
            changes = np.diff(close)
            up_vol = volume[1:][changes > 0].sum()
            down_vol = volume[1:][changes < 0].sum()

            if down_vol == 0:
                ratio = 3.0
            else:
                ratio = up_vol / down_vol

            detail["up_down_ratio"] = round(ratio, 2)
            detail["accumulation"] = ratio > 1.0

            # 换手率分析
            turnover_recent = None
            if 'turnover' in df.columns:
                turnover_recent = df['turnover'].iloc[-5:].mean()
                detail["avg_turnover_5d"] = round(turnover_recent, 2)

            # 评分
            if ratio >= 2.0:
                score = 100
            elif ratio >= 1.5:
                score = 80
            elif ratio >= 1.2:
                score = 65
            elif ratio >= 1.0:
                score = 50
            elif ratio >= 0.8:
                score = 35
            else:
                score = 20

            status = "强势吸筹" if ratio >= 1.5 else (
                "温和吸筹" if ratio >= 1.0 else "资金流出"
            )
            detail["description"] = f"量比(涨/跌)={ratio:.2f}，{status}"
            return score, detail

        except Exception as e:
            detail["description"] = f"计算异常: {e}"
            return 40, detail

    # ───────── L: Leadership / Relative Strength (RPS) ─────────

    def _calc_l_component(self, df: pd.DataFrame, market_df: pd.DataFrame = None) -> Tuple[float, Dict]:
        """相对强度排名（RPS）计算 — 多周期加权。"""
        detail = {"rps_rank": 0, "rel_3m": None, "rel_6m": None, "rel_12m": None, "description": ""}

        try:
            close = df['Close'].values
            if len(close) < 20:
                detail["description"] = "数据不足"
                return 30, detail

            # 计算个股多周期涨幅
            stock_returns = {}
            periods = {"3m": 63, "6m": 126, "12m": 252}
            for name, days in periods.items():
                if len(close) >= days:
                    stock_returns[name] = (close[-1] / close[-days] - 1) * 100
                elif len(close) >= days // 2:
                    # 用可用数据的比例估算
                    avail = len(close) - 1
                    stock_returns[name] = (close[-1] / close[0] - 1) * 100

            # 计算大盘多周期涨幅
            market_returns = {}
            if market_df is not None and len(market_df) > 0:
                m_close = market_df['Close'].values
                for name, days in periods.items():
                    if len(m_close) >= days:
                        market_returns[name] = (m_close[-1] / m_close[-days] - 1) * 100

            # 计算相对强度
            rel_returns = {}
            for name in stock_returns:
                stock_r = stock_returns[name]
                market_r = market_returns.get(name, 0)
                rel_returns[name] = stock_r - market_r

            detail["rel_3m"] = round(rel_returns.get("3m", 0), 2)
            detail["rel_6m"] = round(rel_returns.get("6m", 0), 2)
            detail["rel_12m"] = round(rel_returns.get("12m", 0), 2)
            detail["stock_returns"] = {k: round(v, 2) for k, v in stock_returns.items()}
            detail["market_returns"] = {k: round(v, 2) for k, v in market_returns.items()}

            # 加权 RPS
            # Weighted RS = 0.40 × rel_3m + 0.30 × rel_6m + 0.30 × rel_12m
            weights = {"3m": 0.40, "6m": 0.30, "12m": 0.30}
            available = {k: v for k, v in rel_returns.items() if k in weights}

            if available:
                total_w = sum(weights[k] for k in available)
                weighted_rs = sum(rel_returns[k] * weights[k] / total_w for k in available)
            else:
                weighted_rs = 0

            detail["weighted_rs"] = round(weighted_rs, 2)

            # 将 weighted_rs 映射到 1-99 RPS 排名
            # 经验公式：RS > 30% → 99，RS > 20% → 90，RS > 10% → 80 ...
            rps = self._rs_to_rank(weighted_rs)
            detail["rps_rank"] = rps

            # 评分
            if rps >= 90:
                score = 100
            elif rps >= 80:
                score = 85
            elif rps >= 70:
                score = 70
            elif rps >= 60:
                score = 55
            elif rps >= 50:
                score = 40
            else:
                score = max(20, rps * 0.4)

            detail["description"] = (
                f"RPS={rps}，加权RS={weighted_rs:.1f}% "
                f"(3m:{detail['rel_3m']:+.1f}% / 6m:{detail['rel_6m']:+.1f}% / 12m:{detail['rel_12m']:+.1f}%)"
            )
            return round(score), detail

        except Exception as e:
            detail["description"] = f"计算异常: {e}"
            return 30, detail

    # ───────── I: Institutional ─────────

    def _calc_i_component(self, symbol: str, fund_flow_data: Dict = None) -> Tuple[float, Dict]:
        """机构持仓与资金流向评估。"""
        detail = {"net_inflow": None, "main_force": None, "description": ""}

        try:
            score = 50  # 基础中性分

            if fund_flow_data and fund_flow_data.get("data_success"):
                # 从资金流向数据评估机构行为
                summary = fund_flow_data.get("summary", {})
                if summary:
                    main_net = summary.get("main_net_inflow")  # 主力净流入
                    if main_net is not None:
                        detail["main_force"] = main_net
                        if main_net > 5000:  # 5000万以上大幅流入
                            score = 95
                        elif main_net > 2000:
                            score = 80
                        elif main_net > 500:
                            score = 65
                        elif main_net > 0:
                            score = 55
                        elif main_net > -1000:
                            score = 40
                        else:
                            score = 25
                        detail["description"] = f"主力净流入{main_net:.0f}万元"
                        return score, detail

                # 尝试从明细数据
                inflow_data = fund_flow_data.get("inflow_data")
                if inflow_data:
                    detail["description"] = "有资金流向数据"
                    return 60, detail

            # 尝试通过akshare获取机构持仓信息
            try:
                import akshare as ak
                holder_df = ak.stock_institute_hold_detail(symbol=symbol)
                if holder_df is not None and not holder_df.empty:
                    num_holders = len(holder_df)
                    detail["num_institutional_holders"] = num_holders
                    if num_holders >= 50:
                        score = 85
                    elif num_holders >= 20:
                        score = 70
                    elif num_holders >= 10:
                        score = 55
                    else:
                        score = 40
                    detail["description"] = f"机构持仓家数: {num_holders}"
                    return score, detail
            except Exception:
                pass

            detail["description"] = "无机构持仓数据，使用中性评估"
            return score, detail

        except Exception as e:
            detail["description"] = f"计算异常: {e}"
            return 50, detail

    # ───────── M: Market Direction ─────────

    def _calc_m_component(self, market_df: pd.DataFrame = None) -> Tuple[float, Dict]:
        """市场方向评估（大盘趋势）。"""
        detail = {"trend": "未知", "above_ema50": None, "description": ""}

        try:
            if market_df is None or len(market_df) < 50:
                detail["description"] = "无大盘数据"
                return 50, detail

            close = market_df['Close'].values

            # 计算50日EMA
            ema50 = self._calc_ema(close, 50)

            # 当前价相对EMA
            current = close[-1]
            above_ema = current > ema50[-1]
            ema_distance = (current - ema50[-1]) / ema50[-1] * 100

            detail["above_ema50"] = above_ema
            detail["ema_distance"] = round(ema_distance, 2)

            # 20日趋势
            if len(close) >= 20:
                ret_20d = (close[-1] / close[-20] - 1) * 100
                detail["return_20d"] = round(ret_20d, 2)
            else:
                ret_20d = 0

            # 评分
            if above_ema and ema_distance > 3 and ret_20d > 2:
                score = 100
                trend = "强势上涨"
            elif above_ema and ema_distance > 0:
                score = 80
                trend = "上涨趋势"
            elif above_ema and ema_distance <= 0:
                score = 60
                trend = "震荡偏多"
            elif not above_ema and ema_distance > -3:
                score = 40
                trend = "震荡偏空"
            elif not above_ema and ema_distance > -8:
                score = 20
                trend = "下跌趋势"
            else:
                score = 0
                trend = "熊市"

            detail["trend"] = trend
            detail["description"] = f"大盘{trend}，距50EMA {ema_distance:+.1f}%"
            return score, detail

        except Exception as e:
            detail["description"] = f"计算异常: {e}"
            return 50, detail

    # ───────── 辅助方法 ─────────

    def _get_market_index_data(self) -> Optional[pd.DataFrame]:
        """获取大盘指数数据（沪深300或上证指数），带实例级缓存。"""
        # 实例级缓存：同一个 CANSLIMAnalyzer 实例只拉一次
        if hasattr(self, '_market_cache') and self._market_cache is not None:
            return self._market_cache

        try:
            import akshare as ak
            from datetime import datetime, timedelta

            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=380)).strftime('%Y%m%d')

            # 尝试获取上证指数
            df = ak.stock_zh_index_daily_em(symbol="sh000001", start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                df = df.rename(columns={'date': 'Date', 'open': 'Open', 'close': 'Close',
                                        'high': 'High', 'low': 'Low', 'volume': 'Volume'})
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)
                self._market_cache = df
                return df
        except Exception as e:
            print(f"[CANSLIM] 获取大盘数据异常: {e}")

        return None

    def _rs_to_rank(self, weighted_rs: float) -> int:
        """将加权相对强度转换为1-99排名。"""
        # 经验映射：基于A股市场统计
        if weighted_rs >= 40:
            return 99
        elif weighted_rs >= 30:
            return 95
        elif weighted_rs >= 20:
            return 90
        elif weighted_rs >= 15:
            return 85
        elif weighted_rs >= 10:
            return 80
        elif weighted_rs >= 5:
            return 70
        elif weighted_rs >= 0:
            return 60
        elif weighted_rs >= -5:
            return 50
        elif weighted_rs >= -10:
            return 40
        elif weighted_rs >= -20:
            return 30
        elif weighted_rs >= -30:
            return 20
        else:
            return 10

    def _score_growth(self, growth: float, thresholds: List[float] = None) -> float:
        """将增长率映射为0-100分。"""
        if thresholds is None:
            thresholds = [50, 30, 18, 10, 0]
        # thresholds 从高到低
        scores = [100, 80, 65, 50, 35]
        for threshold, score in zip(thresholds, scores):
            if growth >= threshold:
                return score
        return 20 if growth >= -10 else 10

    def _parse_percent(self, value) -> Optional[float]:
        """解析百分比字符串。"""
        if value is None or value == "N/A":
            return None
        try:
            if isinstance(value, str):
                value = value.replace('%', '').replace('％', '').strip()
            return float(value)
        except (ValueError, TypeError):
            return None

    def _calc_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """计算EMA。"""
        ema = np.zeros_like(data, dtype=float)
        multiplier = 2.0 / (period + 1)
        ema[0] = data[0]
        for i in range(1, len(data)):
            ema[i] = (data[i] - ema[i - 1]) * multiplier + ema[i - 1]
        return ema

    def _get_rating(self, score: float) -> Tuple[str, str, str]:
        """根据综合分获取评级。"""
        for low, high, rating, rating_cn, desc in RATING_BANDS:
            if low <= score <= high:
                return rating, rating_cn, desc
        return "Below Average", "偏弱", "不符合CANSLIM标准"


def format_canslim_for_ai(result: Dict) -> str:
    """将 CANSLIM 分析结果格式化为 AI 可读文本。"""
    if not result or not result.get("components"):
        return "CANSLIM分析数据不可用。"

    lines = []
    lines.append(f"=== CANSLIM/RPS 选股分析 ===")
    lines.append(f"综合评分: {result['composite_score']}/100 ({result['rating_cn']} - {result['rating']})")
    lines.append(f"RPS排名: {result['rps_rank']}")
    lines.append(f"评级说明: {result['rating_desc']}")
    lines.append("")

    # 熊市警告
    if result.get("details", {}).get("bear_market_warning"):
        lines.append("⚠️ 熊市警告：M组件为0，当前不适宜买入！")
        lines.append("")

    lines.append("--- 七大组件详情 ---")
    for key in ["C", "A", "N", "S", "L", "I", "M"]:
        comp = result["components"].get(key, {})
        score = comp.get("score", 0)
        name = comp.get("name", key)
        detail = comp.get("detail", {})
        desc = detail.get("description", "")
        weight = int(COMPONENT_WEIGHTS.get(key, 0) * 100)
        bar = "█" * int(score / 10) + "░" * (10 - int(score / 10))
        lines.append(f"  {key} - {name} (权重{weight}%): {score}/100  {bar}")
        if desc:
            lines.append(f"      └─ {desc}")

    # RPS详情
    l_detail = result["components"].get("L", {}).get("detail", {})
    if l_detail.get("stock_returns"):
        lines.append("")
        lines.append("--- RPS相对强度详情 ---")
        sr = l_detail.get("stock_returns", {})
        mr = l_detail.get("market_returns", {})
        lines.append(f"  个股涨幅: 3月{sr.get('3m', 'N/A')}% / 6月{sr.get('6m', 'N/A')}% / 12月{sr.get('12m', 'N/A')}%")
        lines.append(f"  大盘涨幅: 3月{mr.get('3m', 'N/A')}% / 6月{mr.get('6m', 'N/A')}% / 12月{mr.get('12m', 'N/A')}%")
        lines.append(f"  加权RS: {l_detail.get('weighted_rs', 'N/A')}%")
        lines.append(f"  RPS排名: {l_detail.get('rps_rank', 'N/A')}")

    return "\n".join(lines)
