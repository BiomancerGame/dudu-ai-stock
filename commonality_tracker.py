"""共性追踪分析引擎

场景：用户每个交易日选一只股票，形成日期序列。
AI分析这些历史选股的共性规律，预测下一个交易日的那只股票。
不断追加数据、验证、学习。
"""
from __future__ import annotations

import json
import time
from typing import Callable, Dict, List, Optional

import pandas as pd

from deepseek_client import DeepSeekClient
from stock_data import stock_data_fetcher
from data_source_manager import DataSourceManager
import commonality_tracker_db as db


class CommonalityTracker:
    """共性追踪分析器"""

    def __init__(self):
        self.deepseek_client = DeepSeekClient()
        self.data_source = DataSourceManager()
        self.fetcher = stock_data_fetcher

    # ─────────── 主流程 ───────────

    def analyze_and_predict(self, picks: List[Dict], predict_date: str,
                            emit: Callable[[str, int], None] = None) -> Dict:
        """
        分析每日选股序列的共性，预测下一个交易日的股票。

        Args:
            picks: [{"date":"3.02","symbol":"300835","name":"龙磁科技","price":97.48}, ...]
            predict_date: 要预测的下一个交易日（如 "3.25"）
            emit: 进度回调 (message, progress%)
        """
        if emit is None:
            emit = lambda msg, pct: print(f"  [{pct}%] {msg}")

        emit("保存选股数据...", 5)
        db.save_picks(picks)

        # 获取每只股票的技术数据
        emit("正在获取股票技术数据...", 10)
        enriched = []
        total = len(picks)
        for i, p in enumerate(picks):
            profile = self._get_stock_profile(p["symbol"])
            profile["pick_date"] = p["date"]
            profile["name"] = p.get("name", "")
            profile["entry_price"] = p.get("price", 0)
            enriched.append(profile)
            pct = 10 + int(50 * (i + 1) / total)
            emit(f"获取数据 {i+1}/{total}: {p.get('name', p['symbol'])}", pct)
            time.sleep(0.2)

        # 获取历史学习规则
        rules = db.get_learning_rules(min_confidence=0.3)
        rules_text = "\n".join(
            f"- [置信度{r['confidence']:.0%}] {r['rule_content']}"
            for r in rules[:10]
        ) if rules else ""

        # 获取历史验证记录，让AI参考
        verifications = db.get_verifications()
        history_text = ""
        if verifications:
            lines = []
            for v in verifications[:5]:
                hit_str = "✅ 命中" if v["is_hit"] else "❌ 未中"
                lines.append(f"- 预测{v['predict_symbol']} → 实际{v['actual_symbol']} {hit_str}")
            history_text = "\n".join(lines)

        # AI分析
        emit("AI正在分析共性特征...", 65)
        result = self._ai_analyze(enriched, predict_date, rules_text, history_text)

        # 保存分析轮次
        emit("保存分析结果...", 90)
        dates = [p["date"] for p in picks]
        data_range = f"{dates[0]} ~ {dates[-1]}" if dates else ""
        round_id = db.save_round(data_range, len(picks), result)
        result["round_id"] = round_id

        emit("分析完成！", 100)
        return result

    def batch_learn(self, picks_list: List[Dict],
                    emit: Callable[[str, int], None] = None) -> Dict:
        """
        批量回测学习：逐条处理历史数据，自动完成 提取特征→预测→对比→收敛规则。

        Args:
            picks_list: [{"date": "5.12", "symbol": "300567", "name": "精测电子"}, ...]
                        按日期正序排列，至少3条
            emit: 进度回调
        Returns:
            包含学习过程和最终规则统计的字典
        """
        if emit is None:
            emit = lambda msg, pct: print(f"  [{pct}%] {msg}")

        if len(picks_list) < 3:
            return {"error": "至少需要3条数据才能开始学习"}

        # 先保存所有数据到DB
        db.save_picks(picks_list)

        results = []
        total = len(picks_list)
        train_start = 3  # 前3条作为初始训练集，从第4条开始预测

        for i in range(train_start, total):
            progress = int((i - train_start) / (total - train_start) * 100)
            current = picks_list[i]
            history = picks_list[:i]  # 前面的作为历史

            emit(f"第{i-train_start+1}轮：预测 {current['date']} ...", progress)

            # 1. 提取最近几只历史股票的特征（每只用其pick_date作为截止日，防数据泄露）
            recent = history[-5:]
            features = []
            for p in recent:
                profile = self._get_stock_profile(p["symbol"], as_of_date=p["date"])
                profile["pick_date"] = p["date"]
                profile["name"] = p.get("name", profile.get("name", p["symbol"]))
                features.append(profile)
                time.sleep(0.15)

            # 2. 加载当前规则
            rules = db.get_learning_rules(min_confidence=0.3)
            rules_text = "\n".join(
                f"- [{r['confidence']:.0%}] {r['rule_content']}" for r in rules[:20]
            ) if rules else "暂无"

            history_text = "\n".join(
                f"- {p['date']} | {p.get('name','')} | {p['symbol']}"
                for p in history
            )

            features_text = json.dumps(features, ensure_ascii=False, indent=1)

            # 3. AI预测
            existing = [p["symbol"] for p in history]
            prompt = f"""你是A股选股分析师，正在学习一位用户的选股规律。

## 历史选股序列
{history_text}

## 最近5只股票的真实技术特征（系统查询）
{features_text}

## 已学习的规则
{rules_text}

## 任务
基于以上历史序列和特征模式，预测 **{current['date']}** 这天用户会选哪只股票。
注意：不能选已出现过的({', '.join(existing[-10:])})。

## 输出（严格JSON）：
```json
{{
    "predict_symbol": "6位代码",
    "predict_name": "名称",
    "predict_reason": "100字以内的预测理由",
    "pattern_summary": "你发现的选股模式（50字）"
}}
```"""
            messages = [
                {"role": "system", "content": "选股模式学习专家，输出纯JSON。"},
                {"role": "user", "content": prompt}
            ]
            resp = self.deepseek_client.call_api(messages, max_tokens=800)
            pred = self._parse_json(resp, current["date"])

            predicted_symbol = pred.get("predict_symbol", "")
            actual_symbol = current["symbol"]
            is_hit = predicted_symbol == actual_symbol

            # 4. AI总结本轮教训并生成/更新规则
            learn_prompt = f"""预测结果：{'命中' if is_hit else '未命中'}
- 预测: {predicted_symbol} ({pred.get('predict_name','')})
- 实际: {actual_symbol} ({current.get('name','')})
- 预测理由: {pred.get('predict_reason','')}

实际股票的真实特征：
{json.dumps(self._get_stock_profile(actual_symbol, as_of_date=current['date']), ensure_ascii=False, indent=1)}

请总结1-2条选股规则教训（每条不超过60字），用于改进下次预测。
输出JSON: {{"new_rules": ["规则1", "规则2"]}}"""

            learn_msgs = [
                {"role": "system", "content": "选股规则提炼专家，输出纯JSON。"},
                {"role": "user", "content": learn_prompt}
            ]
            learn_resp = self.deepseek_client.call_api(learn_msgs, max_tokens=500)
            try:
                learn_result = json.loads(self._extract_json_str(learn_resp))
                new_rules = learn_result.get("new_rules", [])
            except Exception:
                new_rules = []

            # 5. 保存规则（带去重）— 命中产生的规则初始置信度高，未命中的教训初始低
            init_conf = 0.7 if is_hit else 0.4
            for rule in new_rules:
                if rule and len(rule) > 5:
                    db.save_learning_rule(rule, confidence=init_conf)

            # 6. 更新所有已有规则置信度（命中+1hit，未命中+1miss）
            self._update_rules_confidence(pred, actual_symbol, is_hit)

            # 7. 淘汰低质量规则
            db.prune_low_confidence_rules(min_attempts=3, threshold=0.25)

            round_result = {
                "round": i - train_start + 1,
                "date": current["date"],
                "predicted": predicted_symbol,
                "actual": actual_symbol,
                "is_hit": is_hit,
                "pattern": pred.get("pattern_summary", ""),
                "new_rules": new_rules,
            }
            results.append(round_result)
            time.sleep(0.3)

        # 最终统计
        hits = sum(1 for r in results if r["is_hit"])
        total_rounds = len(results)
        final_rules = db.get_learning_rules(min_confidence=0.3)

        emit("批量学习完成！", 100)
        return {
            "total_rounds": total_rounds,
            "hits": hits,
            "hit_rate": f"{hits/total_rounds*100:.1f}%" if total_rounds > 0 else "0%",
            "rounds": results,
            "rules_count": len(final_rules),
            "top_rules": [
                {"confidence": r["confidence"], "content": r["rule_content"]}
                for r in sorted(final_rules, key=lambda x: x["confidence"], reverse=True)[:10]
            ],
        }

    def quick_predict(self, predict_date: str,
                      emit: Callable[[str, int], None] = None) -> Dict:
        """
        两轮预测: AI先给候选 -> 系统拉真实数据 -> AI基于真实数据做最终决策.
        """
        if emit is None:
            emit = lambda msg, pct: print(f"  [{pct}%] {msg}")

        emit("读取历史数据...", 5)
        all_picks = db.get_all_picks()
        if len(all_picks) < 3:
            return {"error": "历史数据不足3条，请先录入数据"}

        # 防止数据泄露：只使用predict_date之前的历史记录（严格小于，不含当天）
        try:
            predict_dt = self._parse_predict_date(predict_date)
            filtered_picks = []
            for p in all_picks:
                try:
                    pick_dt = self._parse_predict_date(p["pick_date"])
                    if pick_dt < predict_dt:  # 严格小于
                        filtered_picks.append(p)
                except Exception:
                    filtered_picks.append(p)  # 解析失败的保留
            all_picks = filtered_picks
            if len(all_picks) < 3:
                return {"error": f"{predict_date}之前的历史数据不足3条"}
        except Exception:
            pass

        picks_text = "\n".join(
            f"- {p['pick_date']} | {p.get('name','')} | {p['symbol']} | {p.get('entry_price',0)}"
            for p in all_picks
        )

        emit("加载学习规则...", 8)
        rules = db.get_learning_rules(min_confidence=0.3)
        if rules:
            # 按重要性排序：含关键条件的规则优先
            priority_keywords = ["资金", "净流入", "净流出", "量比", "MA20", "dist_ma20", "板块"]
            def rule_priority(r):
                score = r['confidence'] * 100
                content = r['rule_content']
                for kw in priority_keywords:
                    if kw in content:
                        score += 10
                return score
            sorted_rules = sorted(rules, key=rule_priority, reverse=True)
            rules_text = "\n".join(
                f"- [{r['confidence']:.0%}] {r['rule_content']}"
                for r in sorted_rules[:30]
            )
        else:
            rules_text = ""

        verifications = db.get_verifications()
        history_lines = []
        for v in verifications[:8]:
            hit_str = "HIT" if v["is_hit"] else "MISS"
            history_lines.append(f"- {hit_str} pred={v['predict_symbol']} actual={v['actual_symbol']}")
        history_text = "\n".join(history_lines) if history_lines else ""

        existing_symbols = list(set(p['symbol'] for p in all_picks))
        exclude_text = ", ".join(existing_symbols)

        # 拉取市场数据
        emit("获取当前市场行情...", 12)
        market_context = self._fetch_market_context(emit)

        # ═══ 提取近期选股的真实技术特征（让AI看到选股模式）═══
        emit("提取近期选股特征...", 25)
        recent_picks = all_picks[-5:]  # 最近5只
        picks_features = []
        for p in recent_picks:
            sym = p['symbol']
            emit(f"查询 {p.get('name', sym)} 特征...", 25)
            # 用 pick_date 作为该股票特征的截止日（不泄露未来数据）
            profile = self._get_stock_profile(sym, as_of_date=p.get("pick_date"))
            profile["pick_date"] = p["pick_date"]
            profile["name"] = p.get("name", profile.get("name", sym))
            picks_features.append(profile)
            time.sleep(0.2)

        features_text = json.dumps(picks_features, ensure_ascii=False, indent=2)

        # ═══ 第一轮：AI给出3个候选股票 ═══
        emit("AI第一轮：筛选候选股票...", 35)

        prompt_round1 = f"""你是A股选股专家。

## 任务
基于规则和历史选股规律，给出3只候选股票（只给代码和名称，后续系统会查询真实数据验证）。

## 要求
- 3只候选必须是全新的，不能是以下已出现过的：{exclude_text}
- 候选应符合已学习的规则条件
- 候选的技术形态应与近期选股特征相似（见下方真实数据）

## 历史选股序列
{picks_text}

## 近期选股的真实技术特征（系统查询，非常重要！）
{features_text}

## 已学习的规则
{rules_text if rules_text else "暂无"}

## 当前市场数据
{market_context}

## 历史预测记录
{history_text if history_text else "暂无"}

## 输出（严格JSON）：
```json
{{
    "candidates": [
        {{"symbol": "6位代码", "name": "名称", "reason": "为什么选它（50字）"}},
        {{"symbol": "6位代码", "name": "名称", "reason": "为什么选它（50字）"}},
        {{"symbol": "6位代码", "name": "名称", "reason": "为什么选它（50字）"}}
    ]
}}
```"""

        messages_r1 = [
            {"role": "system", "content": "选股候选推荐，输出纯JSON。"},
            {"role": "user", "content": prompt_round1}
        ]
        resp_r1 = self.deepseek_client.call_api(messages_r1, max_tokens=1000)
        r1 = self._parse_candidates(resp_r1)

        candidates = r1.get("candidates", [])
        if not candidates:
            return {"error": "AI未能给出候选股票", "predict_date": predict_date}

        # ═══ 拉取每个候选的真实技术数据（截止predict_date，避免数据泄露）═══
        emit("获取候选股票的真实行情数据...", 45)
        candidates_with_data = []
        for i, c in enumerate(candidates[:3]):
            sym = c.get("symbol", "")
            if not sym or len(sym) != 6:
                continue
            emit(f"查询 {c.get('name', sym)} ({sym}) 行情...", 45 + i * 8)
            profile = self._get_stock_profile(sym, as_of_date=predict_date)
            profile["candidate_reason"] = c.get("reason", "")
            profile["name"] = c.get("name", profile.get("name", sym))
            candidates_with_data.append(profile)
            time.sleep(0.3)

        if not candidates_with_data:
            return {"error": "候选股票数据获取失败", "predict_date": predict_date}

        # ═══ 第二轮：AI基于真实数据做最终选择 ═══
        emit("AI第二轮：基于真实数据做最终决策...", 70)

        candidates_text = json.dumps(candidates_with_data, ensure_ascii=False, indent=2)

        prompt_round2 = f"""你是A股选股专家。

## 任务
从以下候选股票中选出1只最符合规则的，预测为 **{predict_date}** 的选股。
下方是系统实时查询的**真实技术数据**，请严格基于真实数据判断。

## 候选股票及其真实数据
{candidates_text}

## 已学习的规则（选股标准）
{rules_text if rules_text else "暂无"}

## 选择标准（逐项核查真实数据）
1. MA20位置：dist_ma20是否符合规则要求的范围
2. 量比：vol_ratio是否符合规则（如<0.8为缩量）
3. 资金流向：fund_direction是否为"净流入"，fund_buy_pct主买占比是否>50%
   - 如果资金为净流出，必须降低置信度或排除该候选
4. 涨跌幅：change_1d/change_5d是否符合回调或强势规则
5. 如果某只候选的真实数据不符合规则，直接排除

## 输出（严格JSON）：
```json
{{
    "predict_date": "{predict_date}",
    "predict_symbol": "最终选定的6位代码",
    "predict_name": "股票名称",
    "predict_reason": "基于真实数据的选择理由（必须引用具体数值，包括资金流向，200-300字）",
    "confidence": "高/中/低",
    "applied_rules": ["应用的规则1", "规则2"],
    "data_check": "真实数据验证：现价xx，MA20 xx，量比xx，资金xx，是否符合规则"
}}
```"""

        messages_r2 = [
            {"role": "system", "content": "基于真实行情数据的选股决策专家。只能引用系统提供的真实数据。输出纯JSON。"},
            {"role": "user", "content": prompt_round2}
        ]
        resp_r2 = self.deepseek_client.call_api(messages_r2, max_tokens=2000)
        result = self._parse_json(resp_r2, predict_date)

        # 附上最终选中股票的真实数据
        final_symbol = result.get("predict_symbol", "")
        for c in candidates_with_data:
            if c.get("symbol") == final_symbol:
                result["real_data"] = c
                break
        else:
            if final_symbol and len(final_symbol) == 6:
                emit("获取最终股票行情...", 80)
                result["real_data"] = self._get_stock_profile(final_symbol)

        # 附上所有候选信息
        result["candidates"] = candidates_with_data

        # 保存
        emit("保存结果...", 90)
        dates = [p["pick_date"] for p in all_picks]
        data_range = f"{dates[0]} ~ {dates[-1]}"
        round_id = db.save_round(data_range, len(all_picks), result)
        result["round_id"] = round_id
        result["mode"] = "quick"

        emit("预测完成！", 100)
        return result

    def _parse_candidates(self, text: str) -> Dict:
        """解析第一轮候选结果"""
        try:
            json_str = self._extract_json_str(text)
            return json.loads(json_str)
        except Exception:
            return {"candidates": []}

    def _fetch_market_context(self, emit) -> str:
        """获取当前市场行情上下文(tushare行业资金流向+tdxpy大盘指数)"""
        from datetime import datetime, timedelta
        context_parts = []

        # ── 1. tdxpy拉取大盘指数实时行情 ──
        emit("拉取大盘指数实时行情...", 18)
        try:
            indices = self._get_index_realtime()
            if indices:
                lines = ["### 大盘指数实时行情"]
                for idx in indices:
                    chg = idx.get("change_pct", 0)
                    tag = "+" if chg > 0 else ""
                    lines.append(f"- {idx['name']}: {idx['price']:.2f} ({tag}{chg:.2f}%)")
                context_parts.append("\n".join(lines))
        except Exception as e:
            context_parts.append(f"大盘指数获取失败: {e}")

        # ── 2. tushare拉取行业资金流向 ──
        if self.data_source.tushare_available:
            emit("拉取行业资金流向(tushare)...", 28)
            try:
                today = datetime.now().strftime('%Y%m%d')
                # 尝试今天，如果没数据就取昨天
                for offset in range(3):
                    dt = (datetime.now() - timedelta(days=offset)).strftime('%Y%m%d')
                    df = self.data_source.tushare_api.moneyflow_hsgt(trade_date=dt)
                    if df is not None and not df.empty:
                        row = df.iloc[0]
                        lines = ["### 北向资金"]
                        lines.append(f"- 日期: {dt}")
                        lines.append(f"- 沪股通净流入: {row.get('north_money', 0)/1e4:.2f}亿")
                        context_parts.append("\n".join(lines))
                        break
            except Exception:
                pass

            emit("拉取行业涨跌(tushare)...", 36)
            try:
                today = datetime.now().strftime('%Y%m%d')
                for offset in range(3):
                    dt = (datetime.now() - timedelta(days=offset)).strftime('%Y%m%d')
                    df = self.data_source.tushare_api.index_daily(
                        ts_code='', trade_date=dt
                    )
                    if df is not None and not df.empty:
                        # 取申万行业指数
                        sw_df = df[df['ts_code'].str.startswith('8')]
                        if not sw_df.empty:
                            sw_df = sw_df.sort_values('pct_chg', ascending=False)
                            lines = [f"### 行业指数涨跌TOP10 ({dt})"]
                            for _, r in sw_df.head(10).iterrows():
                                lines.append(f"- {r['ts_code']}: {r['pct_chg']:+.2f}%")
                            context_parts.append("\n".join(lines))
                        break
            except Exception:
                pass

        # ── 3. 兜底：用历史选股序列中的板块信息做市场方向推断 ──
        if not context_parts:
            context_parts.append("市场实时板块数据暂不可用，请AI基于规则和历史序列进行推断")

        return "\n\n".join(context_parts)

    def _get_index_realtime(self) -> list:
        """用tdxpy获取主要指数实时行情"""
        try:
            from tdxpy.hq import TdxHq_API
            api = TdxHq_API()

            TDX_SERVERS = [
                '110.41.147.114', '221.194.181.176',
                '120.79.60.82', '47.107.75.159',
                '218.6.170.47', '119.147.212.81'
            ]
            connected = False
            for ip in TDX_SERVERS:
                try:
                    r = api.connect(ip, 7709)
                    if r:
                        connected = True
                        break
                except Exception:
                    continue
            if not connected:
                return []

            # 上证指数(1,000001)、深证成指(0,399001)、创业板指(0,399006)
            indices_info = [
                (1, '000001', '上证指数'),
                (0, '399001', '深证成指'),
                (0, '399006', '创业板指'),
            ]
            result = []
            for mkt, code, name in indices_info:
                data = api.get_security_quotes(mkt, code)
                if data and len(data) > 0:
                    q = data[0]
                    price = q.get("price", 0)
                    last_close = q.get("last_close", 0)
                    chg_pct = round((price / last_close - 1) * 100, 2) if last_close > 0 else 0
                    result.append({"name": name, "price": price, "change_pct": chg_pct})

            api.disconnect()
            return result
        except Exception:
            return []

    def verify(self, round_id: int, actual_symbol: str, actual_name: str = "") -> Dict:
        """
        验证预测结果: 用户给出实际那天的股票, 对比预测.

        Args:
            round_id: 分析轮次ID
            actual_symbol: 实际的股票代码
            actual_name: 实际的股票名称
        """
        # 获取该轮预测
        rounds = db.get_all_rounds()
        target = None
        for r in rounds:
            if r["id"] == round_id:
                target = r
                break
        if not target:
            return {"error": "未找到对应分析轮次"}

        predicted = target.get("predict_symbol", "")
        is_hit = predicted == actual_symbol

        # AI评估并提取学习规则
        feedback_result = self._ai_verify(target, actual_symbol, actual_name, is_hit)

        # 保存验证
        new_rules = feedback_result.get("new_rules", [])
        db.save_verification(
            round_id, predicted, actual_symbol, actual_name,
            is_hit, feedback_result.get("feedback", ""), new_rules
        )

        # 保存新规则
        for rule in new_rules:
            db.save_learning_rule(rule, confidence=0.5)

        # 回溯已有规则，根据本次验证结果更新置信度
        self._update_rules_confidence(target, actual_symbol, is_hit)

        # 自动淘汰：验证>=3次且置信度<25%的规则自动删除
        pruned = db.prune_low_confidence_rules(min_attempts=3, threshold=0.25)
        if pruned:
            print(f"🗑️ 自动淘汰了 {pruned} 条低置信度规则")

        # 把实际结果也加入每日选股记录
        if actual_symbol:
            predict_date = target.get("predict_date", "")
            if predict_date:
                db.save_picks([{
                    "date": predict_date,
                    "symbol": actual_symbol,
                    "name": actual_name,
                    "price": 0
                }])

        return {
            "is_hit": is_hit,
            "predicted": predicted,
            "actual": actual_symbol,
            "feedback": feedback_result.get("feedback", ""),
            "new_rules": new_rules,
        }

    # ─────────── 数据采集 ───────────

    def _get_stock_profile(self, symbol: str, as_of_date: str = None) -> Dict:
        """获取单只股票的多维度数据画像(tushare历史+tdxpy实时+资金流向)

        Args:
            as_of_date: 截止日期。指定时只拉历史K线数据（不拉实时），保证不泄露未来数据。
        """
        profile = {"symbol": symbol}
        if as_of_date:
            profile["as_of_date"] = as_of_date

        # ── 1. tushare拉取历史K线（MA、涨跌幅）──
        try:
            hist_df = self._get_hist_tushare(symbol, days=30, as_of_date=as_of_date)
            if hist_df is not None and len(hist_df) > 5:
                close = hist_df['close'].values
                vol = hist_df['volume'].values if 'volume' in hist_df.columns else hist_df.get('vol', pd.Series()).values

                profile["current_price"] = round(float(close[-1]), 2)
                profile["price_trend"] = "上涨" if close[-1] > close[-5] else "下跌"
                profile["ma5"] = round(float(close[-5:].mean()), 2)
                profile["ma10"] = round(float(close[-10:].mean()), 2) if len(close) >= 10 else None
                profile["ma20"] = round(float(close[-20:].mean()), 2) if len(close) >= 20 else None

                if profile.get("ma20"):
                    profile["dist_ma20"] = round((close[-1] / profile["ma20"] - 1) * 100, 2)

                if len(vol) >= 5:
                    avg5_vol = vol[-5:].mean()
                    profile["vol_ratio"] = round(float(vol[-1] / avg5_vol), 2) if avg5_vol > 0 else 1

                if len(close) >= 2:
                    profile["change_1d"] = round((close[-1] / close[-2] - 1) * 100, 2)
                if len(close) >= 5:
                    profile["change_5d"] = round((close[-1] / close[-5] - 1) * 100, 2)
                if len(close) >= 20:
                    profile["change_20d"] = round((close[-1] / close[-20] - 1) * 100, 2)
        except Exception as e:
            profile["hist_error"] = str(e)

        # ── 2. tdxpy拉取实时行情 + 资金流向 ──（仅当不指定历史日期时）
        if not as_of_date:
            try:
                realtime = self._get_realtime_tdx(symbol)
                if realtime:
                    profile["realtime_price"] = realtime.get("price")
                    profile["today_change_pct"] = round(
                        (realtime["price"] / realtime["last_close"] - 1) * 100, 2
                    ) if realtime.get("last_close") and realtime["last_close"] > 0 else None
                    profile["today_volume"] = realtime.get("vol")
                    profile["today_amount"] = realtime.get("amount")

                    # 资金流向：主动买入量 vs 主动卖出量
                    b_vol = realtime.get("b_vol", 0)
                    s_vol = realtime.get("s_vol", 0)
                    total = b_vol + s_vol
                    if total > 0:
                        net_inflow = b_vol - s_vol
                        profile["fund_net_inflow_vol"] = net_inflow
                        profile["fund_buy_pct"] = round(b_vol / total * 100, 1)
                        profile["fund_direction"] = "净流入" if net_inflow > 0 else "净流出"
                        # 用成交额估算资金净流入金额
                        if realtime.get("amount") and realtime["amount"] > 0:
                            avg_price = realtime["amount"] / (total * 100) if total > 0 else 0
                            profile["fund_net_inflow_amount"] = round(net_inflow * 100 * avg_price / 1e4, 2)
                            profile["fund_net_inflow_desc"] = f"{'净流入' if net_inflow > 0 else '净流出'}{abs(profile['fund_net_inflow_amount']):.0f}万"
            except Exception as e:
                profile["realtime_error"] = str(e)

        # ── 3. 基本信息（行业）──
        try:
            basic = self.data_source.get_stock_basic_info(symbol)
            if basic:
                profile["industry"] = basic.get("industry", "未知")
                if not profile.get("name"):
                    profile["name"] = basic.get("name", symbol)
        except Exception:
            pass

        return profile

    def _get_hist_tushare(self, symbol: str, days: int = 30, as_of_date: str = None) -> Optional[pd.DataFrame]:
        """用tushare获取近N天历史日线

        Args:
            as_of_date: 预测目标日期（即"上涨日"），格式如 '5.20'/'2026-05-20'/'20260520'。
                        数据严格截止到该日期 **前一天**（不包含as_of_date当天），
                        因为预测某日上涨的股票只能用该日之前的数据。
                        为None时使用当天日期（即拉到今天为止的所有可用数据）。
        """
        from datetime import datetime, timedelta

        # 解析截止日期：as_of_date是预测目标日，数据要严格小于该日期
        if as_of_date:
            target_dt = self._parse_predict_date(as_of_date)
            end_dt = target_dt - timedelta(days=1)  # 数据截止到前一天
        else:
            end_dt = datetime.now()

        end = end_dt.strftime('%Y%m%d')
        start = (end_dt - timedelta(days=days * 2)).strftime('%Y%m%d')

        # 统一走data_source.get_stock_hist_data,享受本地缓存
        df = self.data_source.get_stock_hist_data(symbol, start_date=start, end_date=end)
        if df is not None and not df.empty:
            df = df.sort_values('date').tail(days).reset_index(drop=True)
            return df
        return None

    @staticmethod
    def _parse_predict_date(date_str: str) -> 'datetime':
        """将用户输入的日期字符串解析为datetime对象。支持: '5.19', '2026-05-19', '20260519'"""
        from datetime import datetime
        date_str = date_str.strip()
        # 格式1: '5.19' 或 '05.19'
        if '.' in date_str and len(date_str) <= 5:
            parts = date_str.split('.')
            month, day = int(parts[0]), int(parts[1])
            year = datetime.now().year
            return datetime(year, month, day)
        # 格式2: '2026-05-19'
        if '-' in date_str:
            return datetime.strptime(date_str, '%Y-%m-%d')
        # 格式3: '20260519'
        if len(date_str) == 8:
            return datetime.strptime(date_str, '%Y%m%d')
        # fallback
        return datetime.now()

    def _get_realtime_tdx(self, symbol: str) -> Optional[Dict]:
        """用tdxpy获取实时行情(含资金流向)"""
        try:
            from tdxpy.hq import TdxHq_API
            api = TdxHq_API()

            # 判断市场
            if symbol.startswith('6') or symbol.startswith('68'):
                market = 1  # 上海
            else:
                market = 0  # 深圳

            TDX_SERVERS = [
                '110.41.147.114', '221.194.181.176',
                '120.79.60.82', '47.107.75.159',
                '218.6.170.47', '119.147.212.81'
            ]

            connected = False
            for ip in TDX_SERVERS:
                try:
                    r = api.connect(ip, 7709)
                    if r:
                        connected = True
                        break
                except Exception:
                    continue

            if not connected:
                return None

            data = api.get_security_quotes(market, symbol)
            api.disconnect()

            if data and len(data) > 0:
                q = data[0]
                return {
                    "price": q.get("price", 0),
                    "last_close": q.get("last_close", 0),
                    "open": q.get("open", 0),
                    "high": q.get("high", 0),
                    "low": q.get("low", 0),
                    "vol": q.get("vol", 0),
                    "amount": q.get("amount", 0),
                    "b_vol": q.get("b_vol", 0),
                    "s_vol": q.get("s_vol", 0),
                }
            return None
        except Exception:
            return None

    # ─────────── AI调用 ───────────

    def _ai_analyze(self, profiles: List[Dict], predict_date: str,
                    rules_text: str, history_text: str) -> Dict:
        """AI分析共性并预测下一交易日的那只股票"""

        profiles_text = json.dumps(profiles, ensure_ascii=False, indent=2)

        prompt = f"""你是一位资深A股量化分析师。

## 任务
以下是用户**每个交易日选出的一只股票**（按时间顺序），请分析这些选股的共性规律，
然后预测 **{predict_date}** 这天会选出哪一只股票。

## 每日选股序列
{profiles_text}

## 历史学习规则（重要！必须严格遵循高置信度规则）
{rules_text if rules_text else "暂无"}

⚠️ 置信度>=70%的规则是经过反复验证的铁律，预测时**必须**优先满足这些条件。
置信度<40%的规则仅供参考，可能不可靠。

## 历史预测验证（从错误中学习）
{history_text if history_text else "暂无"}

## 请从四个维度分析共性：
1. **技术面共性**：这些股票在被选中当天的均线排列、涨跌幅区间、量价特征有什么共同点？
2. **板块共性**：集中在哪些行业/概念？板块轮动有规律吗？
3. **形态共性**：被选中时的K线形态有什么共同特征？（突破/回踩/放量/缩量等）
4. **资金共性**：量比、换手率有什么共同区间？

## 输出（严格JSON）：
```json
{{
    "technical_common": "技术面共性（100-200字）",
    "sector_common": "板块共性（100-200字）",
    "pattern_common": "形态共性（100-200字）",
    "capital_common": "资金共性（100-200字）",
    "overall_summary": "综合选股规律总结（200-300字）",
    "predict_date": "{predict_date}",
    "predict_symbol": "6位股票代码",
    "predict_name": "股票名称",
    "predict_reason": "为什么预测这只（150-250字）"
}}
```

重点：
1. predict_symbol 只给出1只你最有把握的股票
2. 该股票必须是之前从未出现在序列中的新股票，不能重复历史选股"""

        messages = [
            {"role": "system", "content": "你是A股选股规律分析专家，擅长从每日选股序列中发现规律并预测。输出纯JSON。"},
            {"role": "user", "content": prompt}
        ]

        response = self.deepseek_client.call_api(messages, max_tokens=4000)
        return self._parse_json(response, predict_date)

    def _ai_verify(self, analysis: Dict, actual_symbol: str,
                   actual_name: str, is_hit: bool) -> Dict:
        """AI验证预测结果并提取规则"""

        prompt = f"""## 预测验证

### 原始分析
- 技术面共性: {analysis.get('technical_common', '')}
- 板块共性: {analysis.get('sector_common', '')}
- 形态共性: {analysis.get('pattern_common', '')}
- 资金共性: {analysis.get('capital_common', '')}
- 综合总结: {analysis.get('overall_summary', '')}

### 预测 vs 实际
- 预测日期: {analysis.get('predict_date', '')}
- 预测股票: {analysis.get('predict_symbol', '')} {analysis.get('predict_name', '')}
- 预测理由: {analysis.get('predict_reason', '')}
- 实际股票: {actual_symbol} {actual_name}
- 是否命中: {"✅ 命中" if is_hit else "❌ 未命中"}

### 请输出（JSON）：
```json
{{
    "feedback": "总结评价：哪些分析准确、哪些偏差、如何改进（150-200字）",
    "new_rules": [
        "从本次验证学到的规则1（一句话）",
        "规则2"
    ]
}}
```
如果命中，提炼有效规则；如果未命中，提炼修正/避免的规则。"""

        messages = [
            {"role": "system", "content": "你是量化策略复盘专家，从预测验证中提炼可复用的规则。输出纯JSON。"},
            {"role": "user", "content": prompt}
        ]

        response = self.deepseek_client.call_api(messages, max_tokens=2000)

        try:
            json_str = self._extract_json_str(response)
            return json.loads(json_str)
        except (json.JSONDecodeError, IndexError):
            return {"feedback": response, "new_rules": []}

    # ─────────── 工具方法 ───────────

    def _parse_json(self, response: str, predict_date: str) -> Dict:
        """解析AI返回的JSON"""
        try:
            json_str = self._extract_json_str(response)
            result = json.loads(json_str)
            if "predict_date" not in result:
                result["predict_date"] = predict_date
            return result
        except (json.JSONDecodeError, IndexError):
            return {
                "technical_common": response,
                "sector_common": "",
                "pattern_common": "",
                "capital_common": "",
                "overall_summary": "",
                "predict_date": predict_date,
                "predict_symbol": "",
                "predict_name": "",
                "predict_reason": "",
            }

    def _update_rules_confidence(self, analysis: Dict, actual_symbol: str, is_hit: bool):
        """根据验证结果更新所有规则的置信度。

        策略：每轮验证时所有规则都参与更新。
        多轮后好规则hit多于miss → 置信度上升；坏规则反之 → 被淘汰。
        这是最简单有效的收敛机制。
        """
        rules = db.get_learning_rules()
        if not rules:
            return

        for rule in rules:
            db.update_learning_rule(rule["id"], hit=is_hit)

    @staticmethod
    def _extract_json_str(text: str) -> str:
        """从文本中提取JSON字符串"""
        if "```json" in text:
            return text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            return text.split("```")[1].split("```")[0].strip()
        return text.strip()
