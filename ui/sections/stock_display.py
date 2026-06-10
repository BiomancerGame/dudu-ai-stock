"""股票信息、图表、分析师报告、团队讨论、最终决策、示例界面 — 从 app.py 抽取。"""

import time
import streamlit as st
import plotly.graph_objects as go
from pdf_generator import display_pdf_export_section
from privacy_utils import is_mask_stock_identity_enabled, mask_stock_code, mask_stock_name


def display_stock_identity(symbol, name):
    if is_mask_stock_identity_enabled():
        return mask_stock_code(symbol), mask_stock_name(name)
    return str(symbol or ""), str(name or "")


def check_api_key():
    """检查API密钥是否配置"""
    try:
        import config
        return bool(config.DEEPSEEK_API_KEY and config.DEEPSEEK_API_KEY.strip())
    except Exception:
        return False


def display_stock_info(stock_info, indicators):
    """显示股票基本信息"""
    display_symbol, display_name = display_stock_identity(
        stock_info.get('symbol', 'N/A'),
        stock_info.get('name', 'N/A')
    )
    st.subheader(f"📊 {display_name} ({display_symbol})")

    # 基本信息卡片
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        current_price = stock_info.get('current_price', 'N/A')
        st.metric("当前价格", f"{current_price}")

    with col2:
        change_percent = stock_info.get('change_percent', 'N/A')
        if isinstance(change_percent, (int, float)):
            st.metric("涨跌幅", f"{change_percent:.2f}%", f"{change_percent:.2f}%")
        else:
            st.metric("涨跌幅", f"{change_percent}")

    with col3:
        pe_ratio = stock_info.get('pe_ratio', 'N/A')
        st.metric("市盈率", f"{pe_ratio}")

    with col4:
        pb_ratio = stock_info.get('pb_ratio', 'N/A')
        st.metric("市净率", f"{pb_ratio}")

    with col5:
        market_cap = stock_info.get('market_cap', 'N/A')
        if isinstance(market_cap, (int, float)):
            market_cap_str = f"{market_cap/1e9:.2f}B" if market_cap > 1e9 else f"{market_cap/1e6:.2f}M"
            st.metric("市值", market_cap_str)
        else:
            st.metric("市值", f"{market_cap}")

    # 技术指标
    if indicators and not isinstance(indicators, dict) or "error" not in indicators:
        st.subheader("📈 关键技术指标")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            rsi = indicators.get('rsi', 'N/A')
            if isinstance(rsi, (int, float)):
                rsi_color = "normal"
                if rsi > 70:
                    rsi_color = "inverse"
                elif rsi < 30:
                    rsi_color = "off"
                st.metric("RSI", f"{rsi:.2f}")
            else:
                st.metric("RSI", f"{rsi}")

        with col2:
            ma20 = indicators.get('ma20', 'N/A')
            if isinstance(ma20, (int, float)):
                st.metric("MA20", f"{ma20:.2f}")
            else:
                st.metric("MA20", f"{ma20}")

        with col3:
            volume_ratio = indicators.get('volume_ratio', 'N/A')
            if isinstance(volume_ratio, (int, float)):
                st.metric("量比", f"{volume_ratio:.2f}")
            else:
                st.metric("量比", f"{volume_ratio}")

        with col4:
            macd = indicators.get('macd', 'N/A')
            if isinstance(macd, (int, float)):
                st.metric("MACD", f"{macd:.4f}")
            else:
                st.metric("MACD", f"{macd}")

