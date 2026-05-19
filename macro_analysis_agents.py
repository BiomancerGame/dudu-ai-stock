"""
宏观分析板块 - AI智能体
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List

import config
from deepseek_client import DeepSeekClient
from prompts import render as render_prompt


class MacroAnalysisAgents:
    """宏观分析多智能体"""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or config.DEFAULT_MODEL_NAME
        self.client = DeepSeekClient(model=self.model)

    def macro_analyst_agent(self, context_text: str) -> Dict[str, Any]:
        prompt = render_prompt(
            "macro_analyst",
            context_text=context_text,
        )
        return self._call_text(
            "你是中国宏观经济分析师，擅长从官方数据中提炼当前经济主线。",
            prompt,
            agent_name="宏观总量分析师",
            focus_areas=["增长", "通胀", "就业", "地产", "信用"],
        )

    def policy_analyst_agent(self, context_text: str) -> Dict[str, Any]:
        prompt = render_prompt(
            "macro_policy_analyst",
            context_text=context_text,
        )
        return self._call_text(
            "你是中国政策与流动性分析师，擅长把政策信号映射到A股行业风格。",
            prompt,
            agent_name="政策流动性分析师",
            focus_areas=["货币", "财政", "产业政策", "估值", "风格"],
        )

    def sector_mapper_agent(self, context_text: str, rule_view: Dict[str, Any], sector_pool: List[str]) -> Dict[str, Any]:
        prompt = render_prompt(
            "macro_sector_mapper",
            sector_pool_text=", ".join(sector_pool),
            rule_view_json=json.dumps(rule_view, ensure_ascii=False, indent=2),
            context_text=context_text,
        )
        structured = self._call_json(
            "你是A股行业配置分析师，只输出合法JSON。",
            prompt,
            fallback=rule_view,
        )
        analysis_prompt = render_prompt(
            "macro_sector_writeup",
            structured_json=json.dumps(structured, ensure_ascii=False, indent=2),
        )
        analysis = self.client.call_api(
            [
                {"role": "system", "content": "你是A股行业配置分析师，擅长把结构化结论写成可执行策略。"},
                {"role": "user", "content": analysis_prompt},
            ],
            max_tokens=2600,
            temperature=0.5,
        )
        return {
            "agent_name": "行业映射分析师",
            "agent_role": "将宏观变量映射为A股行业利好与利空方向",
            "analysis": analysis,
            "structured": structured,
            "focus_areas": ["行业轮动", "顺周期", "红利", "科技成长"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def stock_selector_agent(
        self,
        context_text: str,
        sector_view: Dict[str, Any],
        stock_candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        candidate_text = json.dumps(stock_candidates, ensure_ascii=False, indent=2)
        prompt = render_prompt(
            "macro_stock_selector",
            context_text=context_text,
            sector_view_json=json.dumps(sector_view, ensure_ascii=False, indent=2),
            candidate_text=candidate_text,
        )
        fallback = {
            "recommended_stocks": stock_candidates[:6],
            "watchlist": stock_candidates[6:10],
        }
        structured = self._call_json(
            "你是A股选股分析师，只输出合法JSON。",
            prompt,
            fallback=fallback,
        )
        analysis_prompt = render_prompt(
            "macro_stock_writeup",
            structured_json=json.dumps(structured, ensure_ascii=False, indent=2),
        )
        analysis = self.client.call_api(
            [
                {"role": "system", "content": "你是A股选股分析师，输出简洁、专业、可执行。"},
                {"role": "user", "content": analysis_prompt},
            ],
            max_tokens=2600,
            temperature=0.5,
        )
        return {
            "agent_name": "优质标的分析师",
            "agent_role": "从宏观受益方向中筛选更适合当前环境的A股标的",
            "analysis": analysis,
            "structured": structured,
            "focus_areas": ["候选股筛选", "风险收益比", "风格适配"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def chief_strategist_agent(
        self,
        context_text: str,
        macro_report: str,
        policy_report: str,
        sector_view: Dict[str, Any],
        stock_view: Dict[str, Any],
    ) -> Dict[str, Any]:
        prompt = render_prompt(
            "macro_a_chief_strategist",
            context_text=context_text,
            macro_report=macro_report,
            policy_report=policy_report,
            sector_view_json=json.dumps(sector_view, ensure_ascii=False, indent=2),
            stock_view_json=json.dumps(stock_view, ensure_ascii=False, indent=2),
        )
        return self._call_text(
            "你是首席策略官，擅长把宏观、行业和选股结论整合成完整投资框架。",
            prompt,
            agent_name="首席策略官",
            focus_areas=["总策略", "行业配置", "选股落地", "风险提示"],
            max_tokens=4200,
            temperature=0.45,
        )

    def _call_text(
        self,
        system_prompt: str,
        user_prompt: str,
        agent_name: str,
        focus_areas: List[str],
        max_tokens: int = 3200,
        temperature: float = 0.45,
    ) -> Dict[str, Any]:
        analysis = self.client.call_api(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return {
            "agent_name": agent_name,
            "analysis": analysis,
            "focus_areas": focus_areas,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _call_json(
        self,
        system_prompt: str,
        user_prompt: str,
        fallback: Dict[str, Any],
        max_tokens: int = 2800,
    ) -> Dict[str, Any]:
        response = self.client.call_api(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        parsed = self._extract_json(response)
        if isinstance(parsed, dict):
            return parsed
        return fallback

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any] | None:
        if not text:
            return None
        text = text.strip()
        candidates = [text]

        fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
        candidates.extend(fenced)

        brace_match = re.search(r"(\{.*\})", text, re.S)
        if brace_match:
            candidates.append(brace_match.group(1))

        for candidate in candidates:
            try:
                return json.loads(candidate)
            except Exception:
                continue
        return None
