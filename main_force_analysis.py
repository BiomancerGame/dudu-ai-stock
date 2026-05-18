#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主力选股AI分析整合模块
整体批量分析，从板块热点和资金流向角度筛选优质标的
"""

from typing import Callable, Dict, List, Tuple
import pandas as pd
from main_force_selector import main_force_selector
from stock_data import StockDataFetcher
from ai_agents import StockAnalysisAgents
from deepseek_client import DeepSeekClient
from technical_pattern_scorer import TechnicalPatternScorer
import time
import json
import config

class MainForceAnalyzer:
    """主力选股分析器 - 批量整体分析"""
    
    def __init__(self, model=None):
        self.selector = main_force_selector
        self.fetcher = StockDataFetcher()
        self.model = model or config.DEFAULT_MODEL_NAME
        self.agents = StockAnalysisAgents(model=self.model)
        self.deepseek_client = self.agents.deepseek_client
        self.pattern_scorer = TechnicalPatternScorer(period="6mo")
        self.raw_stocks = None
        self.final_recommendations = []
    
    def run_full_analysis(self, start_date: str = None, days_ago: int = None, 
                         final_n: int = None, max_range_change: float = None,
                         min_market_cap: float = None, max_market_cap: float = None,
                         progress_callback: Callable[[str, int], None] = None) -> Dict:
        """
        运行完整的主力选股分析流程 - 整体批量分析
        
        Args:
            start_date: 开始日期，格式如"2025年10月1日"
            days_ago: 距今多少天
            final_n: 最终精选N只
            max_range_change: 最大涨跌幅限制
            min_market_cap: 最小市值限制
            max_market_cap: 最大市值限制
            
        Returns:
            分析结果字典
        """
        result = {
            'success': False,
            'total_stocks': 0,
            'filtered_stocks': 0,
            'final_recommendations': [],
            'error': None,
            'params': {
                'start_date': start_date,
                'days_ago': days_ago,
                'final_n': final_n,
                'max_range_change': max_range_change,
                'min_market_cap': min_market_cap,
                'max_market_cap': max_market_cap
            }
        }
        
        try:
            def emit(message, percent):
                if progress_callback:
                    progress_callback(message, percent)

            print(f"\n{'='*80}")
            print(f"🚀 主力选股智能分析系统 - 批量整体分析")
            print(f"{'='*80}\n")
            
            # 步骤1: 获取主力资金净流入前100名股票
            emit("正在获取主力资金净流入股票池", 8)
            success, raw_data, message = self.selector.get_main_force_stocks(
                start_date=start_date,
                days_ago=days_ago,
                min_market_cap=min_market_cap,
                max_market_cap=max_market_cap
            )
            
            if not success:
                result['error'] = message
                return result
            
            result['total_stocks'] = len(raw_data)
            emit(f"股票池获取完成，共 {len(raw_data)} 只", 22)
            
            # 步骤2: 智能筛选（涨幅、市值等）
            emit("正在按涨幅、市值等条件筛选候选股", 28)
            filtered_data = self.selector.filter_stocks(
                raw_data,
                max_range_change=max_range_change,
                min_market_cap=min_market_cap,
                max_market_cap=max_market_cap
            )
            
            result['filtered_stocks'] = len(filtered_data)
            emit(f"候选筛选完成，保留 {len(filtered_data)} 只", 36)
            
            if filtered_data.empty:
                result['error'] = "筛选后没有符合条件的股票"
                return result

            # 步骤2.5: 技术形态评分（加分项，不做硬过滤）
            print(f"\n{'='*80}")
            print(f"📐 技术形态评分中...")
            print(f"{'='*80}\n")
            emit("正在计算技术形态评分", 42)
            filtered_data = self.pattern_scorer.score_dataframe(filtered_data)
            emit("技术形态评分完成", 50)
            
            # 保存原始数据
            self.raw_stocks = filtered_data
            
            # 步骤3: 整体数据分析（不是逐个分析）
            print(f"\n{'='*80}")
            print(f"🤖 AI分析师团队开始整体分析...")
            print(f"{'='*80}\n")
            emit("正在生成整体数据摘要", 54)
            
            # 准备整体数据摘要
            overall_summary = self._prepare_overall_summary(filtered_data)
            
            # 四位分析师整体分析
            emit("资金流向分析师正在分析", 60)
            fund_flow_analysis = self._fund_flow_overall_analysis(filtered_data, overall_summary)
            emit("行业板块分析师正在分析", 67)
            industry_analysis = self._industry_overall_analysis(filtered_data, overall_summary)
            emit("财务基本面分析师正在分析", 74)
            fundamental_analysis = self._fundamental_overall_analysis(filtered_data, overall_summary)
            emit("技术形态分析师正在分析", 81)
            technical_pattern_analysis = self._technical_pattern_overall_analysis(filtered_data, overall_summary)
            emit("四位分析师报告生成完成", 88)
            
            # 保存分析报告到对象属性，供UI展示
            self.fund_flow_analysis = fund_flow_analysis
            self.industry_analysis = industry_analysis
            self.fundamental_analysis = fundamental_analysis
            self.technical_pattern_analysis = technical_pattern_analysis
            
            # 步骤4: 综合决策，精选优质标的
            print(f"\n{'='*80}")
            print(f"👔 资深研究员综合评估并精选标的...")
            print(f"{'='*80}\n")
            emit("资深研究员正在综合评分并精选推荐", 92)
            
            final_recommendations = self._select_best_stocks(
                filtered_data,
                fund_flow_analysis,
                industry_analysis,
                fundamental_analysis,
                technical_pattern_analysis,
                final_n=final_n
            )
            
            result['final_recommendations'] = final_recommendations
            result['success'] = True
            emit("精选推荐生成完成", 100)
            
            # 显示最终结果
            self._print_final_recommendations(final_recommendations)
            
            return result
            
        except Exception as e:
            result['error'] = f"分析过程出错: {str(e)}"
            import traceback
            traceback.print_exc()
            return result
    
    def _prepare_overall_summary(self, df: pd.DataFrame) -> str:
        """准备整体数据摘要"""
        
        summary_lines = []
        summary_lines.append(f"候选股票总数: {len(df)}只")
        
        # 主力资金统计
        main_fund_cols = [col for col in df.columns if '主力' in col and '净流入' in col]
        if main_fund_cols:
            col_name = main_fund_cols[0]
            df[col_name] = pd.to_numeric(df[col_name], errors='coerce')
            total_inflow = df[col_name].sum()
            avg_inflow = df[col_name].mean()
            summary_lines.append(f"主力资金总净流入: {total_inflow/100000000:.2f}亿")
            summary_lines.append(f"平均主力资金净流入: {avg_inflow/100000000:.2f}亿")
        
        # 涨跌幅统计
        range_cols = [col for col in df.columns if '涨跌幅' in col]
        if range_cols:
            col_name = range_cols[0]
            df[col_name] = pd.to_numeric(df[col_name], errors='coerce')
            avg_change = df[col_name].mean()
            max_change = df[col_name].max()
            min_change = df[col_name].min()
            summary_lines.append(f"平均涨跌幅: {avg_change:.2f}%")
            summary_lines.append(f"涨跌幅范围: {min_change:.2f}% ~ {max_change:.2f}%")
        
        # 行业分布
        industry_cols = [col for col in df.columns if '行业' in col]
        if industry_cols:
            col_name = industry_cols[0]
            top_industries = df[col_name].value_counts().head(10)
            summary_lines.append("\n主要行业分布:")
            for industry, count in top_industries.items():
                summary_lines.append(f"  - {industry}: {count}只")
        
        return "\n".join(summary_lines)
    
    def _fund_flow_overall_analysis(self, df: pd.DataFrame, summary: str) -> str:
        """资金流向整体分析"""
        
        print("💰 资金流向分析师整体分析中...")
        
        # 准备数据表格
        data_table = self._prepare_data_table(df, focus='fund_flow')
        
        prompt = f"""
