"""共性追踪 Streamlit UI

场景：用户每个交易日选一只股票（日期+代码+名称+买入价），
AI分析序列共性 → 预测下一交易日 → 验证 → 循环学习。
"""
from __future__ import annotations

import json
import streamlit as st
import pandas as pd

import commonality_tracker_db as db
from commonality_tracker import CommonalityTracker


def display_commonality_tracker():
    """共性追踪主界面"""
    st.markdown("## 🔗 共性追踪")
    st.caption("输入每日选股序列 → AI分析共性规律 → 预测下一交易日 → 验证反馈 → 循环优化")

    # 顶部统计
    stats = db.get_stats()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("历史选股", stats["pick_count"])
    c2.metric("分析轮次", stats["round_count"])
    c3.metric("验证次数", stats["verify_count"])
    c4.metric("命中率", f"{stats['hit_rate']:.0%}" if stats["verify_count"] > 0 else "—")
    c5.metric("学习规则", stats["rule_count"])

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📥 输入数据 & 预测", "🔄 批量学习", "✅ 验证结果", "📚 历史记录", "🧠 学习规则"])

    with tab1:
        _render_input_and_predict()
    with tab2:
        _render_batch_learn()
    with tab3:
        _render_verify()
    with tab4:
        _render_history()
    with tab5:
        _render_rules()


def _render_input_and_predict():
    """输入每日选股数据并分析预测"""

    # ═══ 快速预测：基于规则直接预测（不拉技术数据，秒出结果） ═══
    all_picks = db.get_all_picks()
    rules = db.get_learning_rules()
    if all_picks:
        st.markdown("### 🚀 快速预测（基于规则）")
        rule_count = len(rules)
        if rule_count > 0:
            st.caption(f"🧠 已积累 **{rule_count}** 条学习规则 + **{len(all_picks)}** 条选股记录，直接用规则预测，不拉技术数据")
        else:
            st.caption(f"数据库已有 **{len(all_picks)}** 条选股记录（暂无规则，将做完整分析）")

        next_date = st.text_input(
            "预测哪天的股票？",
            placeholder="如 4.22",
            key="ct_quick_predict_date"
        )

        if st.button("🔮 预测下一天", type="primary", key="btn_ct_quick_predict"):
            if not next_date or not next_date.strip():
                st.error("请填写预测日期")
            else:
                if rule_count > 0:
                    _do_quick_predict(next_date.strip())
                else:
                    # 没有规则时走完整分析
                    _do_predict_from_db(all_picks, next_date.strip())

        st.markdown("---")

    # ═══ 完整输入：粘贴新数据 ═══
    with st.expander("📥 粘贴新的选股数据（首次或追加）", expanded=not bool(all_picks)):
        st.markdown("格式：**每行一条**，`日期 名称 代码 买入价`，用空格/Tab分隔。")

        example = """3.02 龙磁科技 300835 97.48
3.03 聚飞光电 300303 9.42
3.04 嘉伟新能 300317 5.74
3.05 精测电子 300567 146.67
3.06 智立方 301312 106.66"""

        picks_text = st.text_area(
            "粘贴选股数据",
            placeholder=example,
            height=300,
            key="ct_picks_input"
        )

        predict_date = st.text_input(
            "预测哪天的股票？（如 3.25）",
            placeholder="3.25",
            key="ct_predict_date"
        )

        if st.button("🚀 保存数据 & 分析预测", type="primary", key="btn_ct_analyze"):
            picks = _parse_picks_table(picks_text)
            if len(picks) < 3:
                st.error("至少需要3条选股记录才能分析共性")
            elif not predict_date.strip():
                st.error("请填写要预测的日期")
            else:
                # 保存新数据到DB后用全部数据预测
                db.save_picks(picks)
                updated_picks = db.get_all_picks()
                all_data = [
                    {"date": p["pick_date"], "symbol": p["symbol"],
                     "name": p.get("name", ""), "price": p.get("entry_price", 0)}
                    for p in updated_picks
                ]
                _do_predict(all_data, predict_date.strip())

    # 显示最新结果
    if "ct_latest_result" in st.session_state:
        _render_result(st.session_state["ct_latest_result"])


