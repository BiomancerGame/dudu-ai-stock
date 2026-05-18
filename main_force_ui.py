#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主力选股UI模块
"""

import streamlit as st
from datetime import datetime, timedelta
from main_force_analysis import MainForceAnalyzer
from main_force_pdf_generator import display_report_download_section
from main_force_history_ui import display_batch_history
from privacy_utils import (
    is_mask_stock_identity_enabled,
    mask_dataframe_stock_identity,
    mask_stock_code,
    mask_stock_name,
)
import pandas as pd


def create_main_force_process_panel():
    st.markdown("### 🧭 主力选股分析过程")
    progress_bar = st.progress(0)
    status_text = st.empty()
    log_box = st.empty()
    logs = []

    def update(message, percent=None):
        timestamp = datetime.now().strftime("%H:%M:%S")
        logs.append(f"{timestamp} {message}")
        if percent is not None:
            progress_bar.progress(max(0, min(int(percent), 100)))
        status_text.info(message)
        with log_box.container():
            with st.expander("查看实时分析过程", expanded=True):
                st.markdown("\n".join(f"- {line}" for line in logs[-14:]))

    return progress_bar, status_text, update


def get_pattern_display(stock_data: dict, scores: dict) -> tuple:
    """统一形态分、等级、标签展示，避免推荐分与明细字段矛盾。"""
    raw_score = scores.get('technical_pattern', stock_data.get('形态评分', 0))
    try:
        score = max(0, min(100, int(float(raw_score))))
    except Exception:
        score = 0

    raw_level = stock_data.get('形态等级')
    raw_tags = stock_data.get('形态标签')

    if score >= 85:
        level = "强势形态"
        fallback_tags = "平台突破、量价配合、趋势确认"
    elif score >= 70:
        level = "形态良好"
        fallback_tags = "趋势向上、资金配合"
    elif score >= 55:
        level = "形态一般"
        fallback_tags = "有一定形态信号"
    elif score > 0:
        level = "弱信号"
        fallback_tags = "形态信号偏弱"
    else:
        level = raw_level or "无数据"
        fallback_tags = raw_tags or "无明显形态"

    if raw_level and raw_level not in ["无数据", "无明显形态"] and score < 85:
        level = raw_level

    tags = raw_tags if raw_tags and raw_tags not in ["无", "无明显形态"] else fallback_tags
    return score, level, tags


def display_main_force_selector():
    """显示主力选股界面"""

    # 检查是否触发批量分析（不立即删除标志）
    if st.session_state.get('main_force_batch_trigger'):
        run_main_force_batch_analysis()
        return

    # 检查是否查看历史记录
    if st.session_state.get('main_force_view_history'):
        display_batch_history()
        return

    # 页面标题和历史记录按钮
    col_title, col_history = st.columns([4, 1])
    with col_title:
        st.markdown("## 🎯 主力选股 - 智能筛选优质标的")
    with col_history:
        st.write("")  # 占位
        if st.button("📚 批量分析历史", width='content'):
            st.session_state.main_force_view_history = True
            st.rerun()

    st.markdown("---")

    st.markdown("""
    <style>
        .main-force-result-card {
            background: #fffdf8;
            border: 1px solid #e6dccb;
            border-radius: 8px;
            padding: 1rem 1.1rem;
            margin: 0.5rem 0 1rem;
            box-shadow: 0 3px 14px rgba(40, 32, 20, 0.06);
        }
        .main-force-score-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.55rem;
            margin: 0.7rem 0 1rem;
        }
        .main-force-score {
            background: #f8f2e6;
            border: 1px solid #e6d3ad;
            border-radius: 8px;
            padding: 0.65rem;
            text-align: center;
        }
        .main-force-score strong {
            display: block;
            color: #14253f;
            font-size: 1.25rem;
            line-height: 1.2;
        }
        .main-force-score span {
            color: #6f6a60;
            font-size: 0.78rem;
        }
        .main-force-score.overall {
            background: #213a5c;
            border-color: #213a5c;
        }
        .main-force-score.overall strong,
        .main-force-score.overall span {
            color: #fffdf8;
        }
        .main-force-section {
            background: #fbf7ee;
            border: 1px solid #ebe4d6;
            border-radius: 8px;
            padding: 0.85rem 0.95rem;
            min-height: 100%;
        }
        .main-force-section h4 {
            margin: 0 0 0.55rem;
            color: #172033;
            font-size: 1rem;
        }
        .main-force-report {
            background: #fffdf8;
            border: 1px solid #ebe4d6;
            border-radius: 8px;
            padding: 1rem;
            margin-top: 0.75rem;
        }
        .main-force-report h3 {
            margin-top: 0;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.25rem;
            padding: 0.3rem;
            background: #fffdf8;
            border: 1px solid #ebe4d6;
            border-radius: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            min-height: 40px;
            padding: 0 1rem;
            border-radius: 6px;
            font-size: 0.95rem;
        }
        .stTabs [aria-selected="true"] {
            background: #f8edd7 !important;
            color: #14253f !important;
            border: 1px solid #d8b56f !important;
        }
        .main-force-logic {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 0.75rem 0 1rem;
        }
        .main-force-card {
            background: #fffdf8;
            border: 1px solid #ebe4d6;
            border-radius: 8px;
            padding: 0.9rem 1rem;
            min-height: 116px;
            box-shadow: 0 2px 10px rgba(40, 32, 20, 0.05);
        }
        .main-force-card.primary {
            background: linear-gradient(180deg, #fffdf8 0%, #f8edd7 100%);
            border-left: 4px solid #b88736;
        }
        .main-force-card strong {
            display: block;
            color: #172033;
            font-size: 0.96rem;
            margin-bottom: 0.35rem;
        }
        .main-force-card span {
            display: block;
            color: #6f6a60;
            font-size: 0.86rem;
            line-height: 1.55;
        }
        .main-force-note {
            background: #fff7e8;
            border: 1px solid #ead2a4;
            border-left: 4px solid #b88736;
            border-radius: 8px;
            color: #57401d;
            padding: 0.75rem 0.95rem;
            line-height: 1.6;
            margin-bottom: 1rem;
        }
        @media (max-width: 900px) {
            .main-force-logic,
            .main-force-score-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
    <div class="main-force-note">
        <strong>选股逻辑：</strong>先找主力资金净流入明显的个股，再过滤过热和市值不合适的标的，
        同时通过所属行业观察资金集中方向，最后由 AI 分析师团队综合精选。
    </div>
    <div class="main-force-logic">
        <div class="main-force-card primary">
            <strong>1. 资金入口</strong>
            <span>使用问财获取指定日期以来主力资金净流入靠前的股票，形成初始候选池。</span>
        </div>
        <div class="main-force-card">
            <strong>2. 防追高过滤</strong>
            <span>限制区间涨跌幅，默认过滤涨幅过高的股票，避免资金已经兑现后的追高风险。</span>
        </div>
        <div class="main-force-card">
            <strong>3. 市值与风险过滤</strong>
            <span>按市值范围筛选，并排除 ST、科创等不符合当前策略偏好的股票。</span>
        </div>
        <div class="main-force-card">
            <strong>4. 板块与 AI 精选</strong>
            <span>按行业观察资金集中度，结合资金面、行业面、基本面报告，精选最终标的。</span>
        </div>
    </div>
    <div class="main-force-note">
        <strong>形态加分：</strong>候选股会额外计算均线多头、20/60日突破、放量、MACD动能、回踩MA20企稳、RSI健康度等形态条件。
        形态用于加分和辅助排序，不会直接把资金强但形态未确认的股票一刀切过滤。
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # 参数设置
    col1, col2, col3 = st.columns(3)

    with col1:
        date_option = st.selectbox(
            "选择时间区间",
            ["最近3个月", "最近6个月", "最近1年", "自定义日期"]
        )

        if date_option == "最近3个月":
            days_ago = 90
            start_date = None
        elif date_option == "最近6个月":
            days_ago = 180
            start_date = None
        elif date_option == "最近1年":
            days_ago = 365
            start_date = None
        else:
            custom_date = st.date_input(
                "选择开始日期",
                value=datetime.now() - timedelta(days=90)
            )
            start_date = f"{custom_date.year}年{custom_date.month}月{custom_date.day}日"
            days_ago = None

    with col2:
        final_n = st.slider(
            "最终精选数量",
            min_value=3,
            max_value=10,
            value=5,
            step=1,
            help="最终推荐的股票数量"
        )

    with col3:
        st.info("💡 系统将获取前100名股票，进行整体分析后精选优质标的")

    # 高级选项
    with st.expander("⚙️ 高级筛选参数"):
        col1, col2, col3 = st.columns(3)

        with col1:
            max_change = st.number_input(
                "最大涨跌幅(%)",
                min_value=5.0,
                max_value=200.0,
                value=30.0,
                step=5.0,
                help="过滤掉涨幅过高的股票，避免追高"
            )

        with col2:
            min_cap = st.number_input(
                "最小市值(亿)",
                min_value=10.0,
                max_value=500.0,
                value=50.0,
                step=10.0
            )

        with col3:
            max_cap = st.number_input(
                "最大市值(亿)",
                min_value=50.0,
                max_value=50000.0,
                value=5000.0,
                step=100.0
            )

    st.markdown("---")

    # 开始分析按钮（使用.env中配置的默认模型）
    is_running = st.session_state.get('main_force_analysis_running', False)
    button_label = "⏳ 主力选股分析中..." if is_running else "🚀 开始主力选股"
    start_clicked = st.button(
        button_label,
        type="primary",
        width='content',
        disabled=is_running,
        key="main_force_start_button"
    )

    if start_clicked:
        st.session_state.main_force_analysis_running = True

        progress_bar, status_text, update_process = create_main_force_process_panel()
        update_process("开始主力选股分析", 3)

        # 创建分析器（使用默认模型）
        analyzer = MainForceAnalyzer()

        # 运行分析
        result = analyzer.run_full_analysis(
            start_date=start_date,
            days_ago=days_ago,
            final_n=final_n,
            max_range_change=max_change,
            min_market_cap=min_cap,
            max_market_cap=max_cap,
            progress_callback=update_process
        )

        # 保存结果到session_state
        st.session_state.main_force_result = result
        st.session_state.main_force_analyzer = analyzer
        st.session_state.main_force_analysis_running = False

        # 显示结果
        if result['success']:
            update_process("主力选股分析完成", 100)
            st.success(f"✅ 分析完成！共筛选出 {len(result['final_recommendations'])} 只优质标的")
            status_text.empty()
            progress_bar.empty()
            st.rerun()
        else:
            update_process(f"分析失败：{result.get('error', '未知错误')}", None)
            st.error(f"❌ 分析失败: {result.get('error', '未知错误')}")
            st.session_state.main_force_analysis_running = False

    # 显示分析结果
    if 'main_force_result' in st.session_state:
        result = st.session_state.main_force_result

        if result['success']:
            display_analysis_results(result, st.session_state.get('main_force_analyzer'))

def display_analysis_results(result: dict, analyzer):
    """显示分析结果"""

    st.markdown("---")
    st.markdown("## 📊 分析结果")

    # 统计信息
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("获取股票数", result['total_stocks'])

    with col2:
        st.metric("筛选后", result['filtered_stocks'])

    with col3:
        st.metric("最终推荐", len(result['final_recommendations']))

    st.markdown("---")

    # 显示AI分析师完整报告
    if analyzer and hasattr(analyzer, 'fund_flow_analysis'):
        display_analyst_reports(analyzer)

    st.markdown("---")

    # 显示推荐股票
    if result['final_recommendations']:
        st.markdown("### ⭐ 精选推荐")

        mask_identity = is_mask_stock_identity_enabled()
        for rec in result['final_recommendations']:
            display_symbol = mask_stock_code(rec['symbol']) if mask_identity else rec['symbol']
            display_name = mask_stock_name(rec['name']) if mask_identity else rec['name']
            with st.expander(
                f"【第{rec['rank']}名】{display_symbol} - {display_name}",
                expanded=(rec['rank'] <= 3)
            ):
                display_recommendation_detail(rec)

    # 显示候选股票列表
    if analyzer and analyzer.raw_stocks is not None and not analyzer.raw_stocks.empty:
        st.markdown("---")
        st.markdown("### 📋 候选股票列表（筛选后）")

        # 选择关键列显示
        display_cols = ['股票代码', '股票简称']

        # 添加行业列
        industry_cols = [col for col in analyzer.raw_stocks.columns if '行业' in col]
        if industry_cols:
            display_cols.append(industry_cols[0])

        # 添加区间主力资金净流入（智能匹配）
        main_fund_col = None
        main_fund_patterns = [
            '区间主力资金流向',      # 实际列名
            '区间主力资金净流入',
            '主力资金流向',
            '主力资金净流入',
            '主力净流入',
            '主力资金'
        ]
        for pattern in main_fund_patterns:
            matching = [col for col in analyzer.raw_stocks.columns if pattern in col]
            if matching:
                main_fund_col = matching[0]
                break
        if main_fund_col:
            display_cols.append(main_fund_col)

        # 添加区间涨跌幅（前复权）（智能匹配）
        interval_pct_col = None
        interval_pct_patterns = [
            '区间涨跌幅:前复权', '区间涨跌幅:前复权(%)', '区间涨跌幅(%)',
            '区间涨跌幅', '涨跌幅:前复权', '涨跌幅:前复权(%)', '涨跌幅(%)', '涨跌幅'
        ]
        for pattern in interval_pct_patterns:
            matching = [col for col in analyzer.raw_stocks.columns if pattern in col]
            if matching:
                interval_pct_col = matching[0]
                break
        if interval_pct_col:
            display_cols.append(interval_pct_col)

        # 添加市值、市盈率、市净率
        for col_name in ['总市值', '市盈率', '市净率']:
            matching_cols = [col for col in analyzer.raw_stocks.columns if col_name in col]
            if matching_cols:
                display_cols.append(matching_cols[0])

        # 添加技术形态评分字段
        for col_name in ['形态评分', '形态等级', '形态标签']:
            if col_name in analyzer.raw_stocks.columns:
                display_cols.append(col_name)

        # 添加综合展示分字段（若来自推荐结果补充）
        for col_name in ['分值_overall', '分值_fund_flow', '分值_industry', '分值_fundamental', '分值_technical_pattern']:
            if col_name in analyzer.raw_stocks.columns:
                display_cols.append(col_name)

        # 选择存在的列
        final_cols = [col for col in display_cols if col in analyzer.raw_stocks.columns]

        # 调试信息：显示找到的列名
        with st.expander("🔍 调试信息 - 查看数据列", expanded=False):
            st.caption("所有可用列:")
            cols_list = list(analyzer.raw_stocks.columns)
            st.write(cols_list)
            st.caption(f"\n已选择显示的列: {final_cols}")
            if main_fund_col:
                st.success(f"✅ 找到主力资金列: {main_fund_col}")
            else:
                st.warning("⚠️ 未找到主力资金列")
            if interval_pct_col:
                st.success(f"✅ 找到涨跌幅列: {interval_pct_col}")
            else:
                st.warning("⚠️ 未找到涨跌幅列")

        # 显示DataFrame
        display_df = analyzer.raw_stocks[final_cols].copy()
        display_df = mask_dataframe_stock_identity(display_df)
        st.dataframe(display_df, width='content', height=400)

        # 显示统计
        st.caption(f"共 {len(display_df)} 只候选股票，显示 {len(final_cols)} 个字段")

        # 下载按钮
        csv = display_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 下载候选列表CSV",
            data=csv,
            file_name=f"main_force_stocks_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )

        # 批量分析功能区
        st.markdown("---")

        col_batch1, col_batch2, col_batch3 = st.columns([2, 1, 1])
        with col_batch1:
            st.markdown("#### 🚀 批量深度分析")
            st.caption("对主力资金净流入TOP股票进行完整的AI团队分析，获取投资评级和关键价位")

        with col_batch2:
            batch_count = st.selectbox(
                "分析数量",
                options=[10, 20, 30, 50],
                index=1,  # 默认20只
                help="选择分析主力资金净流入前N只股票"
            )

        with col_batch3:
            st.write("")  # 占位
            if st.button("🚀 开始批量分析", type="primary", width='content'):
                # 准备数据：按主力资金净流入排序
                df_sorted = analyzer.raw_stocks.copy()

                # 确保主力资金列是数值类型并排序
                if main_fund_col:
                    df_sorted[main_fund_col] = pd.to_numeric(df_sorted[main_fund_col], errors='coerce')
                    df_sorted = df_sorted.sort_values(by=main_fund_col, ascending=False)

                # 提取股票代码并去掉市场后缀（.SH, .SZ等）
                raw_codes = df_sorted.head(batch_count)['股票代码'].tolist()
                stock_codes = []
                for code in raw_codes:
                    # 去掉后缀（如果有的话）
                    if isinstance(code, str):
                        # 去掉 .SH, .SZ, .BJ 等后缀
                        clean_code = code.split('.')[0] if '.' in code else code
                        stock_codes.append(clean_code)
                    else:
                        stock_codes.append(str(code))

                # 存储到session_state，触发批量分析
                st.session_state.main_force_batch_codes = stock_codes
                st.session_state.main_force_batch_trigger = True
                st.rerun()

    # 显示PDF报告下载区域
    if analyzer and result:
        display_report_download_section(analyzer, result)

def display_recommendation_detail(rec: dict):
    """显示单个推荐股票的详细信息"""
    scores = rec.get('scores', {}) or {}
    stock_data = rec.get('stock_data', {})
    mask_identity = is_mask_stock_identity_enabled()
    pattern_score, pattern_level, pattern_tags = get_pattern_display(stock_data, scores)

    st.markdown('<div class="main-force-result-card">', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="main-force-score-grid">
        <div class="main-force-score overall"><strong>{scores.get('overall', 'N/A')}</strong><span>综合分</span></div>
        <div class="main-force-score"><strong>{scores.get('fund_flow', 'N/A')}</strong><span>资金分</span></div>
        <div class="main-force-score"><strong>{scores.get('industry', 'N/A')}</strong><span>板块分</span></div>
        <div class="main-force-score"><strong>{scores.get('fundamental', 'N/A')}</strong><span>基本面分</span></div>
        <div class="main-force-score"><strong>{pattern_score}</strong><span>形态分</span></div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown('<div class="main-force-section"><h4>📌 推荐理由</h4>', unsafe_allow_html=True)
        for reason in rec.get('reasons', []):
            st.markdown(f"- {reason}")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="main-force-section"><h4>💡 投资亮点</h4>', unsafe_allow_html=True)
        st.write(rec.get('highlights', 'N/A'))
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="main-force-section"><h4>📊 投资建议</h4>', unsafe_allow_html=True)
        st.markdown(f"**建议仓位**: {rec.get('position', 'N/A')}")
        st.markdown(f"**投资周期**: {rec.get('investment_period', 'N/A')}")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="main-force-section"><h4>⚠️ 风险提示</h4>', unsafe_allow_html=True)
        st.write(rec.get('risks', 'N/A'))
        st.markdown('</div>', unsafe_allow_html=True)

    # 显示股票详细数据
    if 'stock_data' in rec:
        st.markdown("---")
        st.markdown("#### 📊 股票详细数据")

        stock_data = rec['stock_data']

        # 创建数据展示
        col1, col2, col3 = st.columns(3)

        with col1:
            stock_code = stock_data.get('股票代码', 'N/A')
            st.metric("股票代码", mask_stock_code(stock_code) if mask_identity else stock_code)

            # 显示行业
            industry_keys = [k for k in stock_data.keys() if '行业' in k]
            if industry_keys:
                st.metric("所属行业", stock_data.get(industry_keys[0], 'N/A'))

        with col2:
            # 显示主力资金
            fund_keys = [k for k in stock_data.keys() if '主力' in k and '净流入' in k]
            if fund_keys:
                fund_value = stock_data.get(fund_keys[0], 'N/A')
                if isinstance(fund_value, (int, float)):
                    st.metric("主力资金净流入", f"{fund_value/100000000:.2f}亿")
                else:
                    st.metric("主力资金净流入", str(fund_value))

        with col3:
            # 显示涨跌幅
            change_keys = [k for k in stock_data.keys() if '涨跌幅' in k]
            if change_keys:
                change_value = stock_data.get(change_keys[0], 'N/A')
                if isinstance(change_value, (int, float)):
                    st.metric("区间涨跌幅", f"{change_value:.2f}%")
                else:
                    st.metric("区间涨跌幅", str(change_value))

        st.markdown("#### 📐 技术形态")
        col_shape1, col_shape2, col_shape3 = st.columns(3)
        with col_shape1:
            st.metric("形态评分", pattern_score)
        with col_shape2:
            st.metric("形态等级", pattern_level)
        with col_shape3:
            st.metric("形态标签", pattern_tags)

        # 显示其他关键指标
        st.markdown("**其他关键指标：**")
        metrics_col1, metrics_col2, metrics_col3 = st.columns(3)

        with metrics_col1:
            if '市盈率' in stock_data or any('市盈率' in k for k in stock_data.keys()):
                pe_keys = [k for k in stock_data.keys() if '市盈率' in k]
                if pe_keys:
                    st.caption(f"市盈率: {stock_data.get(pe_keys[0], 'N/A')}")

        with metrics_col2:
            if '市净率' in stock_data or any('市净率' in k for k in stock_data.keys()):
                pb_keys = [k for k in stock_data.keys() if '市净率' in k]
                if pb_keys:
                    st.caption(f"市净率: {stock_data.get(pb_keys[0], 'N/A')}")

        with metrics_col3:
            if '总市值' in stock_data or any('总市值' in k for k in stock_data.keys()):
                cap_keys = [k for k in stock_data.keys() if '总市值' in k]
                if cap_keys:
                    st.caption(f"总市值: {stock_data.get(cap_keys[0], 'N/A')}")

    st.markdown('</div>', unsafe_allow_html=True)

def display_analyst_reports(analyzer):
    """显示AI分析师完整报告"""

    st.markdown("### 🤖 AI分析师团队完整报告")

    # 创建四个标签页
    tab1, tab2, tab3, tab4 = st.tabs(["💰 资金流向分析", "📊 行业板块分析", "📈 财务基本面分析", "📐 技术形态分析"])

    with tab1:
        st.markdown("#### 💰 资金流向分析师报告")
        st.markdown('<div class="main-force-report">', unsafe_allow_html=True)
        if hasattr(analyzer, 'fund_flow_analysis') and analyzer.fund_flow_analysis:
            st.markdown(analyzer.fund_flow_analysis)
        else:
            st.info("暂无资金流向分析报告")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.markdown("#### 📊 行业板块及市场热点分析师报告")
        st.markdown('<div class="main-force-report">', unsafe_allow_html=True)
        if hasattr(analyzer, 'industry_analysis') and analyzer.industry_analysis:
            st.markdown(analyzer.industry_analysis)
        else:
            st.info("暂无行业板块分析报告")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        st.markdown("#### 📈 财务基本面分析师报告")
        st.markdown('<div class="main-force-report">', unsafe_allow_html=True)
        if hasattr(analyzer, 'fundamental_analysis') and analyzer.fundamental_analysis:
            st.markdown(analyzer.fundamental_analysis)
        else:
            st.info("暂无财务基本面分析报告")
        st.markdown('</div>', unsafe_allow_html=True)

    with tab4:
        st.markdown("#### 📐 技术形态分析师报告")
        st.markdown('<div class="main-force-report">', unsafe_allow_html=True)
        if hasattr(analyzer, 'technical_pattern_analysis') and analyzer.technical_pattern_analysis:
            st.markdown(analyzer.technical_pattern_analysis)
        else:
            st.info("暂无技术形态分析报告")
        st.markdown('</div>', unsafe_allow_html=True)

def format_number(value, unit='', suffix=''):
    """格式化数字显示"""
    if value is None or value == 'N/A':
        return 'N/A'

    try:
        num = float(value)

        # 如果单位是亿，需要转换
        if unit == '亿':
            if abs(num) >= 100000000:  # 大于1亿（以元为单位）
                num = num / 100000000
            elif abs(num) < 100:  # 小于100，可能已经是亿
                pass
            else:  # 100-100000000之间，可能是万
                num = num / 10000

        # 格式化显示
        if abs(num) >= 1000:
            formatted = f"{num:,.2f}"
        elif abs(num) >= 1:
            formatted = f"{num:.2f}"
        else:
            formatted = f"{num:.4f}"

        return f"{formatted}{suffix}"
    except (ValueError, TypeError):
        return str(value)


def run_main_force_batch_analysis():
    """执行主力选股TOP股票批量分析（遵循统一调用规范）"""
    import time
    import re

    st.markdown("## 🚀 主力选股TOP股票批量分析")
    st.markdown("---")

    # 检查是否已有分析结果
    if st.session_state.get('main_force_batch_results'):
        display_main_force_batch_results(st.session_state.main_force_batch_results)

        # 返回按钮
        col_back, col_clear = st.columns(2)
        with col_back:
            if st.button("🔙 返回主力选股", width='content'):
                # 清除所有批量分析相关状态
                if 'main_force_batch_trigger' in st.session_state:
                    del st.session_state.main_force_batch_trigger
                if 'main_force_batch_codes' in st.session_state:
                    del st.session_state.main_force_batch_codes
                if 'main_force_batch_results' in st.session_state:
                    del st.session_state.main_force_batch_results
                st.rerun()

        with col_clear:
            if st.button("🔄 重新分析", width='content'):
                # 清除结果，保留触发标志和代码
                if 'main_force_batch_results' in st.session_state:
                    del st.session_state.main_force_batch_results
                st.rerun()

        return

    # 获取股票代码列表
    stock_codes = st.session_state.get('main_force_batch_codes', [])

    if not stock_codes:
        st.error("未找到股票代码列表")
        # 清除触发标志
        if 'main_force_batch_trigger' in st.session_state:
            del st.session_state.main_force_batch_trigger
        return

    mask_identity = is_mask_stock_identity_enabled()
    display_codes = [mask_stock_code(code) for code in stock_codes] if mask_identity else stock_codes
    st.info(f"即将分析 {len(stock_codes)} 只股票：{', '.join(display_codes[:10])}{'...' if len(display_codes) > 10 else ''}")

    # 返回按钮
    if st.button("🔙 取消返回", type="secondary"):
        # 清除所有批量分析相关状态
        if 'main_force_batch_trigger' in st.session_state:
            del st.session_state.main_force_batch_trigger
        if 'main_force_batch_codes' in st.session_state:
            del st.session_state.main_force_batch_codes
        st.rerun()

    st.markdown("---")

    # 分析选项
    col1, col2 = st.columns(2)

    with col1:
        analysis_mode = st.selectbox(
            "分析模式",
            options=["sequential", "parallel"],
            format_func=lambda x: "顺序分析（稳定）" if x == "sequential" else "并行分析（快速）",
            help="顺序分析较慢但稳定，并行分析更快但消耗更多资源"
        )

    with col2:
        if analysis_mode == "parallel":
            max_workers = st.number_input(
                "并行线程数",
                min_value=2,
                max_value=5,
                value=3,
                help="同时分析的股票数量"
            )
        else:
            max_workers = 1

    st.markdown("---")

    # 开始分析按钮
    col_confirm, col_cancel = st.columns(2)

    start_analysis = False
    with col_confirm:
        if st.button("🚀 确认开始分析", type="primary", width='content'):
            start_analysis = True

    with col_cancel:
        if st.button("❌ 取消", type="secondary", width='content'):
            # 清除所有批量分析相关状态
            if 'main_force_batch_trigger' in st.session_state:
                del st.session_state.main_force_batch_trigger
            if 'main_force_batch_codes' in st.session_state:
                del st.session_state.main_force_batch_codes
            st.rerun()

    if start_analysis:
        # 导入统一分析函数（遵循统一规范）
        from app import analyze_single_stock_for_batch
        import concurrent.futures
        import time

        st.markdown("---")
        st.info("⏳ 正在执行批量分析，请稍候...")

        # 显示即将分析的股票代码（调试用）
        with st.expander("🔍 调试信息", expanded=True):
            st.write(f"**股票代码数量**: {len(stock_codes)} 只")
            st.write(f"**股票代码列表**: {display_codes}")
            st.write(f"**代码格式检查**: {'✅ 无后缀，格式正确' if all('.' not in str(c) for c in stock_codes) else '❌ 包含后缀，可能有问题'}")
            st.write(f"**分析模式**: {analysis_mode}")
            st.write(f"**线程数**: {max_workers if analysis_mode == 'parallel' else 1}")

        # 配置分析师参数
        enabled_analysts_config = {
            'technical': True,
            'fundamental': True,
            'fund_flow': True,
            'risk': True,
            'sentiment': False,  # 禁用以提升速度
            'news': False  # 禁用以提升速度
        }
        import config
        selected_model = config.DEFAULT_MODEL_NAME
        period = '1y'

        # 创建进度显示
        progress_bar = st.progress(0)
        status_text = st.empty()

        # 存储结果
        results = []

        # 记录开始时间
        start_time = time.time()

        if analysis_mode == "sequential":
            # 顺序分析
            for i, code in enumerate(stock_codes):
                display_code = mask_stock_code(code) if mask_identity else code
                status_text.text(f"正在分析 {display_code} ({i+1}/{len(stock_codes)})")
                progress_bar.progress((i + 1) / len(stock_codes))

                try:
                    # 调用统一分析函数
                    result = analyze_single_stock_for_batch(
                        symbol=code,
                        period=period,
                        enabled_analysts_config=enabled_analysts_config,
                        selected_model=selected_model
                    )

                    results.append(result)

                except Exception as e:
                    results.append({
                        "symbol": code,
                        "success": False,
                        "error": str(e)
                    })

        else:
            # 并行分析
            status_text.text(f"并行分析 {len(stock_codes)} 只股票（{max_workers}线程）...")
            print(f"\n{'='*60}")
            print(f"🚀 开始并行分析 {len(stock_codes)} 只股票")
            print(f"{'='*60}")

            def analyze_one(code):
                try:
                    print(f"  开始分析: {code}")
                    result = analyze_single_stock_for_batch(
                        symbol=code,
                        period=period,
                        enabled_analysts_config=enabled_analysts_config,
                        selected_model=selected_model
                    )
                    print(f"  完成分析: {code}")
                    return result
                except Exception as e:
                    print(f"  分析失败: {code} - {str(e)}")
                    return {"symbol": code, "success": False, "error": str(e)}

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(analyze_one, code): code for code in stock_codes}

                completed = 0
                for future in concurrent.futures.as_completed(futures):
                    code = futures[future]  # 获取对应的股票代码
                    completed += 1
                    progress = completed / len(stock_codes)
                    progress_bar.progress(progress)
                    display_code = mask_stock_code(code) if mask_identity else code
                    status_text.text(f"已完成 {completed}/{len(stock_codes)} ({display_code})")

                    print(f"  进度更新: {completed}/{len(stock_codes)} ({progress*100:.1f}%) - {code}")

                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        print(f"  获取结果失败: {code} - {str(e)}")
                        results.append({"symbol": code, "success": False, "error": str(e)})

            print(f"\n✅ 所有并行任务已完成")
            print(f"   完成数: {completed}")
            print(f"   结果数: {len(results)}")
            print(f"{'='*60}\n")

        # 清除进度
        progress_bar.empty()
        status_text.empty()

        # 计算统计
        elapsed_time = time.time() - start_time
        success_count = sum(1 for r in results if r.get("success", False))
        failed_count = len(results) - success_count

        # 显示完成信息
        if success_count > 0:
            st.success(f"✅ 批量分析完成！成功 {success_count} 只，失败 {failed_count} 只，耗时 {elapsed_time/60:.1f} 分钟")
        else:
            st.error(f"❌ 批量分析完成，但所有 {failed_count} 只股票都分析失败！")

            # 显示失败原因（调试用）
            with st.expander("❌ 查看失败原因", expanded=True):
                for r in results:
                    if not r.get("success", False):
                        st.error(f"**{r.get('symbol', 'N/A')}**: {r.get('error', '未知错误')}")

        # 先保存到数据库历史记录（在 rerun 之前完成）
        save_success = False
        save_error = None
        try:
            from main_force_batch_db import batch_db

            # 调试信息
            print(f"\n{'='*60}")
            print(f"📝 准备保存批量分析结果到历史记录")
            print(f"{'='*60}")
            print(f"股票代码数: {len(stock_codes)}")
            print(f"分析模式: {analysis_mode}")
            print(f"成功数: {success_count}")
            print(f"失败数: {failed_count}")
            print(f"总耗时: {elapsed_time:.2f}秒")
            print(f"结果数: {len(results)}")

            # 检查结果数据类型
            print(f"\n检查结果数据类型:")
            for i, result in enumerate(results[:3]):  # 只检查前3个
                print(f"  结果 {i+1}:")
                for key, value in list(result.items())[:5]:  # 只检查前5个字段
                    print(f"    - {key}: {type(value).__name__}")

            print(f"\n开始保存到数据库...")
            save_start = time.time()

            # 保存到数据库
            record_id = batch_db.save_batch_analysis(
                batch_count=len(stock_codes),
                analysis_mode=analysis_mode,
                success_count=success_count,
                failed_count=failed_count,
                total_time=elapsed_time,
                results=results
            )

            save_elapsed = time.time() - save_start
            print(f"✅ 批量分析结果已保存到历史记录")
            print(f"   记录ID: {record_id}")
            print(f"   保存耗时: {save_elapsed:.2f}秒")
            print(f"{'='*60}\n")
            save_success = True

        except Exception as e:
            import traceback
            save_error = str(e)
            print(f"\n{'='*60}")
            print(f"⚠️ 保存历史记录失败")
            print(f"{'='*60}")
            print(f"错误信息: {str(e)}")
            print(f"详细错误:")
            print(traceback.format_exc())
            print(f"{'='*60}\n")

        # 保存结果到session_state
        st.session_state.main_force_batch_results = {
            "results": results,
            "total": len(results),
            "success": success_count,
            "failed": failed_count,
            "elapsed_time": elapsed_time,
            "analysis_mode": analysis_mode,
            "saved_to_history": save_success,
            "save_error": save_error
        }

        time.sleep(0.5)

        # 重新渲染以显示结果
        st.rerun()


def display_main_force_batch_results(batch_results):
    """显示主力选股批量分析结果"""
    import re

    results = batch_results['results']
    total = batch_results['total']
    success = batch_results['success']
    failed = batch_results['failed']
    elapsed_time = batch_results['elapsed_time']
    saved_to_history = batch_results.get('saved_to_history', False)
    save_error = batch_results.get('save_error')

    st.markdown("## 📊 批量分析结果")

    # 显示保存状态
    if saved_to_history:
        st.success("✅ 分析结果已自动保存到历史记录，可点击右上角'📚 批量分析历史'查看")
    elif save_error:
        st.warning(f"⚠️ 历史记录保存失败: {save_error}，但结果仍可查看")

    st.markdown("---")

    # 统计信息
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("总计分析", f"{total} 只")

    with col2:
        st.metric("成功分析", f"{success} 只", delta=f"{success/total*100:.1f}%")

    with col3:
        st.metric("失败分析", f"{failed} 只")

    with col4:
        st.metric("总耗时", f"{elapsed_time/60:.1f} 分钟")

    st.markdown("---")

    # 成功分析的股票
    successful_results = [r for r in results if r['success']]

    if successful_results:
        st.markdown(f"### ✅ 成功分析的股票 ({len(successful_results)}只)")

        # 创建DataFrame展示
        display_data = []
        for result in successful_results:
            stock_info = result.get('stock_info', {})
            final_decision = result.get('final_decision', {})

            # 提取评级emoji
            rating = final_decision.get('rating', '未知')
            rating_emoji = {
                '强烈买入': '🔥',
                '买入': '✅',
                '持有': '⏸️',
                '卖出': '⚠️',
                '强烈卖出': '🚫'
            }.get(rating, '❓')

            display_data.append({
                '股票代码': stock_info.get('symbol', ''),
                '股票名称': stock_info.get('name', ''),
                '评级': f"{rating_emoji} {rating}",
                '信心度': final_decision.get('confidence_level', 'N/A'),
                '进场区间': final_decision.get('entry_range', 'N/A'),
                '止盈位': final_decision.get('take_profit', 'N/A'),
                '止损位': final_decision.get('stop_loss', 'N/A'),
                '目标价': final_decision.get('target_price', 'N/A')
            })

        df_display = pd.DataFrame(display_data)

        # 类型统一，避免Arrow序列化错误
        numeric_cols = ['信心度', '止盈位', '止损位', '目标价']
        for col in numeric_cols:
            if col in df_display.columns:
                df_display[col] = pd.to_numeric(df_display[col], errors='coerce')

        text_cols = ['股票代码', '股票名称', '评级', '进场区间']
        for col in text_cols:
            if col in df_display.columns:
                df_display[col] = df_display[col].astype(str)

        st.dataframe(mask_dataframe_stock_identity(df_display), width='content', height=400)

        # 详细分析结果（可展开）
        st.markdown("---")
        st.markdown("### 📋 详细分析报告")

        for result in successful_results:
            stock_info = result.get('stock_info', {})
            final_decision = result.get('final_decision', {})

            symbol = stock_info.get('symbol', '')
            name = stock_info.get('name', '')
            display_symbol = mask_stock_code(symbol) if is_mask_stock_identity_enabled() else symbol
            display_name = mask_stock_name(name) if is_mask_stock_identity_enabled() else name
            rating = final_decision.get('rating', '未知')
            rating_emoji = {
                '强烈买入': '🔥',
                '买入': '✅',
                '持有': '⏸️',
                '卖出': '⚠️',
                '强烈卖出': '🚫'
            }.get(rating, '❓')

            with st.expander(f"{rating_emoji} {display_symbol} - {display_name} | {rating}"):
                # 关键信息
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("信心度", final_decision.get('confidence_level', 'N/A'))

                with col2:
                    st.metric("进场区间", final_decision.get('entry_range', 'N/A'))

                with col3:
                    st.metric("目标价", final_decision.get('target_price', 'N/A'))

                # 止盈止损
                col1, col2 = st.columns(2)

                with col1:
                    st.metric("止盈位", final_decision.get('take_profit', 'N/A'))

                with col2:
                    st.metric("止损位", final_decision.get('stop_loss', 'N/A'))

                # 投资建议
                st.markdown("#### 💡 投资建议")
                advice = final_decision.get('operation_advice', final_decision.get('advice', '暂无建议'))
                st.info(advice)

                # 加入监测按钮
                if st.button(f"➕ 加入监测列表", key=f"monitor_{symbol}"):
                    # 解析进场区间
                    entry_range = final_decision.get('entry_range', '')
                    entry_min, entry_max = None, None
                    if entry_range and isinstance(entry_range, str) and "-" in entry_range:
                        try:
                            parts = entry_range.split("-")
                            entry_min = float(parts[0].strip())
                            entry_max = float(parts[1].strip())
                        except:
                            pass

                    # 解析止盈止损
                    take_profit_str = final_decision.get('take_profit', '')
                    take_profit = None
                    if take_profit_str:
                        try:
                            numbers = re.findall(r'\d+\.?\d*', str(take_profit_str))
                            if numbers:
                                take_profit = float(numbers[0])
                        except:
                            pass

                    stop_loss_str = final_decision.get('stop_loss', '')
                    stop_loss = None
                    if stop_loss_str:
                        try:
                            numbers = re.findall(r'\d+\.?\d*', str(stop_loss_str))
                            if numbers:
                                stop_loss = float(numbers[0])
                        except:
                            pass

                    # 调用监测管理器添加
                    from monitor_db import monitor_db

                    try:
                        # 准备进场区间数据
                        entry_range_dict = {}
                        if entry_min and entry_max:
                            entry_range_dict = {"min": entry_min, "max": entry_max}

                        # 添加到监测列表
                        monitor_db.add_monitored_stock(
                            symbol=symbol,
                            name=name,
                            rating=rating,
                            entry_range=entry_range_dict if entry_range_dict else None,
                            take_profit=take_profit,
                            stop_loss=stop_loss
                        )
                        st.success(f"✅ {symbol} - {name} 已加入监测列表")
                    except Exception as e:
                        st.error(f"❌ 添加失败: {str(e)}")

    # 失败的股票
    failed_results = [r for r in results if not r['success']]

    if failed_results:
        st.markdown("---")
        st.markdown(f"### ❌ 分析失败的股票 ({len(failed_results)}只)")

        failed_data = []
        for result in failed_results:
            failed_data.append({
                '股票代码': result.get('symbol', ''),
                '失败原因': result.get('error', '未知错误')
            })

        df_failed = pd.DataFrame(failed_data)
        st.dataframe(df_failed, width='content')