你是一名资深的资金面分析师，现在需要你从整体角度分析这批主力资金净流入的股票。

【整体数据摘要】
{summary}

【候选股票详细数据】（共{len(df)}只）
{data_table}

【分析任务】
请从资金流向的整体角度进行分析，重点关注：

1. **资金流向特征**
   - 哪些板块/行业资金流入最集中？
   - 主力资金的整体行为特征（大规模建仓/试探性进场/板块轮动）
   - 资金流向与涨跌幅的配合情况

2. **优质标的识别**
   - 从资金面角度，哪些股票最值得关注？
   - 主力资金流入大但涨幅不高的潜力股
   - 资金持续流入且趋势明确的股票

3. **板块热点判断**
   - 当前资金最看好哪些板块？
   - 是否有板块轮动迹象？
   - 新兴热点 vs 传统强势板块

4. **投资建议**
   - 从资金面角度，建议重点关注哪3-5只股票？
   - 理由和风险提示

请给出专业、系统的资金面整体分析报告。
"""
        
        messages = [
            {"role": "system", "content": "你是资金面分析专家，擅长从整体资金流向中发现投资机会。"},
            {"role": "user", "content": prompt}
        ]
        
        analysis = self.deepseek_client.call_api(messages, max_tokens=4000)
        
        print("  ✅ 资金流向整体分析完成")
        time.sleep(1)
        
        return analysis
    
    def _industry_overall_analysis(self, df: pd.DataFrame, summary: str) -> str:
        """行业板块整体分析"""
        
        print("📊 行业板块分析师整体分析中...")
        
        # 准备数据表格
        data_table = self._prepare_data_table(df, focus='industry')
        
        prompt = f"""
