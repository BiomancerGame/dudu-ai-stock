"""股票分析业务逻辑 — 从 app.py 抽取。"""

import time
import streamlit as st
import config
from stock_data import StockDataFetcher, stock_data_fetcher
from ai_agents import StockAnalysisAgents
from database import db
from core.concurrent import run_parallel


@st.cache_data(ttl=300)  # 缓存5分钟
def get_stock_data(symbol, period):
    """获取股票数据（带缓存）"""
    fetcher = stock_data_fetcher
    stock_info = fetcher.get_stock_info(symbol)
    stock_data = fetcher.get_stock_data(symbol, period)

    if isinstance(stock_data, dict) and "error" in stock_data:
        return stock_info, None, None

    stock_data_with_indicators = fetcher.calculate_technical_indicators(stock_data)
    indicators = fetcher.get_latest_indicators(stock_data_with_indicators)

    return stock_info, stock_data_with_indicators, indicators

def parse_stock_list(stock_input):
    """解析股票代码列表

    支持的格式：
    - 每行一个代码
    - 逗号分隔
    - 空格分隔
    """
    if not stock_input or not stock_input.strip():
        return []

    # 先按换行符分割
    lines = stock_input.strip().split('\n')

    # 处理每一行
    stock_list = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 检查是否包含逗号
        if ',' in line:
            codes = [code.strip() for code in line.split(',')]
            stock_list.extend([code for code in codes if code])
        # 检查是否包含空格
        elif ' ' in line:
            codes = [code.strip() for code in line.split()]
            stock_list.extend([code for code in codes if code])
        else:
            stock_list.append(line)

    # 去重并保持顺序
    seen = set()
    unique_list = []
    for code in stock_list:
        if code not in seen:
            seen.add(code)
            unique_list.append(code)

    return unique_list