def display_stock_chart(stock_data, stock_info):
    """显示股票图表"""
    st.subheader("📈 股价走势图")

    # 脱敏处理标题
    _, display_name = display_stock_identity(
        stock_info.get('symbol', ''),
        stock_info.get('name', '')
    )
    chart_title = f"{display_name} 股价走势" if display_name else "股价走势"

    # 创建蜡烛图
    fig = go.Figure()

    # 添加蜡烛图（涨红跌绿）
    fig.add_trace(go.Candlestick(
        x=stock_data.index,
        open=stock_data['Open'],
        high=stock_data['High'],
        low=stock_data['Low'],
        close=stock_data['Close'],
        name="K线",
        increasing_line_color='#ef4444',
        increasing_fillcolor='#ef4444',
        decreasing_line_color='#22c55e',
        decreasing_fillcolor='#22c55e',
    ))

    # 添加移动平均线
    if 'MA5' in stock_data.columns:
        fig.add_trace(go.Scatter(
            x=stock_data.index,
            y=stock_data['MA5'],
            name="MA5",
            line=dict(color='#f59e0b', width=1.2)
        ))

    if 'MA20' in stock_data.columns:
        fig.add_trace(go.Scatter(
            x=stock_data.index,
            y=stock_data['MA20'],
            name="MA20",
            line=dict(color='#3b82f6', width=1.2)
        ))

    if 'MA60' in stock_data.columns:
        fig.add_trace(go.Scatter(
            x=stock_data.index,
            y=stock_data['MA60'],
            name="MA60",
            line=dict(color='#a855f7', width=1.2)
        ))

    # 布林带
    if 'BB_upper' in stock_data.columns and 'BB_lower' in stock_data.columns:
        fig.add_trace(go.Scatter(
            x=stock_data.index,
            y=stock_data['BB_upper'],
            name="布林上轨",
            line=dict(color='#f87171', width=1, dash='dash')
        ))
        fig.add_trace(go.Scatter(
            x=stock_data.index,
            y=stock_data['BB_lower'],
            name="布林下轨",
            line=dict(color='#4ade80', width=1, dash='dash'),
            fill='tonexty',
            fillcolor='rgba(74,222,128,0.08)'
        ))

    fig.update_layout(
        title=dict(text=chart_title, font=dict(size=15)),
        xaxis_title="日期",
        yaxis_title="价格",
        height=520,
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=50, r=20, t=60, b=40),
        xaxis_rangeslider_visible=False,
        plot_bgcolor='#fafafa',
        paper_bgcolor='#ffffff',
        xaxis=dict(gridcolor='#f0f0f0', showgrid=True),
        yaxis=dict(gridcolor='#f0f0f0', showgrid=True),
    )

    # 生成唯一的key
    chart_key = f"main_stock_chart_{stock_info.get('symbol', 'unknown')}_{int(time.time())}"
    st.plotly_chart(fig, use_container_width=True, config={'responsive': True}, key=chart_key)

    # 成交量图
    if 'Volume' in stock_data.columns:
        # 按涨跌着色
        colors = []
        for i in range(len(stock_data)):
            if i == 0:
                colors.append('#ef4444')
            elif stock_data['Close'].iloc[i] >= stock_data['Close'].iloc[i - 1]:
                colors.append('#ef4444')
            else:
                colors.append('#22c55e')

        fig_volume = go.Figure()
        fig_volume.add_trace(go.Bar(
            x=stock_data.index,
            y=stock_data['Volume'],
            name="成交量",
            marker_color=colors,
            marker_line_width=0,
        ))

        fig_volume.update_layout(
            title=dict(text="成交量", font=dict(size=13)),
            xaxis_title="日期",
            yaxis_title="成交量",
            height=180,
            margin=dict(l=50, r=20, t=35, b=30),
            plot_bgcolor='#fafafa',
            paper_bgcolor='#ffffff',
            xaxis=dict(gridcolor='#f0f0f0', showgrid=True),
            yaxis=dict(gridcolor='#f0f0f0', showgrid=True),
            bargap=0.1,
        )

        # 生成唯一的key
        volume_key = f"volume_chart_{stock_info.get('symbol', 'unknown')}_{int(time.time())}"
        st.plotly_chart(fig_volume, use_container_width=True, config={'responsive': True}, key=volume_key)

def display_agents_analysis(agents_results):
    """显示各分析师报告"""
    st.subheader("🤖 AI分析师团队报告")

    # 创建标签页
    tab_names = []
    tab_contents = []

    for agent_key, agent_result in agents_results.items():
        agent_name = agent_result.get('agent_name', '未知分析师')
        tab_names.append(agent_name)
        tab_contents.append(agent_result)

    tabs = st.tabs(tab_names)

    for i, tab in enumerate(tabs):
        with tab:
            agent_result = tab_contents[i]

            # 分析师信息
            st.markdown(f"""
            <div class="agent-card">
                <h4>👨‍💼 {agent_result.get('agent_name', '未知')}</h4>
                <p><strong>职责：</strong>{agent_result.get('agent_role', '未知')}</p>
                <p><strong>关注领域：</strong>{', '.join(agent_result.get('focus_areas', []))}</p>
                <p><strong>分析时间：</strong>{agent_result.get('timestamp', '未知')}</p>
            </div>
            """, unsafe_allow_html=True)

            # 分析报告
            st.markdown('<div class="report-block"><div class="report-heading">📄 分析报告</div>', unsafe_allow_html=True)
            st.write(agent_result.get('analysis', '暂无分析'))
            st.markdown('</div>', unsafe_allow_html=True)