你是一名资深的行业板块分析师，现在需要你从行业热点和板块轮动角度分析这批股票。

【整体数据摘要】
{summary}

【候选股票详细数据】（共{len(df)}只）
{data_table}

【分析任务】
请从行业板块的整体角度进行分析，重点关注：

1. **热点板块识别**
   - 哪些行业/板块最受资金青睐？
   - 热点板块的持续性如何？
   - 是否有新兴热点正在形成？

2. **板块特征分析**
   - 各板块的涨幅与资金流入匹配度
   - 哪些板块处于启动阶段（资金流入但涨幅不大）
   - 哪些板块可能过热（涨幅高但资金流入减弱）

3. **行业前景评估**
   - 主力资金集中的行业，基本面支撑如何？
   - 政策面、产业面是否有催化因素？
   - 行业竞争格局和龙头地位

4. **优质标的推荐**
   - 从行业板块角度，推荐3-5只最具潜力的股票
   - 推荐理由（行业地位、成长空间、催化因素）

请给出专业、深入的行业板块分析报告。
"""
        
        messages = [
            {"role": "system", "content": "你是行业板块分析专家，擅长发现市场热点和板块机会。"},
            {"role": "user", "content": prompt}
        ]
        
        analysis = self.deepseek_client.call_api(messages, max_tokens=4000)
        
        print("  ✅ 行业板块整体分析完成")
        time.sleep(1)
        
        return analysis
    
    def _fundamental_overall_analysis(self, df: pd.DataFrame, summary: str) -> str:
        """财务基本面整体分析"""
        
        print("📈 财务基本面分析师整体分析中...")
        
        # 准备数据表格
        data_table = self._prepare_data_table(df, focus='fundamental')
        
        prompt = f"""
你是一名资深的基本面分析师，现在需要你从财务质量和基本面角度分析这批股票。

【整体数据摘要】
{summary}

【候选股票详细数据】（共{len(df)}只）
{data_table}

【分析任务】
请从财务基本面的整体角度进行分析，重点关注：

1. **财务质量评估**
   - 整体财务指标健康度如何？
   - 哪些股票盈利能力、成长性突出？
   - 是否存在财务风险较大的股票？

2. **估值水平分析**
   - 市盈率、市净率的整体分布
   - 哪些股票估值合理且有成长空间？
   - 高估值是否有业绩支撑？

3. **成长性评估**
   - 营收、净利润增长情况
   - 哪些股票成长性最好？
   - 成长能力评分较高的股票

4. **优质标的筛选**
   - 从基本面角度，推荐3-5只最优质的股票
   - 推荐理由（财务健康、估值合理、成长性好）

请给出专业、详实的基本面分析报告。
"""
        
        messages = [
            {"role": "system", "content": "你是基本面分析专家，擅长从财务角度评估投资价值。"},
            {"role": "user", "content": prompt}
        ]
        
        analysis = self.deepseek_client.call_api(messages, max_tokens=4000)
        
        print("  ✅ 财务基本面整体分析完成")
        time.sleep(1)
        
        return analysis

    def _technical_pattern_overall_analysis(self, df: pd.DataFrame, summary: str) -> str:
        """技术形态整体分析"""

        print("📐 技术形态分析师整体分析中...")

        data_table = self._prepare_data_table(df, focus='technical')

        prompt = f"""
你是一名资深技术形态分析师，现在需要你从趋势结构、突破形态、量价配合角度分析这批股票。

【整体数据摘要】
{summary}

【候选股票形态数据】（共{len(df)}只）
{data_table}