def analyze_single_stock_for_batch(symbol, period, enabled_analysts_config=None, selected_model=None):
    """单个股票分析（用于批量分析）

    Args:
        symbol: 股票代码
        period: 数据周期
        enabled_analysts_config: 分析师配置字典
        selected_model: 选择的AI模型，默认从 .env 的 DEFAULT_MODEL_NAME 读取

    返回分析结果或错误信息
    """
    try:
        # 使用默认模型
        if selected_model is None:
            selected_model = config.DEFAULT_MODEL_NAME

        # 使用默认配置
        if enabled_analysts_config is None:
            enabled_analysts_config = {
                'technical': True,
                'fundamental': True,
                'fund_flow': True,
                'risk': True,
                'sentiment': False,
                'news': False,
                'pattern': False,
                'canslim': False
            }

        # 1. 获取股票数据
        stock_info, stock_data, indicators = get_stock_data(symbol, period)

        if "error" in stock_info:
            return {"symbol": symbol, "error": stock_info['error'], "success": False}

        if stock_data is None:
            return {"symbol": symbol, "error": "无法获取股票历史数据", "success": False}

        # 2. 获取财务数据
        fetcher = stock_data_fetcher
        financial_data = fetcher.get_financial_data(symbol)

        # 获取分析师选择状态（从参数而不是session_state）
        enable_fundamental = enabled_analysts_config.get('fundamental', True)
        enable_fund_flow = enabled_analysts_config.get('fund_flow', True)
        enable_sentiment = enabled_analysts_config.get('sentiment', False)
        enable_news = enabled_analysts_config.get('news', False)
        enable_risk = enabled_analysts_config.get('risk', True)
        enable_pattern = enabled_analysts_config.get('pattern', False)
        enable_canslim = enabled_analysts_config.get('canslim', False)
        is_a_stock = fetcher._is_chinese_stock(symbol)

        # 并行获取各类辅助数据（季报、资金流向、情绪、新闻、风险、形态）
        data_tasks = {}

        if enable_fundamental and is_a_stock:
            def _fetch_quarterly():
                from quarterly_report_data import QuarterlyReportDataFetcher
                return QuarterlyReportDataFetcher().get_quarterly_reports(symbol)
            data_tasks["quarterly"] = (_fetch_quarterly, ())

        if enable_fund_flow and is_a_stock:
            def _fetch_fund_flow():
                from fund_flow_akshare import FundFlowAkshareDataFetcher
                return FundFlowAkshareDataFetcher().get_fund_flow_data(symbol)
            data_tasks["fund_flow"] = (_fetch_fund_flow, ())

        if enable_sentiment and is_a_stock:
            def _fetch_sentiment():
                from market_sentiment_data import MarketSentimentDataFetcher
                return MarketSentimentDataFetcher().get_market_sentiment_data(symbol, stock_data)
            data_tasks["sentiment"] = (_fetch_sentiment, ())

        if enable_news and is_a_stock:
            def _fetch_news():
                from qstock_news_data import QStockNewsDataFetcher
                return QStockNewsDataFetcher().get_stock_news(symbol)
            data_tasks["news"] = (_fetch_news, ())

        if enable_risk and is_a_stock:
            def _fetch_risk():
                return fetcher.get_risk_data(symbol)
            data_tasks["risk"] = (_fetch_risk, ())

        if enable_pattern:
            def _fetch_pattern():
                from pattern_recognition import PatternRecognizer
                return PatternRecognizer().analyze(symbol)
            data_tasks["pattern"] = (_fetch_pattern, ())

        if enable_canslim:
            def _fetch_canslim():
                from canslim_analyzer import CANSLIMAnalyzer
                return CANSLIMAnalyzer().analyze(symbol)
            data_tasks["canslim"] = (_fetch_canslim, ())

        # 并行执行所有数据获取
        data_results = run_parallel(data_tasks, max_workers=5) if data_tasks else {}

        # 提取结果（异常视为 None）
        quarterly_data = data_results.get("quarterly") if not isinstance(data_results.get("quarterly"), Exception) else None
        fund_flow_data = data_results.get("fund_flow") if not isinstance(data_results.get("fund_flow"), Exception) else None
        sentiment_data = data_results.get("sentiment") if not isinstance(data_results.get("sentiment"), Exception) else None
        news_data = data_results.get("news") if not isinstance(data_results.get("news"), Exception) else None
        risk_data = data_results.get("risk") if not isinstance(data_results.get("risk"), Exception) else None
        pattern_data = data_results.get("pattern") if not isinstance(data_results.get("pattern"), Exception) else None
        canslim_data = data_results.get("canslim") if not isinstance(data_results.get("canslim"), Exception) else None

        # 6. 初始化AI分析系统
        agents = StockAnalysisAgents(model=selected_model)

        # 使用传入的分析师配置
        enabled_analysts = enabled_analysts_config

        # 7. 运行多智能体分析
        agents_results = agents.run_multi_agent_analysis(
            stock_info, stock_data, indicators, financial_data,
            fund_flow_data, sentiment_data, news_data, quarterly_data, risk_data,
            pattern_data=pattern_data, canslim_data=canslim_data,
            enabled_analysts=enabled_analysts_config
        )

        # 8. 团队讨论
        discussion_result = agents.conduct_team_discussion(agents_results, stock_info)

        # 9. 最终决策
        final_decision = agents.make_final_decision(discussion_result, stock_info, indicators)

        # 保存到数据库
        saved_to_db = False
        db_error = None
        try:
            record_id = db.save_analysis(
                symbol=stock_info.get('symbol', ''),
                stock_name=stock_info.get('name', ''),
                period=period,
                stock_info=stock_info,
                agents_results=agents_results,
                discussion_result=discussion_result,
                final_decision=final_decision
            )
            saved_to_db = True
            print(f"✅ {symbol} 成功保存到数据库，记录ID: {record_id}")
        except Exception as e:
            db_error = str(e)
            print(f"❌ {symbol} 保存到数据库失败: {db_error}")

        return {
            "symbol": symbol,
            "success": True,
            "stock_info": stock_info,
            "indicators": indicators,
            "agents_results": agents_results,
            "discussion_result": discussion_result,
            "final_decision": final_decision,
            "saved_to_db": saved_to_db,
            "db_error": db_error
        }

    except Exception as e:
        return {"symbol": symbol, "error": str(e), "success": False}


