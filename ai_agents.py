from deepseek_client import DeepSeekClient
from prompts import render as render_prompt
from typing import Callable, Dict, Any
import time
import config

class StockAnalysisAgents:
    """股票分析AI智能体集合"""
    
    def __init__(self, model=None):
        self.model = model or config.DEFAULT_MODEL_NAME
        self.deepseek_client = DeepSeekClient(model=self.model)
        
    def technical_analyst_agent(self, stock_info: Dict, stock_data: Any, indicators: Dict) -> Dict[str, Any]:
        """技术面分析智能体"""
        print("🔍 技术分析师正在分析中...")
        time.sleep(1)  # 模拟分析时间
        
        analysis = self.deepseek_client.technical_analysis(stock_info, stock_data, indicators)
        
        return {
            "agent_name": "技术分析师",
            "agent_role": "负责技术指标分析、图表形态识别、趋势判断",
            "analysis": analysis,
            "focus_areas": ["技术指标", "趋势分析", "支撑阻力", "交易信号"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def fundamental_analyst_agent(self, stock_info: Dict, financial_data: Dict = None, quarterly_data: Dict = None) -> Dict[str, Any]:
        """基本面分析智能体"""
        print("📊 基本面分析师正在分析中...")
        
        # 如果有季报数据，显示数据来源
        if quarterly_data and quarterly_data.get('data_success'):
            income_count = quarterly_data.get('income_statement', {}).get('periods', 0) if quarterly_data.get('income_statement') else 0
            balance_count = quarterly_data.get('balance_sheet', {}).get('periods', 0) if quarterly_data.get('balance_sheet') else 0
            cash_flow_count = quarterly_data.get('cash_flow', {}).get('periods', 0) if quarterly_data.get('cash_flow') else 0
            print(f"   ✓ 已获取季报数据：利润表{income_count}期，资产负债表{balance_count}期，现金流量表{cash_flow_count}期")
        else:
            print("   ⚠ 未获取到季报数据，将基于基本财务数据分析")
        
        time.sleep(1)
        
        analysis = self.deepseek_client.fundamental_analysis(stock_info, financial_data, quarterly_data)
        
        return {
            "agent_name": "基本面分析师", 
            "agent_role": "负责公司财务分析、行业研究、估值分析",
            "analysis": analysis,
            "focus_areas": ["财务指标", "行业分析", "公司价值", "成长性", "季报趋势"],
            "quarterly_data": quarterly_data,  # 保存季报数据以供后续使用
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def fund_flow_analyst_agent(self, stock_info: Dict, indicators: Dict, fund_flow_data: Dict = None) -> Dict[str, Any]:
        """资金面分析智能体"""
        print("💰 资金面分析师正在分析中...")
        
        # 如果有资金流向数据，显示数据来源
        if fund_flow_data and fund_flow_data.get('data_success'):
            print("   ✓ 已获取资金流向数据（akshare数据源）")
        else:
            print("   ⚠ 未获取到资金流向数据，将基于技术指标分析")
        
        time.sleep(1)
        
        analysis = self.deepseek_client.fund_flow_analysis(stock_info, indicators, fund_flow_data)
        
        return {
            "agent_name": "资金面分析师",
            "agent_role": "负责资金流向分析、主力行为研究、市场情绪判断", 
            "analysis": analysis,
            "focus_areas": ["资金流向", "主力动向", "市场情绪", "流动性"],
            "fund_flow_data": fund_flow_data,  # 保存资金流向数据以供后续使用
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def risk_management_agent(self, stock_info: Dict, indicators: Dict, risk_data: Dict = None) -> Dict[str, Any]:
        """风险管理智能体（增强版）"""
        print("⚠️ 风险管理师正在评估中...")
        
        # 如果有风险数据，显示数据来源
        if risk_data and risk_data.get('data_success'):
            print("   ✓ 已获取问财风险数据（限售解禁、大股东减持、重要事件）")
        else:
            print("   ⚠ 未获取到风险数据，将基于基本信息分析")
        
        time.sleep(1)
        
        # 构建风险数据文本
        risk_data_text = ""
        if risk_data and risk_data.get('data_success'):
            # 使用格式化的风险数据
            from risk_data_fetcher import RiskDataFetcher
            fetcher = RiskDataFetcher()
            risk_data_text = f"""

【实际风险数据】（来自问财）
{fetcher.format_risk_data_for_ai(risk_data)}

以上是通过问财（pywencai）获取的实际风险数据，请重点关注这些数据进行深度风险分析。
"""
        
        risk_prompt = render_prompt(
            "risk_management",
            symbol=stock_info.get("symbol", "N/A"),
            name=stock_info.get("name", "N/A"),
            current_price=stock_info.get("current_price", "N/A"),
            beta=stock_info.get("beta", "N/A"),
            week_52_high=stock_info.get("52_week_high", "N/A"),
            week_52_low=stock_info.get("52_week_low", "N/A"),
            rsi=indicators.get("rsi", "N/A"),
            risk_data_text=risk_data_text,
        )
        
        messages = [
            {"role": "system", "content": "你是一名资深的风险管理专家，具有20年以上的风险识别和控制经验，擅长全面评估各类投资风险，特别关注限售解禁、股东减持、重要事件等可能影响股价的风险因素。你擅长从海量原始数据中提取关键信息，进行深度解析和量化评估。"},
            {"role": "user", "content": risk_prompt}
        ]
        
        analysis = self.deepseek_client.call_api(messages, max_tokens=6000)
        
        return {
            "agent_name": "风险管理师",
            "agent_role": "负责风险识别、风险评估、风险控制策略制定",
            "analysis": analysis,
            "focus_areas": ["限售解禁风险", "股东减持风险", "重要事件风险", "风险识别", "风险量化", "风险控制", "资产配置"],
            "risk_data": risk_data,  # 保存风险数据以供后续使用
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def market_sentiment_agent(self, stock_info: Dict, sentiment_data: Dict = None) -> Dict[str, Any]:
        """市场情绪分析智能体"""
        print("📈 市场情绪分析师正在分析中...")
        
        # 如果有市场情绪数据，显示数据来源
        if sentiment_data and sentiment_data.get('data_success'):
            print("   ✓ 已获取市场情绪数据（ARBR、换手率、涨跌停等）")
        else:
            print("   ⚠ 未获取到详细情绪数据，将基于基本信息分析")
        
        time.sleep(1)
        
        # 构建带有市场情绪数据的prompt
        sentiment_data_text = ""
        if sentiment_data and sentiment_data.get('data_success'):
            # 使用格式化的市场情绪数据
            from market_sentiment_data import MarketSentimentDataFetcher
            fetcher = MarketSentimentDataFetcher()
            sentiment_data_text = f"""

【市场情绪实际数据】
{fetcher.format_sentiment_data_for_ai(sentiment_data)}

以上是通过akshare获取的实际市场情绪数据，请重点基于这些数据进行分析。
"""
        
        sentiment_prompt = render_prompt(
            "market_sentiment",
            symbol=stock_info.get("symbol", "N/A"),
            name=stock_info.get("name", "N/A"),
            sector=stock_info.get("sector", "N/A"),
            industry=stock_info.get("industry", "N/A"),
            sentiment_data_text=sentiment_data_text,
        )
        
        messages = [
            {"role": "system", "content": "你是一名专业的市场情绪分析师，擅长解读市场心理和投资者行为，善于利用ARBR等情绪指标进行分析。"},
            {"role": "user", "content": sentiment_prompt}
        ]
        
        analysis = self.deepseek_client.call_api(messages, max_tokens=4000)
        
        return {
            "agent_name": "市场情绪分析师",
            "agent_role": "负责市场情绪研究、投资者心理分析、热点追踪",
            "analysis": analysis,
            "focus_areas": ["ARBR指标", "市场情绪", "投资者心理", "资金活跃度", "恐慌贪婪指数"],
            "sentiment_data": sentiment_data,  # 保存市场情绪数据以供后续使用
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def news_analyst_agent(self, stock_info: Dict, news_data: Dict = None) -> Dict[str, Any]:
        """新闻分析智能体"""
        print("📰 新闻分析师正在分析中...")
        
        # 如果有新闻数据，显示数据来源
        if news_data and news_data.get('data_success'):
            news_count = news_data.get('news_data', {}).get('count', 0) if news_data.get('news_data') else 0
            source = news_data.get('source', 'unknown')
            print(f"   ✓ 已从 {source} 获取 {news_count} 条新闻")
        else:
            print("   ⚠ 未获取到新闻数据，将基于基本信息分析")
        
        time.sleep(1)
        
        # 构建带有新闻数据的prompt
        news_text = ""
        if news_data and news_data.get('data_success'):
            # 使用格式化的新闻数据
            from qstock_news_data import QStockNewsDataFetcher
            fetcher = QStockNewsDataFetcher()
            news_text = f"""

【最新新闻数据】
{fetcher.format_news_for_ai(news_data)}

以上是通过qstock获取的实际新闻数据，请重点基于这些数据进行分析。
"""
        
        news_prompt = render_prompt(
            "news_analysis",
            symbol=stock_info.get("symbol", "N/A"),
            name=stock_info.get("name", "N/A"),
            sector=stock_info.get("sector", "N/A"),
            industry=stock_info.get("industry", "N/A"),
            news_text=news_text,
        )
        
        messages = [
            {"role": "system", "content": "你是一名专业的新闻分析师，擅长解读新闻事件、舆情分析，评估新闻对股价的影响。你具有敏锐的洞察力和丰富的市场经验。"},
            {"role": "user", "content": news_prompt}
        ]
        
        analysis = self.deepseek_client.call_api(messages, max_tokens=4000)
        
        return {
            "agent_name": "新闻分析师",
            "agent_role": "负责新闻事件分析、舆情研究、重大事件影响评估",
            "analysis": analysis,
            "focus_areas": ["新闻解读", "舆情分析", "事件影响", "市场反应", "投资机会"],
            "news_data": news_data,  # 保存新闻数据以供后续使用
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def run_multi_agent_analysis(self, stock_info: Dict, stock_data: Any, indicators: Dict, 
                                 financial_data: Dict = None, fund_flow_data: Dict = None, 
                                 sentiment_data: Dict = None, news_data: Dict = None,
                                 quarterly_data: Dict = None, risk_data: Dict = None,
                                 enabled_analysts: Dict = None,
                                 progress_callback: Callable[[str, str, float], None] = None) -> Dict[str, Any]:
        """运行多智能体分析
        
        Args:
            enabled_analysts: 字典，指定哪些分析师参与分析
                例如: {'technical': True, 'fundamental': True, ...}
                如果为None，则运行所有分析师
        """
        # 如果未指定，默认所有分析师都参与
        if enabled_analysts is None:
            enabled_analysts = {
                'technical': True,
                'fundamental': True,
                'fund_flow': True,
                'risk': True,
                'sentiment': True,
                'news': True
            }
        
        print("🚀 启动多智能体股票分析系统...")
        print("=" * 50)
        
        # 显示参与分析的分析师
        active_analysts = [name for name, enabled in enabled_analysts.items() if enabled]
        print(f"📋 参与分析的分析师: {', '.join(active_analysts)}")
        print("=" * 50)
        
        # 并行运行各个分析师
        agents_results = {}
        analyst_steps = [
            ("technical", "technical", "技术分析师", lambda: self.technical_analyst_agent(stock_info, stock_data, indicators), True),
            ("fundamental", "fundamental", "基本面分析师", lambda: self.fundamental_analyst_agent(stock_info, financial_data, quarterly_data), True),
            ("fund_flow", "fund_flow", "资金面分析师", lambda: self.fund_flow_analyst_agent(stock_info, indicators, fund_flow_data), True),
            ("risk", "risk_management", "风险管理师", lambda: self.risk_management_agent(stock_info, indicators, risk_data), True),
            ("sentiment", "market_sentiment", "市场情绪分析师", lambda: self.market_sentiment_agent(stock_info, sentiment_data), False),
            ("news", "news", "新闻分析师", lambda: self.news_analyst_agent(stock_info, news_data), False),
        ]
        active_steps = [
            step for step in analyst_steps
            if enabled_analysts.get(step[0], step[4])
        ]
        total_steps = max(len(active_steps), 1)
        
        for index, (_, result_key, agent_name, agent_runner, _) in enumerate(active_steps, start=1):
            if progress_callback:
                progress_callback("running", f"{agent_name}正在分析", (index - 1) / total_steps)
            agents_results[result_key] = agent_runner()
            if progress_callback:
                progress_callback("done", f"{agent_name}分析完成", index / total_steps)
        
        print("✅ 所有已选择的分析师完成分析")
        print("=" * 50)
        
        return agents_results
    
    def conduct_team_discussion(self, agents_results: Dict[str, Any], stock_info: Dict) -> str:
        """进行团队讨论"""
        print("🤝 分析团队正在进行综合讨论...")
        time.sleep(2)
        
        # 收集参与分析的分析师名单和报告
        participants = []
        reports = []
        
        if "technical" in agents_results:
            participants.append("技术分析师")
            reports.append(f"【技术分析师报告】\n{agents_results['technical'].get('analysis', '')}")
        
        if "fundamental" in agents_results:
            participants.append("基本面分析师")
            reports.append(f"【基本面分析师报告】\n{agents_results['fundamental'].get('analysis', '')}")
        
        if "fund_flow" in agents_results:
            participants.append("资金面分析师")
            reports.append(f"【资金面分析师报告】\n{agents_results['fund_flow'].get('analysis', '')}")
        
        if "risk_management" in agents_results:
            participants.append("风险管理师")
            reports.append(f"【风险管理师报告】\n{agents_results['risk_management'].get('analysis', '')}")
        
        if "market_sentiment" in agents_results:
            participants.append("市场情绪分析师")
            reports.append(f"【市场情绪分析师报告】\n{agents_results['market_sentiment'].get('analysis', '')}")
        
        if "news" in agents_results:
            participants.append("新闻分析师")
            reports.append(f"【新闻分析师报告】\n{agents_results['news'].get('analysis', '')}")
        
        # 组合所有报告
        all_reports = "\n\n".join(reports)
        
        discussion_prompt = render_prompt(
            "team_discussion",
            participants=", ".join(participants),
            name=stock_info.get("name", "N/A"),
            symbol=stock_info.get("symbol", "N/A"),
            all_reports=all_reports,
        )
        
        messages = [
            {"role": "system", "content": "你需要模拟一场专业的投资团队讨论会议，体现不同角色的观点碰撞和最终共识形成。"},
            {"role": "user", "content": discussion_prompt}
        ]
        
        discussion_result = self.deepseek_client.call_api(messages, max_tokens=6000)
        
        print("✅ 团队讨论完成")
        return discussion_result
    
    def make_final_decision(self, discussion_result: str, stock_info: Dict, indicators: Dict) -> Dict[str, Any]:
        """制定最终投资决策"""
        print("📋 正在制定最终投资决策...")
        time.sleep(1)
        
        decision = self.deepseek_client.final_decision(discussion_result, stock_info, indicators)
        
        print("✅ 最终投资决策完成")
        return decision