【分析任务】
请从技术形态角度进行分析，重点关注：

1. **趋势结构**
   - 哪些股票处于均线多头或中期上升趋势？
   - 哪些股票形态评分最高，趋势确认度最好？

2. **突破与量价**
   - 哪些股票出现20日/60日高点突破？
   - 突破是否有成交量配合？
   - 哪些股票是温和放量，哪些可能短线过热？

3. **回踩与风控**
   - 哪些股票靠近MA20并出现企稳迹象？
   - 哪些股票虽然资金强，但形态还没有确认？

4. **技术面建议**
   - 从形态角度，建议重点关注哪3-5只股票？
   - 给出形态理由和需要观察的失效条件。

请给出专业、简洁、可执行的技术形态分析报告。
"""

        messages = [
            {"role": "system", "content": "你是技术形态分析专家，擅长趋势、突破、量价关系和风险位置判断。"},
            {"role": "user", "content": prompt}
        ]

        analysis = self.deepseek_client.call_api(messages, max_tokens=4000)

        print("  ✅ 技术形态整体分析完成")
        time.sleep(1)

        return analysis
    
    def _prepare_data_table(self, df: pd.DataFrame, focus: str = 'all') -> str:
        """准备数据表格用于AI分析"""
        
        # 选择关键列
        key_columns = ['股票代码', '股票简称']
        
        # 根据分析重点添加相关列
        if focus == 'fund_flow' or focus == 'all':
            fund_cols = [col for col in df.columns if '主力' in col or '资金' in col]
            key_columns.extend(fund_cols[:3])  # 最多3列资金数据
        
        if focus == 'industry' or focus == 'all':
            industry_cols = [col for col in df.columns if '行业' in col]
            key_columns.extend(industry_cols[:1])
        
        # 智能匹配区间涨跌幅列
        interval_pct_col = None
        possible_names = [
            '区间涨跌幅:前复权', '区间涨跌幅:前复权(%)', '区间涨跌幅(%)', 
            '区间涨跌幅', '涨跌幅:前复权', '涨跌幅:前复权(%)', '涨跌幅(%)', '涨跌幅'
        ]
        for name in possible_names:
            for col in df.columns:
                if name in col:
                    interval_pct_col = col
                    break
            if interval_pct_col:
                break
        if interval_pct_col:
            key_columns.append(interval_pct_col)
        
        if focus == 'fundamental' or focus == 'all':
            fundamental_cols = [col for col in df.columns if any(
                keyword in col for keyword in ['市盈率', '市净率', '营收', '净利润', '评分']
            )]
            key_columns.extend(fundamental_cols[:5])

        if focus in ('technical', 'all'):
            pattern_cols = [col for col in ['形态评分', '形态等级', '形态标签'] if col in df.columns]
            key_columns.extend(pattern_cols)
        
        # 去重并保持顺序
        seen = set()
        unique_columns = []
        for col in key_columns:
            if col in df.columns and col not in seen:
                seen.add(col)
                unique_columns.append(col)
        
        # 限制显示前50只股票的详细数据，避免超出token限制
        display_df = df[unique_columns].head(50)
        
        # 转换为表格字符串
        table_str = display_df.to_string(index=False, max_rows=50)
        
        if len(df) > 50:
            table_str += f"\n... 还有 {len(df) - 50} 只股票未显示"
        
        return table_str
    
    def _select_best_stocks(self, df: pd.DataFrame, 
                           fund_analysis: str, 
                           industry_analysis: str,
                           fundamental_analysis: str,
                           technical_pattern_analysis: str,
                           final_n: int = 5) -> List[Dict]:
        """综合四位分析师的意见，精选最优标的"""
        
        # 准备完整数据表格
        data_table = self._prepare_data_table(df, focus='all')
        
        prompt = f"""
你是一名资深股票研究员，具有20年以上的投资研究经验。现在需要你综合四位分析师的意见，
从{len(df)}只候选股票中精选出{final_n}只最具投资价值的优质标的。

【候选股票数据】
{data_table}

【资金流向分析师观点】
{fund_analysis}

【行业板块分析师观点】
{industry_analysis}

【财务基本面分析师观点】
{fundamental_analysis}

【技术形态分析师观点】
{technical_pattern_analysis}