def run_batch_analysis(stock_list, period, batch_mode="顺序分析"):
    """运行批量股票分析"""
    import concurrent.futures
    import threading

    # 在开始分析前获取配置（从session_state）
    enabled_analysts_config = {
        'technical': st.session_state.get('enable_technical', True),
        'fundamental': st.session_state.get('enable_fundamental', True),
        'fund_flow': st.session_state.get('enable_fund_flow', True),
        'risk': st.session_state.get('enable_risk', True),
        'sentiment': st.session_state.get('enable_sentiment', False),
        'news': st.session_state.get('enable_news', False)
    }
    selected_model = st.session_state.get('selected_model', config.DEFAULT_MODEL_NAME)

    # 创建进度显示
    st.subheader(f"📊 批量分析进行中 ({batch_mode})")

    progress_bar = st.progress(0)
    status_text = st.empty()

    # 存储结果
    results = []
    total = len(stock_list)

    if batch_mode == "多线程并行":
        # 多线程并行分析
        status_text.text(f"🚀 使用多线程并行分析 {total} 只股票...")

        # 创建线程锁用于更新进度
        lock = threading.Lock()
        completed = [0]  # 使用列表以便在闭包中修改
        progress_status = [{}]  # 存储进度状态

        def analyze_with_progress(symbol):
            """包装分析函数，不在线程中访问Streamlit上下文"""
            try:
                result = analyze_single_stock_for_batch(symbol, period, enabled_analysts_config, selected_model)
                with lock:
                    completed[0] += 1
                    progress_status[0][symbol] = result
                return result
            except Exception as e:
                with lock:
                    completed[0] += 1
                    error_result = {"symbol": symbol, "error": str(e), "success": False}
                    progress_status[0][symbol] = error_result
                return error_result

        # 使用线程池执行，限制最大并发数为3以避免API限流
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_symbol = {executor.submit(analyze_with_progress, symbol): symbol
                              for symbol in stock_list}

            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result(timeout=300)  # 5分钟超时
                    results.append(result)

                    # 在主线程中更新UI
                    progress = len(results) / total
                    progress_bar.progress(progress)

                    if result['success']:
                        status_text.text(f"✅ [{len(results)}/{total}] {symbol} 分析完成")
                    else:
                        status_text.text(f"❌ [{len(results)}/{total}] {symbol} 分析失败: {result.get('error', '未知错误')}")

                except concurrent.futures.TimeoutError:
                    results.append({"symbol": symbol, "error": "分析超时（5分钟）", "success": False})
                    progress_bar.progress(len(results) / total)
                    status_text.text(f"⏱️ [{len(results)}/{total}] {symbol} 分析超时")
                except Exception as e:
                    results.append({"symbol": symbol, "error": str(e), "success": False})
                    progress_bar.progress(len(results) / total)
                    status_text.text(f"❌ [{len(results)}/{total}] {symbol} 出现错误")

    else:
        # 顺序分析
        status_text.text(f"📝 按顺序分析 {total} 只股票...")

        for i, symbol in enumerate(stock_list, 1):
            status_text.text(f"🔍 [{i}/{total}] 正在分析 {symbol}...")

            try:
                result = analyze_single_stock_for_batch(symbol, period, enabled_analysts_config, selected_model)
            except Exception as e:
                result = {"symbol": symbol, "error": str(e), "success": False}

            results.append(result)

            # 更新进度
            progress = i / total
            progress_bar.progress(progress)

            if result['success']:
                status_text.text(f"✅ [{i}/{total}] {symbol} 分析完成")
            else:
                status_text.text(f"❌ [{i}/{total}] {symbol} 分析失败: {result.get('error', '未知错误')}")

    # 完成
    progress_bar.progress(1.0)

    # 统计结果
    success_count = sum(1 for r in results if r['success'])
    failed_count = total - success_count
    saved_count = sum(1 for r in results if r.get('saved_to_db', False))

    # 显示完成信息
    if success_count > 0:
        status_text.success(f"✅ 批量分析完成！成功 {success_count} 只，失败 {failed_count} 只，已保存 {saved_count} 只到历史记录")

        # 显示保存失败的股票
        save_failed = [r['symbol'] for r in results if r.get('success') and not r.get('saved_to_db', False)]
        if save_failed:
            st.warning(f"⚠️ 以下股票分析成功但保存失败: {', '.join(save_failed)}")
    else:
        status_text.error(f"❌ 批量分析完成，但所有股票都分析失败")

    # 保存结果到session_state
    st.session_state.batch_analysis_results = results
    st.session_state.batch_analysis_mode = batch_mode

    progress_bar.empty()

    # 自动显示结果
    st.rerun()