def _render_batch_learn():
    """批量学习：一次性输入多条数据，系统自动逐条学习收敛规则"""
    st.markdown("### 🔄 批量学习模式")
    st.caption("输入一批历史选股数据（按日期正序），系统自动：提取特征 → 预测下一只 → 对比答案 → 更新规则。快速收敛！")

    # 清空旧规则按钮
    rules = db.get_learning_rules()
    if rules:
        with st.expander(f"⚠️ 当前有 {len(rules)} 条规则（可选：清空后重新学习）"):
            st.warning("如果旧规则全是50%未收敛，建议清空后重新批量学习")
            if st.button("🗑️ 清空所有规则，从头学习", key="btn_clear_rules"):
                from commonality_tracker_db import get_conn, DB_PATH
                with get_conn(DB_PATH) as conn:
                    conn.execute("DELETE FROM learning_rules")
                st.success("已清空所有规则！现在可以重新批量学习。")
                st.rerun()

    example = """5.06 精测电子 300567
5.07 钧崴电子 301458
5.08 惠伦晶体 300460
5.09 聚飞光电 300303
5.12 龙磁科技 300835"""

    batch_text = st.text_area(
        "粘贴选股序列（每行：日期 名称 代码）",
        placeholder=example,
        height=250,
        key="ct_batch_input"
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        start_btn = st.button("🚀 开始批量学习", type="primary", key="btn_batch_learn")
    with col2:
        st.caption("前3条作为初始训练集，从第4条开始预测+验证")

    if start_btn:
        if not batch_text or not batch_text.strip():
            st.error("请粘贴选股数据")
            return

        # 解析输入
        picks = []
        for line in batch_text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 3:
                # 支持两种格式: "日期 名称 代码" 或 "日期 名称 代码 价格"
                date_str = parts[0]
                name = parts[1]
                symbol = parts[2]
                picks.append({"date": date_str, "symbol": symbol, "name": name})
            elif len(parts) == 2:
                date_str = parts[0]
                symbol = parts[1]
                picks.append({"date": date_str, "symbol": symbol, "name": ""})

        if len(picks) < 4:
            st.error("至少需要4条数据（前3条训练，第4条开始预测）")
            return

        st.info(f"共 {len(picks)} 条数据，前3条训练，将进行 {len(picks)-3} 轮预测学习")

        progress_bar = st.progress(0)
        status_text = st.empty()

        def emit(msg, pct):
            status_text.text(f"⏳ {msg}")
            progress_bar.progress(min(pct, 100) / 100)

        tracker = CommonalityTracker()
        result = tracker.batch_learn(picks, emit)

        if "error" in result:
            st.error(result["error"])
            return

        progress_bar.progress(1.0)
        status_text.text("✅ 批量学习完成！")

        # 展示结果
        st.markdown("---")
        st.markdown("### 📊 学习结果")

        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("总轮次", result["total_rounds"])
        rc2.metric("命中次数", result["hits"])
        rc3.metric("命中率", result["hit_rate"])

        st.metric("最终规则数", result["rules_count"])

        # 每轮详情
        st.markdown("#### 逐轮学习过程")
        for r in result.get("rounds", []):
            hit_icon = "✅" if r["is_hit"] else "❌"
            st.markdown(f"{hit_icon} **{r['date']}** — 预测:{r['predicted']} | 实际:{r['actual']}")
            if r.get("pattern"):
                st.caption(f"  模式: {r['pattern']}")
            if r.get("new_rules"):
                for nr in r["new_rules"]:
                    st.caption(f"  📝 新规则: {nr}")

        # 最终TOP规则
        top_rules = result.get("top_rules", [])
        if top_rules:
            st.markdown("#### 🏆 收敛后的TOP10规则")
            for i, tr in enumerate(top_rules):
                conf = tr["confidence"]
                bar = "█" * int(conf * 10) + "░" * (10 - int(conf * 10))
                st.markdown(f"{i+1}. [{conf:.0%}] {bar} {tr['content']}")


def _do_quick_predict(predict_date: str):
    """快速预测：基于规则直接预测，不拉技术数据"""
    st.info(f"⚡ 快速模式：基于学习规则预测 {predict_date} 的股票")

    progress_bar = st.progress(0)
    status_text = st.empty()

    def emit(msg, pct):
        status_text.text(f"⏳ {msg}")
        progress_bar.progress(min(pct, 100) / 100)

    tracker = CommonalityTracker()
    result = tracker.quick_predict(predict_date, emit)

    if "error" in result:
        st.error(result["error"])
        return

    progress_bar.progress(1.0)
    status_text.text("✅ 预测完成！")

    st.session_state["ct_latest_result"] = result
    st.rerun()


def _do_predict_from_db(all_picks: list, predict_date: str):
    """完整分析模式：拉技术数据做共性分析"""
    picks_data = [
        {"date": p["pick_date"], "symbol": p["symbol"],
         "name": p.get("name", ""), "price": p.get("entry_price", 0)}
        for p in all_picks
    ]
    _do_predict(picks_data, predict_date)


def _do_predict(picks_data: list, predict_date: str):
    """执行预测的通用流程"""
    st.info(f"📊 使用 {len(picks_data)} 条记录分析共性，预测 {predict_date} 的股票")

    progress_bar = st.progress(0)
    status_text = st.empty()

    def emit(msg, pct):
        status_text.text(f"⏳ {msg}")
        progress_bar.progress(min(pct, 100) / 100)

    tracker = CommonalityTracker()
    result = tracker.analyze_and_predict(picks_data, predict_date, emit)

    progress_bar.progress(1.0)
    status_text.text("✅ 分析完成！")

    st.session_state["ct_latest_result"] = result
    st.rerun()


def _render_result(result: dict):
    """渲染分析预测结果"""
    st.markdown("---")

    is_quick = result.get("mode") == "quick"

    if is_quick:
        # 快速模式：不显示四维度，直接显示预测
        st.markdown("### ⚡ 规则驱动预测结果")
    else:
        # 完整模式：显示四维度共性分析
        st.markdown("### 🔍 共性分析结果")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**📈 技术面共性**")
            st.markdown(result.get("technical_common", "—"))
            st.markdown("**📐 形态共性**")
            st.markdown(result.get("pattern_common", "—"))
        with col2:
            st.markdown("**🏭 板块共性**")
            st.markdown(result.get("sector_common", "—"))
            st.markdown("**💰 资金共性**")
            st.markdown(result.get("capital_common", "—"))

        st.markdown("**🎯 综合规律**")
        st.success(result.get("overall_summary", "—"))
        st.markdown("---")

    # 预测结果（重点突出）
    st.markdown("### 🔮 预测结果")
    pred_col1, pred_col2, pred_col3 = st.columns([1, 1, 2])
    with pred_col1:
        st.metric("预测日期", result.get("predict_date", "—"))
    with pred_col2:
        symbol = result.get("predict_symbol", "—")
        name = result.get("predict_name", "")
        st.metric("预测股票", f"{symbol} {name}")
    with pred_col3:
        st.markdown(f"**预测理由：** {result.get('predict_reason', '—')}")

    # 快速模式显示详细信息
    if is_quick:
        # 数据验证结论
        data_check = result.get("data_check", "")
        if data_check:
            st.info(f"📋 **数据验证：** {data_check}")

        applied = result.get("applied_rules", [])
        confidence = result.get("confidence", "")
        if confidence:
            st.markdown(f"**预测置信度：** {confidence}")
        if applied:
            st.markdown("**本次应用的规则：**")
            for r in applied:
                st.markdown(f"- ✅ {r}")

        market_basis = result.get("market_basis", "")
        if market_basis:
            st.markdown(f"**市场数据依据：** {market_basis}")

        # 显示最终选中股票的真实行情
        real_data = result.get("real_data", {})
        if real_data and not real_data.get("data_error"):
            st.markdown("---")
            st.markdown("### 📊 选中股票真实行情（系统查询）")
            rd_cols = st.columns(4)
            rd_cols[0].metric("现价", f"¥{real_data.get('current_price', '—')}")
            rd_cols[1].metric("1日涨跌", f"{real_data.get('change_1d', '—')}%")
            rd_cols[2].metric("5日涨跌", f"{real_data.get('change_5d', '—')}%")
            rd_cols[3].metric("20日涨跌", f"{real_data.get('change_20d', '—')}%")

            rd_cols2 = st.columns(4)
            rd_cols2[0].metric("MA5", f"¥{real_data.get('ma5', '—')}")
            rd_cols2[1].metric("MA20", f"¥{real_data.get('ma20', '—')}")
            rd_cols2[2].metric("距MA20", f"{real_data.get('dist_ma20', '—')}%")
            rd_cols2[3].metric("量比", real_data.get("vol_ratio", "—"))

            # 资金流向
            fund_dir = real_data.get("fund_direction", "")
            if fund_dir:
                rd_cols3 = st.columns(4)
                color = "🟢" if fund_dir == "净流入" else "🔴"
                rd_cols3[0].metric("资金方向", f"{color} {fund_dir}")
                rd_cols3[1].metric("净流入(万)", real_data.get("fund_net_inflow_amount", "—"))
                rd_cols3[2].metric("主买占比", f"{real_data.get('fund_buy_pct', '—')}%")
                rd_cols3[3].metric("行业", real_data.get("industry", "—"))
            else:
                industry = real_data.get("industry", "")
                if industry:
                    st.markdown(f"**所属行业：** {industry}")

        # 显示所有候选股票对比
        candidates = result.get("candidates", [])
        if candidates:
            with st.expander(f"📋 查看全部 {len(candidates)} 只候选股票的真实数据", expanded=False):
                for c in candidates:
                    sym = c.get("symbol", "?")
                    name = c.get("name", "?")
                    is_selected = (sym == result.get("predict_symbol", ""))
                    prefix = "✅ " if is_selected else "  "
                    st.markdown(f"**{prefix}{name} ({sym})**")
                    cc = st.columns(6)
                    cc[0].caption(f"现价: {c.get('current_price', '—')}")
                    cc[1].caption(f"MA20: {c.get('ma20', '—')}")
                    cc[2].caption(f"距MA20: {c.get('dist_ma20', '—')}%")
                    cc[3].caption(f"量比: {c.get('vol_ratio', '—')}")
                    cc[4].caption(f"资金: {c.get('fund_net_inflow_desc', c.get('fund_direction', '—'))}")
                    cc[5].caption(f"行业: {c.get('industry', '—')}")
                    reason = c.get("candidate_reason", "")
                    if reason:
                        st.caption(f"候选理由: {reason}")
                    st.markdown("---")

    if result.get("round_id"):
        st.caption(f"轮次ID: {result['round_id']}（验证时使用）")


def _render_verify():
    """验证预测结果"""
    st.markdown("### ✅ 验证预测")
    st.caption("输入实际结果，AI会对比预测并学习规则")

    rounds = db.get_all_rounds()
    if not rounds:
        st.info("暂无分析记录，请先进行共性分析")
        return

    # 选择轮次
    round_options = {
        f"[轮次{r['id']}] {r['data_range']} → 预测{r['predict_date']}: {r['predict_symbol']} {r.get('predict_name','')}": r['id']
        for r in rounds[:20]
    }
    selected_label = st.selectbox("选择要验证的预测", list(round_options.keys()), key="ct_verify_select")
    round_id = round_options[selected_label]

    # 显示该轮预测详情
    target = next((r for r in rounds if r["id"] == round_id), None)
    if target:
        st.markdown(f"**预测日期：** {target['predict_date']}")
        st.markdown(f"**预测股票：** {target['predict_symbol']} {target.get('predict_name', '')}")
        st.markdown(f"**预测理由：** {target.get('predict_reason', '')[:200]}")

    st.markdown("---")

    # 输入实际结果
    col1, col2 = st.columns(2)
    with col1:
        actual_symbol = st.text_input("实际股票代码", placeholder="300xxx", key="ct_actual_symbol")
    with col2:
        actual_name = st.text_input("实际股票名称（可选）", placeholder="xxx科技", key="ct_actual_name")

    if st.button("🔍 验证并学习", type="primary", key="btn_ct_verify"):
        if not actual_symbol or not actual_symbol.strip().isdigit():
            st.error("请输入有效的6位股票代码")
            return

        with st.spinner("AI正在验证并提取规则..."):
            tracker = CommonalityTracker()
            v_result = tracker.verify(round_id, actual_symbol.strip(), actual_name.strip())

        if "error" in v_result:
            st.error(v_result["error"])
            return

        # 存入session，这样页面重刷后仍能显示
        st.session_state["ct_verify_result"] = v_result
        st.rerun()

    # ═══ 验证结果展示（独立于按钮块，避免重刷丢失） ═══
    v_result = st.session_state.get("ct_verify_result")
    if v_result:
        st.markdown("---")
        if v_result["is_hit"]:
            st.success(f"🎉 **命中！** 预测 {v_result['predicted']} = 实际 {v_result['actual']}")
        else:
            st.warning(f"❌ **未命中** — 预测: {v_result['predicted']}，实际: {v_result['actual']}")

        st.markdown("**💡 AI反馈：**")
        st.markdown(v_result.get("feedback", ""))

        if v_result.get("new_rules"):
            st.markdown("**📝 新学到的规则：**")
            for rule in v_result["new_rules"]:
                st.markdown(f"- {rule}")

        st.info("💡 实际结果已自动加入数据库，下次预测会包含更多数据。")

        # ═══ 继续预测下一天 ═══
        st.markdown("---")
        st.markdown("### 🔮 继续预测下一天")
        next_predict = st.text_input(
            "下一个预测日期",
            placeholder="如 3.31",
            key="ct_next_predict_after_verify"
        )
        if st.button("🚀 继续预测", type="primary", key="btn_ct_continue_predict"):
            if not next_predict or not next_predict.strip():
                st.error("请填写下一个预测日期")
            else:
                st.session_state.pop("ct_verify_result", None)
                _do_quick_predict(next_predict.strip())


def _render_history():
    """历史分析记录"""
    st.markdown("### 📚 分析历史")

    # 已有选股数据
    picks = db.get_all_picks()
    if picks:
        st.markdown(f"#### 📋 每日选股记录 ({len(picks)}条)")
        df = pd.DataFrame(picks)
        display_cols = ["pick_date", "symbol", "name", "entry_price"]
        existing_cols = [c for c in display_cols if c in df.columns]
        if existing_cols:
            df_show = df[existing_cols].copy()
            df_show.columns = ["日期", "代码", "名称", "买入价"][:len(existing_cols)]
            st.dataframe(df_show, use_container_width=True, hide_index=True, height=300)

    # 分析轮次
    rounds = db.get_all_rounds()
    if rounds:
        st.markdown("#### 🔄 分析轮次")
        for r in rounds[:10]:
            with st.expander(f"轮次{r['id']} | {r['data_range']} → 预测{r['predict_date']}: {r['predict_symbol']}"):
                st.markdown(f"**技术面：** {r.get('technical_common', '')[:150]}")
                st.markdown(f"**板块：** {r.get('sector_common', '')[:150]}")
                st.markdown(f"**形态：** {r.get('pattern_common', '')[:150]}")
                st.markdown(f"**资金：** {r.get('capital_common', '')[:150]}")
                st.markdown(f"**预测：** {r['predict_symbol']} {r.get('predict_name','')} — {r.get('predict_reason','')[:200]}")

    # 验证记录
    verifications = db.get_verifications()
    if verifications:
        st.markdown("#### ✅ 验证记录")
        for v in verifications[:10]:
            hit_icon = "✅" if v["is_hit"] else "❌"
            st.markdown(f"{hit_icon} 预测 **{v['predict_symbol']}** → 实际 **{v['actual_symbol']}** {v.get('actual_name','')}")

    if not picks and not rounds:
        st.info("暂无数据，请先输入选股序列进行分析")

    # 清空按钮
    st.markdown("---")
    if st.button("🗑️ 清空所有数据（谨慎）", key="btn_ct_clear"):
        db.clear_all_picks()
        st.success("已清空选股记录")
        st.rerun()


def _render_rules():
    """学习规则库"""
    st.markdown("### 🧠 学习规则库")
    st.caption("每次验证后AI会自动提炼规则，供后续预测参考")

    rules = db.get_learning_rules()
    if rules:
        for r in rules:
            conf = r['confidence']
            icon = "🟢" if conf >= 0.7 else "🟡" if conf >= 0.4 else "🔴"
            st.markdown(
                f"{icon} **[{conf:.0%}]** {r['rule_content']} "
                f"_(命中{r['hit_times']}次, 未中{r['miss_times']}次)_"
            )
    else:
        st.info("暂无学习规则。完成「验证」后将自动积累。")


# ─────────── 工具函数 ───────────

def _parse_picks_table(text: str) -> list:
    """
    解析用户粘贴的选股表格，每行格式：日期 名称 代码 买入价
    支持空格/Tab分隔，兼容各种格式
    """
    if not text or not text.strip():
        return []

    picks = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # 用多种分隔符分割
        parts = line.replace("\t", " ").split()
        if len(parts) < 3:
            continue

        # 尝试识别各字段
        date_str = ""
        name = ""
        symbol = ""
        price = 0

        for part in parts:
            # 日期：含.的短字符串如 3.02
            if not date_str and "." in part and len(part) <= 5:
                try:
                    float(part)  # 验证是数字
                    date_str = part
                    continue
                except ValueError:
                    pass
            # 代码：6位数字
            if not symbol and part.isdigit() and len(part) == 6:
                symbol = part
                continue
            # 价格：纯数字（含小数）
            if not price:
                try:
                    val = float(part)
                    if val > 0 and not part.isdigit():
                        price = val
                        continue
                    elif val > 0 and len(part) != 6:
                        price = val
                        continue
                except ValueError:
                    pass
            # 名称：中文字符串
            if not name and not part.isdigit():
                try:
                    float(part)
                except ValueError:
                    name = part
                    continue

        if symbol and date_str:
            picks.append({
                "date": date_str,
                "symbol": symbol,
                "name": name,
                "price": price
            })

    return picks