【筛选标准】
1. **主力资金**: 主力资金净流入较多，显示机构看好
2. **涨幅适中**: 区间涨跌幅不是很高（避免追高），还有上涨空间
3. **行业热点**: 所属行业有发展前景，是市场热点
4. **基本面良好**: 财务指标健康，盈利能力强
5. **技术形态**: 均线、突破、量能、MACD等形态条件较好
6. **综合平衡**: 资金、行业、基本面、形态四方面都不错

【任务要求】
综合四位分析师的观点，精选出{final_n}只最优标的。

对于每只精选股票，请提供：
1. **股票代码和名称**
2. **核心推荐理由**（3-5条，综合资金、行业、基本面、技术形态）
3. **投资亮点**（最突出的优势）
4. **风险提示**（需要注意的风险）
5. **建议仓位**（如20-30%）
6. **投资周期**（短期/中期/长期）

请按以下JSON格式输出（只输出JSON，不要其他内容）：
```json
{{
  "recommendations": [
    {{
      "rank": 1,
      "symbol": "股票代码",
      "name": "股票名称",
      "reasons": [
        "理由1：资金面角度",
        "理由2：行业板块角度", 
        "理由3：基本面角度"
      ],
      "highlights": "投资亮点描述",
      "risks": "风险提示",
      "position": "建议仓位",
      "investment_period": "投资周期",
      "scores": {{
        "fund_flow": 0,
        "industry": 0,
        "fundamental": 0,
        "technical_pattern": 0,
        "overall": 0
      }}
    }}
  ]
}}
```