def run_stock_analysis(symbol, period):
    """运行股票分析"""
    from ui.sections.stock_display import (
        display_stock_info,
        display_stock_chart,
        display_agents_analysis,
        display_team_discussion,
        display_final_decision,
    )
    from app import create_analysis_process_panel

    # 进度条和过程日志
    progress_bar, status_text, update_process = create_analysis_process_panel("实时分析过程")

    try:
        # 1. 获取股票数据
        update_process("正在获取股票基础信息与历史行情", 8)
        progress_bar.progress(10)

        stock_info, stock_data, indicators = get_stock_data(symbol, period)

        if "error" in stock_info:
            st.error(f"❌ {stock_info['error']}")
            return

        if stock_data is None:
            st.error("❌ 无法获取股票历史数据")
            return

        # 显示股票基本信息
        display_stock_info(stock_info, indicators)
        update_process("股票基础数据获取完成", 20, level="success")

        # 显示股票图表
        display_stock_chart(stock_data, stock_info)
        update_process("K线图与技术指标渲染完成", 30, level="success")

        # 2. 并行获取所有辅助数据（财务、季报、资金流向、情绪、新闻、风险）
        update_process("正在并行获取各类数据", 32)
        fetcher = stock_data_fetcher
        is_a_stock = fetcher._is_chinese_stock(symbol)

        # 获取分析师选择状态
        enable_fundamental = st.session_state.get('enable_fundamental', True)
        enable_fund_flow = st.session_state.get('enable_fund_flow', True)
        enable_sentiment = st.session_state.get('enable_sentiment', False)
        enable_news = st.session_state.get('enable_news', False)
        enable_risk = st.session_state.get('enable_risk', True)
        enable_pattern = st.session_state.get('enable_pattern', False)
        enable_canslim = st.session_state.get('enable_canslim', False)

        # 构建并行数据获取任务
        data_tasks = {}
        data_tasks["financial"] = (fetcher.get_financial_data, (symbol,))

        if enable_fundamental and is_a_stock:
            def _fetch_quarterly():
                from quarterly_report_data import QuarterlyReportDataFetcher
                return QuarterlyReportDataFetcher().get_quarterly_reports(symbol)
            data_tasks["quarterly"] = (_fetch_quarterly, ())

        if enable_fund_flow and is_a_stock:
            def _fetch_fund_flow():
                from fund_flow_akshare import FundFlowAkshareDataFetcher
                return FundFlowAkshareDataFetcher().get_fund_flow_data(symbol)
            data_tasks["fund_flow"] = (_fetch_fund_flow, ())

        if enable_sentiment and is_a_stock:
            def _fetch_sentiment():
                from market_sentiment_data import MarketSentimentDataFetcher
                return MarketSentimentDataFetcher().get_market_sentiment_data(symbol, stock_data)
            data_tasks["sentiment"] = (_fetch_sentiment, ())

        if enable_news and is_a_stock:
            def _fetch_news():
                from qstock_news_data import QStockNewsDataFetcher
                return QStockNewsDataFetcher().get_stock_news(symbol)
            data_tasks["news"] = (_fetch_news, ())

        if enable_risk and is_a_stock:
            def _fetch_risk():
                return fetcher.get_risk_data(symbol)
            data_tasks["risk"] = (_fetch_risk, ())

        if enable_pattern:
            def _fetch_pattern():
                from pattern_recognition import PatternRecognizer
                return PatternRecognizer().analyze(symbol)
            data_tasks["pattern"] = (_fetch_pattern, ())

        if enable_canslim:
            def _fetch_canslim():
                from canslim_analyzer import CANSLIMAnalyzer
                return CANSLIMAnalyzer().analyze(symbol, financial_data=None, fund_flow_data=None)
            data_tasks["canslim"] = (_fetch_canslim, ())

        update_process("并行获取数据中（财务/季报/资金/情绪/新闻/风险/形态/CANSLIM）", 35)
        data_results = run_parallel(data_tasks, max_workers=6)
        progress_bar.progress(50)

        # 提取结果
        def _safe_get(key):
            v = data_results.get(key)
            return v if not isinstance(v, Exception) else None

        financial_data = _safe_get("financial")
        quarterly_data = _safe_get("quarterly")
        fund_flow_data = _safe_get("fund_flow")
        sentiment_data = _safe_get("sentiment")
        news_data = _safe_get("news")
        risk_data = _safe_get("risk")
        pattern_data = _safe_get("pattern")
        canslim_data = _safe_get("canslim")

        # 显示数据获取结果摘要
        data_summary = []
        if financial_data:
            data_summary.append("财务数据")
        if quarterly_data and quarterly_data.get('data_success'):
            data_summary.append("季报数据")
        if fund_flow_data and fund_flow_data.get('data_success'):
            data_summary.append("资金流向")
        if sentiment_data and sentiment_data.get('data_success'):
            data_summary.append("市场情绪")
        if news_data and news_data.get('data_success'):
            data_summary.append("新闻数据")
        if risk_data and risk_data.get('data_success'):
            data_summary.append("风险数据")
        if pattern_data and pattern_data.get('summary'):
            data_summary.append("形态数据")
        if canslim_data and canslim_data.get('components'):
            data_summary.append(f"CANSLIM({canslim_data.get('composite_score',0)}分)")

        if data_summary:
            st.info(f"✅ 已获取: {', '.join(data_summary)}")

        # 显示失败项
        failed_items = []
        if isinstance(data_results.get("quarterly"), Exception):
            failed_items.append("季报")
        if isinstance(data_results.get("fund_flow"), Exception):
            failed_items.append("资金流向")
        if isinstance(data_results.get("sentiment"), Exception):
            failed_items.append("情绪")
        if isinstance(data_results.get("news"), Exception):
            failed_items.append("新闻")
        if isinstance(data_results.get("risk"), Exception):
            failed_items.append("风险")
        if isinstance(data_results.get("pattern"), Exception):
            failed_items.append("形态")
        if isinstance(data_results.get("canslim"), Exception):
            failed_items.append("CANSLIM")
        if failed_items:
            st.warning(f"⚠️ 获取失败: {', '.join(failed_items)}（将基于可用数据分析）")

        if not is_a_stock:
            st.info("ℹ️ 非A股标的，部分数据源不可用（季报/资金/情绪/新闻/风险）")

        update_process("所有数据获取完成", 50, level="success")

        # 6. 初始化AI分析系统
        update_process("正在初始化AI分析系统", 52)
        # 使用选择的模型
        selected_model = st.session_state.get('selected_model', config.DEFAULT_MODEL_NAME)
        agents = StockAnalysisAgents(model=selected_model)
        update_process("AI分析系统初始化完成", 55, selected_model, level="success")

        # 获取所有分析师选择状态
        enable_technical = st.session_state.get('enable_technical', True)
        enable_fundamental = st.session_state.get('enable_fundamental', True)
        enable_risk = st.session_state.get('enable_risk', True)

        # 创建分析师启用字典
        enabled_analysts = {
            'technical': enable_technical,
            'fundamental': enable_fundamental,
            'fund_flow': enable_fund_flow,
            'risk': enable_risk,
            'sentiment': enable_sentiment,
            'news': enable_news,
            'pattern': enable_pattern,
            'canslim': enable_canslim
        }

        # 7. 运行多智能体分析（传入所有数据和分析师选择）
        update_process("AI分析师团队开始逐项分析", 58)

        def agent_progress(status, message, ratio):
            level = "success" if status == "done" else "info"
            update_process(message, 58 + ratio * 17, level=level)

        agents_results = agents.run_multi_agent_analysis(
            stock_info, stock_data, indicators, financial_data,
            fund_flow_data, sentiment_data, news_data, quarterly_data, risk_data,
            pattern_data=pattern_data, canslim_data=canslim_data,
            enabled_analysts=enabled_analysts,
            progress_callback=agent_progress
        )
        update_process("AI分析师团队分析完成", 75, level="success")

        # 显示各分析师报告
        display_agents_analysis(agents_results)

        # 8. 团队讨论
        update_process("分析团队正在综合讨论", 82)
        discussion_result = agents.conduct_team_discussion(agents_results, stock_info)
        update_process("团队讨论完成", 88, level="success")

        # 显示团队讨论
        display_team_discussion(discussion_result)

        # 9. 最终决策
        update_process("正在制定最终投资决策", 94)
        final_decision = agents.make_final_decision(discussion_result, stock_info, indicators)
        update_process("最终投资决策生成完成", 100, level="success")

        # 显示最终决策
        display_final_decision(final_decision, stock_info, agents_results, discussion_result)

        # 保存分析结果到session_state（用于页面刷新后显示）
        st.session_state.analysis_completed = True
        st.session_state.stock_info = stock_info
        st.session_state.agents_results = agents_results
        st.session_state.discussion_result = discussion_result
        st.session_state.final_decision = final_decision
        st.session_state.just_completed = True  # 标记刚刚完成分析

        # 保存到数据库
        try:
            db.save_analysis(
                symbol=stock_info.get('symbol', ''),
                stock_name=stock_info.get('name', ''),
                period=period,
                stock_info=stock_info,
                agents_results=agents_results,
                discussion_result=discussion_result,
                final_decision=final_decision
            )
            st.success("✅ 分析记录已保存到数据库")
        except Exception as e:
            st.warning(f"⚠️ 保存到数据库时出现错误: {str(e)}")

        update_process("分析完成", 100, level="success")

    except Exception as e:
        st.error(f"❌ 分析过程中出现错误: {str(e)}")
        update_process("分析过程中出现错误", None, str(e), level="error")
