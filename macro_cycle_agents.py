"""
宏观周期分析 - AI智能体模块
包含四位专业分析师：康波周期分析师、美林时钟分析师、中国政策分析师、首席宏观策略师
"""

from deepseek_client import DeepSeekClient
from prompts import render as render_prompt
from typing import Dict, Any
import time
import config


class MacroCycleAgents:
    """宏观周期AI智能体集合"""

    def __init__(self, model=None):
        self.model = model or config.DEFAULT_MODEL_NAME
        self.deepseek_client = DeepSeekClient(model=self.model)
        print(f"[宏观周期] AI智能体系统初始化 (模型: {self.model})")

    def kondratieff_wave_agent(self, macro_data_text: str) -> Dict[str, Any]:
        """
        康波周期分析师 - 判断当前处于康德拉季耶夫长波的哪个阶段

        职责：
        - 分析当前技术革命阶段（第五轮信息技术康波的位置）
        - 判断回升/繁荣/衰退/萧条四阶段中的位置
        - 分析大宗商品与康波的关系
        - 给出战略性资产配置方向
        """
        print("🌊 康波周期分析师正在分析...")
        time.sleep(1)

        prompt = render_prompt(
            "macro_kondratieff",
            macro_data_text=macro_data_text,
        )
        messages = [
            {"role": "system", "content": "你是全球顶尖的康德拉季耶夫长波周期研究专家，深研周金涛的理论体系，擅长将60年长周期框架应用于当前经济形势分析，帮助投资者做出战略性决策。"},
            {"role": "user", "content": prompt}
        ]

        analysis = self.deepseek_client.call_api(messages, max_tokens=6000)
        print("  ✓ 康波周期分析师分析完成")

        return {
            "agent_name": "康波周期分析师",
            "agent_icon": "🌊",
            "agent_role": "判断当前处于康德拉季耶夫长波（50-60年大周期）的哪个阶段，给出战略性资产配置方向",
            "analysis": analysis,
            "focus_areas": ["康波定位", "技术革命", "大宗商品超级周期", "战略资产配置"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def merrill_lynch_clock_agent(self, macro_data_text: str) -> Dict[str, Any]:
        """
        美林投资时钟分析师 - 判断当前处于美林时钟的哪个象限

        职责：
        - 根据经济增长和通胀两个维度判断象限
        - 结合中国特色（政策第三维度）
        - 给出中短期资产配置建议
        """
        print("⏰ 美林时钟分析师正在分析...")
        time.sleep(1)

        prompt = render_prompt(
            "macro_merrill_lynch",
            macro_data_text=macro_data_text,
        )
        messages = [
            {"role": "system", "content": "你是一位精通美林投资时钟理论的顶级资产配置策略师，擅长将经典框架进行中国化改造，加入政策分析作为第三维度，帮助中国投资者做出精准的中短期资产配置决策。"},
            {"role": "user", "content": prompt}
        ]

        analysis = self.deepseek_client.call_api(messages, max_tokens=6000)
        print("  ✓ 美林时钟分析师分析完成")

        return {
            "agent_name": "美林时钟分析师",
            "agent_icon": "⏰",
            "agent_role": "判断当前处于美林投资时钟的哪个象限（3-5年中短周期），给出资产配置建议",
            "analysis": analysis,
            "focus_areas": ["经济增长", "通胀水平", "政策方向", "资产配置"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def china_policy_agent(self, macro_data_text: str) -> Dict[str, Any]:
        """
        中国政策分析师 - 分析中国特色政策环境

        职责：
        - 分析当前政策环境
        - 评估政策对周期的影响
        - 识别政策驱动的投资机会
        """
        print("🏛️ 中国政策分析师正在分析...")
        time.sleep(1)

        prompt = render_prompt(
            "macro_china_policy",
            macro_data_text=macro_data_text,
        )
        messages = [
            {"role": "system", "content": "你是一位资深的中国宏观经济政策研究专家，深入了解中国政府的经济调控方式和政策意图，擅长从政策中发现投资机会和风险。"},
            {"role": "user", "content": prompt}
        ]

        analysis = self.deepseek_client.call_api(messages, max_tokens=5000)
        print("  ✓ 中国政策分析师分析完成")

        return {
            "agent_name": "中国政策分析师",
            "agent_icon": "🏛️",
            "agent_role": "分析中国特色政策环境，评估政策对周期的影响，识别政策驱动的投资机会",
            "analysis": analysis,
            "focus_areas": ["货币政策", "财政政策", "产业政策", "房地产政策", "政策拐点"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def chief_macro_strategist_agent(self, kondratieff_report: str, merrill_report: str, policy_report: str, macro_data_text: str) -> Dict[str, Any]:
        """
        首席宏观策略师 - 综合三位分析师的观点，形成最终策略

        职责：
        - 整合康波、美林时钟、政策三个维度
        - 构建"周期仪表盘"
        - 给出最终的综合建议
        """
        print("👔 首席宏观策略师正在综合研判...")
        time.sleep(1)

        prompt = render_prompt(
            "macro_chief_strategist",
            kondratieff_report=kondratieff_report,
            merrill_report=merrill_report,
            policy_report=policy_report,
        )
        messages = [
            {"role": "system", "content": "你是一位世界级的首席宏观策略师，擅长将康波长周期、美林投资时钟和中国政策环境三个维度有机结合，为投资者提供既有战略高度又有战术灵活性的综合投资策略。你的判断沉稳、客观、有数据支撑。"},
            {"role": "user", "content": prompt}
        ]

        analysis = self.deepseek_client.call_api(messages, max_tokens=6000)
        print("  ✓ 首席宏观策略师综合研判完成")

        return {
            "agent_name": "首席宏观策略师",
            "agent_icon": "👔",
            "agent_role": "整合康波周期、美林时钟、中国政策三维分析，构建周期仪表盘，给出最终综合策略",
            "analysis": analysis,
            "focus_areas": ["周期仪表盘", "综合资产配置", "双指针共振", "分人群建议"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }


# 测试
if __name__ == "__main__":
    print("=" * 60)
    print("测试宏观周期AI智能体系统")
    print("=" * 60)
    agents = MacroCycleAgents()
    print(f"模型: {agents.model}")
    print("初始化完成")