注意：
- 必须严格按照JSON格式输出
- 推荐数量为{final_n}只
- 按投资价值从高到低排序
- 理由要具体、有说服力，体现四位分析师的综合观点
"""
        
        try:
            print("  🔍 正在综合评估并精选标的...")
            
            messages = [
                {"role": "system", "content": "你是资深股票研究员，擅长综合多维度分析做出投资决策。"},
                {"role": "user", "content": prompt}
            ]
            
            response = self.deepseek_client.call_api(messages, max_tokens=4000)
            
            # 解析JSON响应
            import re
            
            # 提取JSON部分
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析
                json_str = response
            
            result = json.loads(json_str)
            recommendations = result.get('recommendations', [])
            
            # 补充详细数据
            for rec in recommendations:
                symbol = rec['symbol']
                # 从原始数据中找到对应股票
                stock_data = df[df['股票代码'] == symbol]
                if not stock_data.empty:
                    row_dict = stock_data.iloc[0].to_dict()
                    rec['scores'] = self._normalize_scores(rec, row_dict)
                    self._sync_pattern_fields(row_dict, rec['scores'])
                    for score_key, score_value in rec['scores'].items():
                        row_dict[f"分值_{score_key}"] = score_value
                    rec['stock_data'] = row_dict
            
            return recommendations
            
        except Exception as e:
            print(f"  ❌ JSON解析失败，使用备选方案: {e}")
            
            # 降级方案：按主力资金排序返回前N个
            main_fund_cols = [col for col in df.columns if '主力' in col and '净流入' in col]
            if main_fund_cols:
                col_name = main_fund_cols[0]
                df[col_name] = pd.to_numeric(df[col_name], errors='coerce')
                sorted_df = df.nlargest(final_n, col_name)
            else:
                sorted_df = df.head(final_n)
            
            recommendations = []
            for i, (idx, row) in enumerate(sorted_df.iterrows(), 1):
                recommendations.append({
                    'rank': i,
                    'symbol': row.get('股票代码', 'N/A'),
                    'name': row.get('股票简称', 'N/A'),
                    'reasons': [
                        f"主力资金净流入较多",
                        f"所属行业: {row.get('所属同花顺行业', 'N/A')}",
                        f"涨跌幅适中"
                    ],
                    'highlights': '主力资金持续关注',
                    'risks': '需关注后续走势',
                    'position': '15-25%',
                    'investment_period': '中短期',
                    'stock_data': row.to_dict(),
                    'scores': self._normalize_scores({}, row.to_dict())
                })
                self._sync_pattern_fields(recommendations[-1]['stock_data'], recommendations[-1]['scores'])
                for score_key, score_value in recommendations[-1]['scores'].items():
                    recommendations[-1]['stock_data'][f"分值_{score_key}"] = score_value
            
            return recommendations

    def _normalize_scores(self, rec: Dict, stock_data: Dict) -> Dict:
        """标准化推荐分值，保证UI可显示每项具体分值。"""
        raw_scores = rec.get('scores') if isinstance(rec.get('scores'), dict) else {}

        def safe_score(value, default):
            try:
                if value is None or value == 'N/A':
                    return int(default)
                return max(0, min(100, int(float(value))))
            except Exception:
                return int(default)

        technical = safe_score(raw_scores.get('technical_pattern'), stock_data.get('形态评分', 50))
        fund_flow = safe_score(raw_scores.get('fund_flow'), self._infer_fund_score(stock_data))
        industry = safe_score(raw_scores.get('industry'), 75)
        fundamental = safe_score(raw_scores.get('fundamental'), self._infer_fundamental_score(stock_data))
        overall_default = round(fund_flow * 0.3 + industry * 0.2 + fundamental * 0.25 + technical * 0.25)
        overall = safe_score(raw_scores.get('overall'), overall_default)

        return {
            'fund_flow': fund_flow,
            'industry': industry,
            'fundamental': fundamental,
            'technical_pattern': technical,
            'overall': overall,
        }

    def _sync_pattern_fields(self, stock_data: Dict, scores: Dict) -> None:
        """让推荐明细里的形态评分、等级、标签保持同一口径。"""
        technical = scores.get('technical_pattern', stock_data.get('形态评分', 0))
        try:
            technical = max(0, min(100, int(float(technical))))
        except Exception:
            technical = 0

        stock_data['形态评分'] = technical
        existing_tags = stock_data.get('形态标签')
        has_meaningful_tags = bool(existing_tags) and existing_tags not in ['无', '无明显形态', 'N/A']
        if technical >= 85:
            stock_data['形态等级'] = '强势形态'
            stock_data['形态标签'] = existing_tags if has_meaningful_tags else '平台突破、量价配合、趋势确认'
        elif technical >= 70:
            stock_data['形态等级'] = '形态良好'
            stock_data['形态标签'] = existing_tags if has_meaningful_tags else '趋势向上、资金配合'
        elif technical >= 55:
            stock_data['形态等级'] = '形态一般'
            stock_data['形态标签'] = existing_tags if has_meaningful_tags else '有一定形态信号'
        elif technical > 0:
            stock_data['形态等级'] = '弱信号'
            stock_data['形态标签'] = existing_tags if has_meaningful_tags else '形态信号偏弱'
        else:
            stock_data['形态等级'] = stock_data.get('形态等级') or '无数据'
            stock_data['形态标签'] = stock_data.get('形态标签') or '无明显形态'

    def _infer_fund_score(self, stock_data: Dict) -> int:
        fund_keys = [k for k in stock_data.keys() if '主力' in k and ('净流入' in k or '流向' in k)]
        if not fund_keys:
            return 70
        try:
            fund_value = float(stock_data.get(fund_keys[0], 0))
            if fund_value >= 300000000:
                return 92
            if fund_value >= 100000000:
                return 85
            if fund_value > 0:
                return 75
        except Exception:
            pass
        return 65

    def _infer_fundamental_score(self, stock_data: Dict) -> int:
        score_keys = [k for k in stock_data.keys() if '评分' in k or '能力' in k]
        values = []
        for key in score_keys:
            try:
                values.append(float(stock_data.get(key)))
            except Exception:
                continue
        if values:
            avg = sum(values) / len(values)
            if avg <= 10:
                return int(avg * 10)
            return max(0, min(100, int(avg)))
        return 72
    
    def _print_final_recommendations(self, recommendations: List[Dict]):
        """打印最终推荐结果"""
        if not recommendations:
            print("❌ 未能生成推荐结果")
            return
        
        print(f"\n{'='*80}")
        print(f"⭐ 最终精选推荐 ({len(recommendations)}只)")
        print(f"{'='*80}\n")
        
        for rec in recommendations:
            print(f"【第{rec['rank']}名】{rec['symbol']} - {rec['name']}")
            print(f"{'-'*60}")
            
            print(f"📌 推荐理由:")
            for reason in rec.get('reasons', []):
                print(f"   • {reason}")
            
            print(f"\n💡 投资亮点: {rec.get('highlights', 'N/A')}")
            print(f"⚠️  风险提示: {rec.get('risks', 'N/A')}")
            print(f"📊 建议仓位: {rec.get('position', 'N/A')}")
            print(f"⏰ 投资周期: {rec.get('investment_period', 'N/A')}")
            print(f"{'='*80}\n")

# 全局实例
main_force_analyzer = MainForceAnalyzer()