def display_team_discussion(discussion_result):
    """显示团队讨论"""
    st.subheader("🤝 分析团队讨论")

    st.markdown("""
    <div class="agent-card">
        <h4>💭 团队综合讨论</h4>
        <p>各位分析师正在就该股票进行深入讨论，整合不同维度的分析观点...</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="report-block"><div class="report-heading">🤝 团队讨论结论</div>', unsafe_allow_html=True)
    st.write(discussion_result)
    st.markdown('</div>', unsafe_allow_html=True)

def display_final_decision(final_decision, stock_info, agents_results=None, discussion_result=None):
    """显示最终投资决策"""
    st.subheader("📋 最终投资决策")

    if isinstance(final_decision, dict) and "decision_text" not in final_decision:
        # JSON格式的决策
        col1, col2 = st.columns([1, 2])

        with col1:
            # 投资评级
            rating = final_decision.get('rating', '未知')
            rating_color = {"买入": "🟢", "持有": "🟡", "卖出": "🔴"}.get(rating, "⚪")

            st.markdown(f"""
            <div class="decision-card">
                <h3 style="text-align: center;">{rating_color} {rating}</h3>
                <h4 style="text-align: center;">投资评级</h4>
            </div>
            """, unsafe_allow_html=True)

            # 关键指标
            confidence = final_decision.get('confidence_level', 'N/A')
            st.metric("信心度", f"{confidence}/10")

            target_price = final_decision.get('target_price', 'N/A')
            st.metric("目标价格", f"{target_price}")

            position_size = final_decision.get('position_size', 'N/A')
            st.metric("建议仓位", f"{position_size}")

        with col2:
            # 详细建议
            st.markdown('<div class="decision-summary">', unsafe_allow_html=True)
            st.markdown("**🎯 操作建议**")
            st.write(final_decision.get('operation_advice', '暂无建议'))
            st.markdown("**📍 关键位置**")
            col2_1, col2_2 = st.columns(2)

            with col2_1:
                st.write(f"**进场区间:** {final_decision.get('entry_range', 'N/A')}")
                st.write(f"**止盈位:** {final_decision.get('take_profit', 'N/A')}")

            with col2_2:
                st.write(f"**止损位:** {final_decision.get('stop_loss', 'N/A')}")
                st.write(f"**持有周期:** {final_decision.get('holding_period', 'N/A')}")
            st.markdown('</div>', unsafe_allow_html=True)

        # 风险提示
        risk_warning = final_decision.get('risk_warning', '')
        if risk_warning:
            st.markdown(f"""
            <div class="warning-card">
                <h4>⚠️ 风险提示</h4>
                <p>{risk_warning}</p>
            </div>
            """, unsafe_allow_html=True)

    else:
        # 文本格式的决策
        decision_text = final_decision.get('decision_text', str(final_decision))
        st.write(decision_text)

    # 添加PDF导出功能
    st.markdown("---")
    if agents_results and discussion_result:
        display_pdf_export_section(stock_info, agents_results, discussion_result, final_decision)
    else:
        st.warning("⚠️ PDF导出功能需要完整的分析数据")

def show_example_interface():
    """显示示例界面"""
    st.markdown("""
    <div class="section-title">
        <div>
            <h2>使用参考</h2>
            <p>还没输入标的时，可以先看这里确认代码格式和分析覆盖范围。</p>
        </div>
        <span class="section-kicker">Guide</span>
    </div>
    <div class="support-grid">
        <div class="support-card">
            <strong>可输入的代码</strong>
            <span>A股：000001、600036、600519</span>
            <span>港股：00700、09988、01810</span>
            <span>美股：AAPL、MSFT、NVDA</span>
        </div>
        <div class="support-card">
            <strong>会输出什么</strong>
            <span>股票基础信息、K线与指标图、各分析师报告、团队讨论、最终评级、仓位和风控建议。</span>
        </div>
        <div class="support-card">
            <strong>市场覆盖</strong>
            <span>A股覆盖技术、财务、资金、情绪和新闻；港股覆盖技术与 21 项财务指标；美股覆盖技术和财务数据。</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not check_api_key():
        st.warning("首次运行需要配置 DeepSeek API Key，请在 .env 中设置 DEEPSEEK_API_KEY。")
