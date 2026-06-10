"""批量分析结果展示 — 从 app.py 抽取。"""

import streamlit as st
from privacy_utils import mask_dataframe_stock_identity
from ui.sections.stock_display import (
    display_stock_identity,
    display_stock_info,
    display_stock_chart,
    display_agents_analysis,
    display_team_discussion,
    display_final_decision,
)
from services.analysis import get_stock_data


def display_batch_analysis_results(results, period):
    """显示批量分析结果（对比视图）"""

    st.subheader("📊 批量分析结果对比")

    # 统计信息
    total = len(results)
    success_results = [r for r in results if r['success']]
    failed_results = [r for r in results if not r['success']]
    saved_count = sum(1 for r in results if r.get('saved_to_db', False))

    # 显示统计
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总数", total)
    with col2:
        st.metric("成功", len(success_results), delta=None, delta_color="normal")
    with col3:
        st.metric("失败", len(failed_results), delta=None, delta_color="inverse")
    with col4:
        st.metric("已保存", saved_count, delta=None, delta_color="normal")

    # 提示信息
    if saved_count > 0:
        st.info(f"💾 已有 {saved_count} 只股票的分析结果保存到历史记录，可在侧边栏点击「📖 历史记录」查看")

    st.markdown("---")

    # 失败的股票列表
    if failed_results:
        with st.expander(f"❌ 查看失败的 {len(failed_results)} 只股票", expanded=False):
            for result in failed_results:
                st.error(f"**{result['symbol']}**: {result.get('error', '未知错误')}")

    # 保存失败的股票列表
    save_failed_results = [r for r in success_results if not r.get('saved_to_db', False)]
    if save_failed_results:
        with st.expander(f"⚠️ 查看分析成功但保存失败的 {len(save_failed_results)} 只股票", expanded=False):
            for result in save_failed_results:
                db_error = result.get('db_error', '未知错误')
                st.warning(f"**{result['symbol']} - {result['stock_info'].get('name', 'N/A')}**: {db_error}")

    # 成功的股票分析结果
    if not success_results:
        st.warning("⚠️ 没有成功分析的股票")
        return

    # 创建对比视图选项
    view_mode = st.radio(
        "显示模式",
        ["对比表格", "详细卡片"],
        horizontal=True,
        help="对比表格：横向对比多只股票；详细卡片：逐个查看详细分析"
    )

    if view_mode == "对比表格":
        # 表格对比视图
        display_comparison_table(success_results)
    else:
        # 详细卡片视图
        display_detailed_cards(success_results, period)

def display_comparison_table(results):
    """显示对比表格"""
    import pandas as pd

    st.subheader("📋 股票对比表格")

    # 构建对比数据
    comparison_data = []
    for result in results:
        stock_info = result['stock_info']
        indicators = result.get('indicators', {})
        final_decision = result['final_decision']

        # 解析评级
        if isinstance(final_decision, dict):
            rating = final_decision.get('rating', 'N/A')
            confidence = final_decision.get('confidence_level', 'N/A')
            target_price = final_decision.get('target_price', 'N/A')
        else:
            rating = 'N/A'
            confidence = 'N/A'
            target_price = 'N/A'

        # 确保信心度为字符串类型，避免类型混合导致的序列化错误
        if isinstance(confidence, (int, float)):
            confidence = str(confidence)

        row = {
            '股票代码': stock_info.get('symbol', 'N/A'),
            '股票名称': stock_info.get('name', 'N/A'),
            '当前价格': stock_info.get('current_price', 'N/A'),
            '涨跌幅(%)': stock_info.get('change_percent', 'N/A'),
            '市盈率': stock_info.get('pe_ratio', 'N/A'),
            '市净率': stock_info.get('pb_ratio', 'N/A'),
            'RSI': indicators.get('rsi', 'N/A'),
            'MACD': indicators.get('macd', 'N/A'),
            '投资评级': rating,
            '信心度': confidence,
            '目标价格': target_price
        }
        comparison_data.append(row)

    # 创建DataFrame
    df = pd.DataFrame(comparison_data)

    # 应用样式
    # 显示表格（不使用样式，避免matplotlib导入问题）
    st.dataframe(
        mask_dataframe_stock_identity(df),
        width='stretch',
        height=400
    )

    # 添加评级说明
    st.caption("💡 投资评级说明：强烈买入 > 买入 > 持有 > 卖出 > 强烈卖出")

    # 添加筛选功能
    st.markdown("---")
    st.subheader("🔍 快速筛选")

    col1, col2 = st.columns(2)
    with col1:
        rating_filter = st.multiselect(
            "按评级筛选",
            options=df['投资评级'].unique().tolist(),
            default=df['投资评级'].unique().tolist()
        )

    with col2:
        # 按涨跌幅排序
        sort_by = st.selectbox(
            "排序方式",
            ["默认", "涨跌幅降序", "涨跌幅升序", "信心度降序", "RSI降序"]
        )

    # 应用筛选
    filtered_df = df[df['投资评级'].isin(rating_filter)]

    # 应用排序
    if sort_by == "涨跌幅降序":
        filtered_df = filtered_df.sort_values('涨跌幅(%)', ascending=False)
    elif sort_by == "涨跌幅升序":
        filtered_df = filtered_df.sort_values('涨跌幅(%)', ascending=True)
    elif sort_by == "信心度降序":
        filtered_df = filtered_df.sort_values('信心度', ascending=False)
    elif sort_by == "RSI降序":
        filtered_df = filtered_df.sort_values('RSI', ascending=False)

    if not filtered_df.empty:
        st.dataframe(mask_dataframe_stock_identity(filtered_df), width='stretch')
    else:
        st.info("没有符合条件的股票")

def display_detailed_cards(results, period):
    """显示详细卡片视图"""

    st.subheader("📇 详细分析卡片")

    # 选择要查看的股票
    stock_options = [
        f"{display_stock_identity(r['stock_info']['symbol'], r['stock_info']['name'])[0]} - "
        f"{display_stock_identity(r['stock_info']['symbol'], r['stock_info']['name'])[1]}"
        for r in results
    ]
    selected_stock = st.selectbox("选择股票", options=stock_options)

    # 找到对应的结果
    selected_index = stock_options.index(selected_stock)
    result = results[selected_index]

    # 显示详细分析
    stock_info = result['stock_info']
    indicators = result['indicators']
    agents_results = result['agents_results']
    discussion_result = result['discussion_result']
    final_decision = result['final_decision']

    # 获取股票数据用于显示图表
    try:
        stock_info_current, stock_data, _ = get_stock_data(stock_info['symbol'], period)

        # 显示股票基本信息
        display_stock_info(stock_info, indicators)

        # 显示股票图表
        if stock_data is not None:
            display_stock_chart(stock_data, stock_info)

        # 显示各分析师报告
        display_agents_analysis(agents_results)

        # 显示团队讨论
        display_team_discussion(discussion_result)

        # 显示最终决策
        display_final_decision(final_decision, stock_info, agents_results, discussion_result)

    except Exception as e:
        st.error(f"显示详细信息时出错: {str(e)}")
