"""
智囊团游资龙虎榜AI分析师集群
专注于龙虎榜数据的多维度分析
"""

from deepseek_client import DeepSeekClient
from prompts import render as render_prompt


def _fmt_amount(v) -> str:
    """格式化金额:数字 -> 千分位 2 位小数,否则原样转字符串。"""
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)
from typing import Dict, Any, List
import time
import config


class LonghubangAgents:
    """龙虎榜AI分析师集合"""
    
    def __init__(self, model=None):
        self.model = model or config.DEFAULT_MODEL_NAME
        self.deepseek_client = DeepSeekClient(model=self.model)
        print(f"[智囊团游资龙虎榜] AI分析师系统初始化 (模型: {self.model})")
    
    def youzi_behavior_analyst(self, longhubang_data: str, summary: Dict) -> Dict[str, Any]:
        """
        游资行为分析师 - 分析游资操作特征和意图
        
        职责：
        - 识别活跃游资及其操作风格
        - 分析游资席位的进出特征
        - 研判游资对个股的态度
        """
        print("🎯 游资行为分析师正在分析...")
        time.sleep(1)
        
        # 构建游资统计信息
        youzi_info = ""
        if summary.get('top_youzi'):
            youzi_info = "\n【活跃游资统计】\n"
            for idx, (name, amount) in enumerate(list(summary['top_youzi'].items())[:15], 1):
                youzi_info += f"{idx}. {name}: 净流入 {amount:,.2f} 元\n"
        
        prompt = render_prompt(
            "longhubang_youzi_behavior",
            total_records=summary.get("total_records", 0),
            total_stocks=summary.get("total_stocks", 0),
            total_youzi=summary.get("total_youzi", 0),
            total_buy_amount=_fmt_amount(summary.get("total_buy_amount", 0)),
            total_sell_amount=_fmt_amount(summary.get("total_sell_amount", 0)),
            total_net_inflow=_fmt_amount(summary.get("total_net_inflow", 0)),
            youzi_info=youzi_info,
            longhubang_data=longhubang_data[:8000],
        )
        
        messages = [
            {"role": "system", "content": "你是一名资深的游资研究专家，擅长从龙虎榜数据中洞察游资意图和操作手法。"},
            {"role": "user", "content": prompt}
        ]
        
        analysis = self.deepseek_client.call_api(messages, max_tokens=4000)
        
        print("  ✓ 游资行为分析师分析完成")
        
        return {
            "agent_name": "游资行为分析师",
            "agent_role": "分析游资操作特征、意图和目标股票",
            "analysis": analysis,
            "focus_areas": ["游资画像", "操作风格", "目标股票", "进出节奏", "题材偏好"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def stock_potential_analyst(self, longhubang_data: str, summary: Dict) -> Dict[str, Any]:
        """
        个股潜力分析师 - 从龙虎榜数据挖掘潜力股
        
        职责：
        - 分析上榜股票的资金动向
        - 评估股票的上涨潜力
        - 识别次日大概率上涨的股票
        """
        print("📈 个股潜力分析师正在分析...")
        time.sleep(1)
        
        # 构建股票统计信息
        stock_info = ""
        if summary.get('top_stocks'):
            stock_info = "\n【热门股票统计】\n"
            for idx, stock in enumerate(summary['top_stocks'][:20], 1):
                stock_info += f"{idx}. {stock['name']}({stock['code']}): 净流入 {stock['net_inflow']:,.2f} 元\n"
        
        prompt = render_prompt(
            "longhubang_stock_potential",
            total_records=summary.get("total_records", 0),
            total_stocks=summary.get("total_stocks", 0),
            total_youzi=summary.get("total_youzi", 0),
            stock_info=stock_info,
            longhubang_data=longhubang_data[:8000],
        )
        
        messages = [
            {"role": "system", "content": "你是一名资深的个股研究专家和短线交易高手，擅长从龙虎榜中挖掘短期爆发股。"},
            {"role": "user", "content": prompt}
        ]
        
        analysis = self.deepseek_client.call_api(messages, max_tokens=4000)
        
        print("  ✓ 个股潜力分析师分析完成")
        
        return {
            "agent_name": "个股潜力分析师",
            "agent_role": "挖掘次日大概率上涨的潜力股票",
            "analysis": analysis,
            "focus_areas": ["潜力股挖掘", "资金流向", "技术形态", "题材概念", "操作策略"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def theme_tracker_analyst(self, longhubang_data: str, summary: Dict) -> Dict[str, Any]:
        """
        题材追踪分析师 - 分析龙虎榜中的热点题材
        
        职责：
        - 识别当前热点题材和概念
        - 分析题材的炒作周期
        - 预判题材的持续性
        """
        print("🔥 题材追踪分析师正在分析...")
        time.sleep(1)
        
        # 构建概念统计信息
        concept_info = ""
        if summary.get('hot_concepts'):
            concept_info = "\n【热门概念统计】\n"
            for idx, (concept, count) in enumerate(list(summary['hot_concepts'].items())[:20], 1):
                concept_info += f"{idx}. {concept}: 出现 {count} 次\n"
        
        prompt = render_prompt(
            "longhubang_theme_tracker",
            total_records=summary.get("total_records", 0),
            total_stocks=summary.get("total_stocks", 0),
            concept_info=concept_info,
            longhubang_data=longhubang_data[:8000],
        )
        
        messages = [
            {"role": "system", "content": "你是一名资深的题材研究专家，擅长从龙虎榜数据中捕捉题材热点和投资机会。"},
            {"role": "user", "content": prompt}
        ]
        
        analysis = self.deepseek_client.call_api(messages, max_tokens=4000)
        
        print("  ✓ 题材追踪分析师分析完成")
        
        return {
            "agent_name": "题材追踪分析师",
            "agent_role": "识别热点题材，分析炒作周期，预判轮动方向",
            "analysis": analysis,
            "focus_areas": ["热点题材", "炒作周期", "龙头梯队", "题材轮动", "风险评估"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def risk_control_specialist(self, longhubang_data: str, summary: Dict) -> Dict[str, Any]:
        """
        风险控制专家 - 识别龙虎榜中的风险信号
        
        职责：
        - 识别高风险股票和陷阱
        - 分析游资出货信号
        - 提供风险管理建议
        """
        print("⚠️ 风险控制专家正在分析...")
        time.sleep(1)
        
        prompt = render_prompt(
            "longhubang_risk_control",
            total_records=summary.get("total_records", 0),
            total_stocks=summary.get("total_stocks", 0),
            total_youzi=summary.get("total_youzi", 0),
            total_buy_amount=_fmt_amount(summary.get("total_buy_amount", 0)),
            total_sell_amount=_fmt_amount(summary.get("total_sell_amount", 0)),
            total_net_inflow=_fmt_amount(summary.get("total_net_inflow", 0)),
            longhubang_data=longhubang_data[:8000],
        )
        
        messages = [
            {"role": "system", "content": "你是一名资深的风险控制专家，擅长识别龙虎榜中的风险信号和资金陷阱。"},
            {"role": "user", "content": prompt}
        ]
        
        analysis = self.deepseek_client.call_api(messages, max_tokens=4000)
        
        print("  ✓ 风险控制专家分析完成")
        
        return {
            "agent_name": "风险控制专家",
            "agent_role": "识别高风险股票、游资出货信号和市场陷阱",
            "analysis": analysis,
            "focus_areas": ["高风险股票", "出货信号", "资金陷阱", "题材风险", "风险管理"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def chief_strategist(self, all_analyses: List[Dict]) -> Dict[str, Any]:
        """
        首席策略师 - 综合所有分析师的意见，给出最终投资建议
        
        职责：
        - 整合多维度分析结果
        - 给出最终推荐股票清单
        - 提供具体操作策略
        """
        print("👔 首席策略师正在综合分析...")
        time.sleep(1)
        
        # 整合所有分析师的分析结果
        analyses_text = ""
        for analysis in all_analyses:
            analyses_text += f"\n{'='*60}\n"
            analyses_text += f"【{analysis['agent_name']}】分析报告\n"
            analyses_text += f"职责: {analysis['agent_role']}\n"
            analyses_text += f"{'='*60}\n"
            analyses_text += analysis['analysis'] + "\n"
        
        prompt = render_prompt(
            "longhubang_chief_strategist",
            analyses_text=analyses_text[:15000],
        )
        
        messages = [
            {"role": "system", "content": "你是一名资深的首席投资策略师，擅长综合多维度分析，给出最优投资决策。"},
            {"role": "user", "content": prompt}
        ]
        
        analysis = self.deepseek_client.call_api(messages, max_tokens=5000)
        
        print("  ✓ 首席策略师分析完成")
        
        return {
            "agent_name": "首席策略师",
            "agent_role": "综合多维度分析，给出最终投资建议和推荐股票清单",
            "analysis": analysis,
            "focus_areas": ["综合研判", "推荐股票", "风险警示", "热点题材", "操作策略"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }


# 测试函数
if __name__ == "__main__":
    print("=" * 60)
    print("测试智囊团游资龙虎榜AI分析师系统")
    print("=" * 60)
    
    # 创建模拟数据
    test_summary = {
        'total_records': 150,
        'total_stocks': 50,
        'total_youzi': 30,
        'total_buy_amount': 500000000,
        'total_sell_amount': 200000000,
        'total_net_inflow': 300000000,
        'top_youzi': {
            '92科比': 14455321,
            '赵老哥': 12000000,
            '章盟主': 10000000
        },
        'top_stocks': [
            {'code': '001337', 'name': '四川黄金', 'net_inflow': 14455321}
        ],
        'hot_concepts': {
            '黄金概念': 10,
            '新能源': 8,
            'ChatGPT': 7
        }
    }
    
    test_data = """
【详细交易记录 TOP50】
92科比 | 四川黄金(001337) | 买入:14,470,401 卖出:15,080 净流入:14,455,321 | 日期:2023-03-22
"""
    
    agents = LonghubangAgents()
    
    # 测试游资行为分析师
    print("\n测试游资行为分析师...")
    result = agents.youzi_behavior_analyst(test_data, test_summary)
    print(f"分析师: {result['agent_name']}")
    print(f"分析内容长度: {len(result['analysis'])} 字符")
