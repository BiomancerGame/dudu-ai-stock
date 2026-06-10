import openai
import json
from typing import Dict, List, Any, Optional
import config

from core.cache import llm_cache, make_key
from core.errors import DeepSeekAPIError
from core.logging_setup import get_logger
from prompts import render as render_prompt

try:
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )
    _HAS_TENACITY = True
except ImportError:  # pragma: no cover
    _HAS_TENACITY = False

logger = get_logger(__name__)

# 视为可重试的底层异常
_RETRIABLE_EXC = (
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
)


class DeepSeekClient:
    """DeepSeek API客户端"""

    def __init__(self, model=None):
        self.model = model or config.DEFAULT_MODEL_NAME
        self.client = openai.OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
        )

    # ----------------------------------------------------------------- #
    # 内部:真正发起请求,可能抛 DeepSeekAPIError                            #
    # ----------------------------------------------------------------- #
    def _do_request(
        self,
        messages: List[Dict[str, str]],
        model_to_use: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=model_to_use,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except _RETRIABLE_EXC as e:
            logger.warning("DeepSeek 可重试异常 model=%s err=%s", model_to_use, e)
            raise DeepSeekAPIError(str(e), model=model_to_use, retriable=True) from e
        except openai.OpenAIError as e:
            logger.error("DeepSeek 不可重试异常 model=%s err=%s", model_to_use, e)
            raise DeepSeekAPIError(str(e), model=model_to_use, retriable=False) from e

        message = response.choices[0].message
        parts: list[str] = []
        if getattr(message, "reasoning_content", None):
            parts.append(f"【推理过程】\n{message.reasoning_content}\n")
        if message.content:
            parts.append(message.content)
        result = "\n".join(parts).strip()
        if not result:
            raise DeepSeekAPIError("API 返回空响应", model=model_to_use, retriable=True)
        return result

    if _HAS_TENACITY:
        _do_request_retry = retry(
            reraise=True,
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(DeepSeekAPIError),
        )(_do_request)

    def call_api_strict(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """严格版:出错抛 ``DeepSeekAPIError``,带重试与缓存。"""
        model_to_use = model or self.model
        if "reasoner" in model_to_use.lower() and max_tokens <= 2000:
            max_tokens = 8000

        cache_key = make_key(model_to_use, messages, temperature)
        cached = llm_cache.get(cache_key)
        if cached is not None:
            logger.debug("LLM 缓存命中 key=%s...", cache_key[:12])
            return cached

        runner = self._do_request_retry if _HAS_TENACITY else self._do_request
        result = runner(messages, model_to_use, temperature, max_tokens)
        try:
            llm_cache.set(cache_key, result, expire=3600)
        except Exception as e:  # 缓存失败不致命
            logger.debug("写入 LLM 缓存失败: %s", e)
        return result

    def call_api(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """向后兼容:出错返回 ``"API调用失败: ..."`` 字符串。"""
        try:
            return self.call_api_strict(messages, model, temperature, max_tokens)
        except DeepSeekAPIError as e:
            logger.error("call_api 最终失败: %s", e)
            return f"API调用失败: {e}"
        except Exception as e:  # 兜底
            logger.exception("call_api 未预期异常")
            return f"API调用失败: {e}"
    
    def technical_analysis(self, stock_info: Dict, stock_data: Any, indicators: Dict) -> str:
        """技术面分析"""
        prompt = render_prompt(
            "technical_analysis",
            symbol=stock_info.get("symbol", "N/A"),
            name=stock_info.get("name", "N/A"),
            current_price=stock_info.get("current_price", "N/A"),
            change_percent=stock_info.get("change_percent", "N/A"),
            price=indicators.get("price", "N/A"),
            ma5=indicators.get("ma5", "N/A"),
            ma10=indicators.get("ma10", "N/A"),
            ma20=indicators.get("ma20", "N/A"),
            ma60=indicators.get("ma60", "N/A"),
            rsi=indicators.get("rsi", "N/A"),
            macd=indicators.get("macd", "N/A"),
            macd_signal=indicators.get("macd_signal", "N/A"),
            bb_upper=indicators.get("bb_upper", "N/A"),
            bb_lower=indicators.get("bb_lower", "N/A"),
            k_value=indicators.get("k_value", "N/A"),
            d_value=indicators.get("d_value", "N/A"),
            volume_ratio=indicators.get("volume_ratio", "N/A"),
        )
        messages = [
            {"role": "system", "content": "你是一名经验丰富的股票技术分析师，具有深厚的技术分析功底。"},
            {"role": "user", "content": prompt},
        ]
        return self.call_api(messages)
    
    def fundamental_analysis(self, stock_info: Dict, financial_data: Dict = None, quarterly_data: Dict = None) -> str:
        """基本面分析"""
        
        # 构建财务数据部分
        financial_section = ""
        if financial_data and not financial_data.get('error'):
            ratios = financial_data.get('financial_ratios', {})
            if ratios:
                financial_section = f"""
详细财务指标：
【盈利能力】
- 净资产收益率(ROE)：{ratios.get('净资产收益率ROE', ratios.get('ROE', 'N/A'))}
- 总资产收益率(ROA)：{ratios.get('总资产收益率ROA', ratios.get('ROA', 'N/A'))}
- 销售毛利率：{ratios.get('销售毛利率', ratios.get('毛利率', 'N/A'))}
- 销售净利率：{ratios.get('销售净利率', ratios.get('净利率', 'N/A'))}

【偿债能力】
- 资产负债率：{ratios.get('资产负债率', 'N/A')}
- 流动比率：{ratios.get('流动比率', 'N/A')}
- 速动比率：{ratios.get('速动比率', 'N/A')}

【运营能力】
- 存货周转率：{ratios.get('存货周转率', 'N/A')}
- 应收账款周转率：{ratios.get('应收账款周转率', 'N/A')}
- 总资产周转率：{ratios.get('总资产周转率', 'N/A')}

【成长能力】
- 营业收入同比增长：{ratios.get('营业收入同比增长', ratios.get('收入增长', 'N/A'))}
- 净利润同比增长：{ratios.get('净利润同比增长', ratios.get('盈利增长', 'N/A'))}

【每股指标】
- 每股收益(EPS)：{ratios.get('EPS', 'N/A')}
- 每股账面价值：{ratios.get('每股账面价值', 'N/A')}
- 股息率：{ratios.get('股息率', stock_info.get('dividend_yield', 'N/A'))}
- 派息率：{ratios.get('派息率', 'N/A')}
"""
            
            # 添加报告期信息
            if ratios.get('报告期'):
                financial_section = f"\n财务数据报告期：{ratios.get('报告期')}\n" + financial_section
        
        # 构建季报数据部分
        quarterly_section = ""
        if quarterly_data and quarterly_data.get('data_success'):
            # 使用格式化的季报数据
            from quarterly_report_data import QuarterlyReportDataFetcher
            fetcher = QuarterlyReportDataFetcher()
            quarterly_section = f"""

【最近8期季报详细数据】
{fetcher.format_quarterly_reports_for_ai(quarterly_data)}

以上是通过akshare获取的最近8期季度财务报告，请重点基于这些数据进行趋势分析。
"""
        
        prompt_head = render_prompt(
            "fundamental_analysis",
            symbol=stock_info.get("symbol", "N/A"),
            name=stock_info.get("name", "N/A"),
            current_price=stock_info.get("current_price", "N/A"),
            market_cap=stock_info.get("market_cap", "N/A"),
            sector=stock_info.get("sector", "N/A"),
            industry=stock_info.get("industry", "N/A"),
            pe_ratio=stock_info.get("pe_ratio", "N/A"),
            pb_ratio=stock_info.get("pb_ratio", "N/A"),
            ps_ratio=stock_info.get("ps_ratio", "N/A"),
            beta=stock_info.get("beta", "N/A"),
            week_52_high=stock_info.get("52_week_high", "N/A"),
            week_52_low=stock_info.get("52_week_low", "N/A"),
            financial_section=financial_section,
            quarterly_section=quarterly_section,
        )
        prompt = prompt_head

        messages = [
            {"role": "system", "content": "你是一名经验丰富的股票基本面分析师，擅长公司财务分析和行业研究。"},
            {"role": "user", "content": prompt},
        ]
        return self.call_api(messages)

    def fund_flow_analysis(self, stock_info: Dict, indicators: Dict, fund_flow_data: Dict = None) -> str:
        """资金面分析"""
        
        # 构建资金流向数据部分 - 使用akshare格式化数据
        fund_flow_section = ""
        if fund_flow_data and fund_flow_data.get('data_success'):
            # 使用格式化的资金流向数据
            from fund_flow_akshare import FundFlowAkshareDataFetcher
            fetcher = FundFlowAkshareDataFetcher()
            fund_flow_section = f"""

【近20个交易日资金流向详细数据】
{fetcher.format_fund_flow_for_ai(fund_flow_data)}

以上是通过akshare从东方财富获取的实际资金流向数据，请重点基于这些数据进行趋势分析。
"""
        else:
            fund_flow_section = "\n【资金流向数据】\n注意：未能获取到资金流向数据，将基于成交量进行分析。\n"
        
        prompt_head = render_prompt(
            "fund_flow_analysis",
            symbol=stock_info.get("symbol", "N/A"),
            name=stock_info.get("name", "N/A"),
            current_price=stock_info.get("current_price", "N/A"),
            market_cap=stock_info.get("market_cap", "N/A"),
            volume_ratio=indicators.get("volume_ratio", "N/A"),
            fund_flow_section=fund_flow_section,
        )
        prompt = prompt_head

        messages = [
            {"role": "system", "content": "你是一名经验丰富的资金面分析师，擅长市场资金流向和主力行为分析，能够深入解读资金数据背后的投资逻辑。"},
            {"role": "user", "content": prompt},
        ]
        return self.call_api(messages, max_tokens=3000)
    
    def comprehensive_discussion(self, technical_report: str, fundamental_report: str, 
                               fund_flow_report: str, stock_info: Dict) -> str:
        """综合讨论"""
        prompt = render_prompt(
            "comprehensive_discussion",
            symbol=stock_info.get("symbol", "N/A"),
            name=stock_info.get("name", "N/A"),
            current_price=stock_info.get("current_price", "N/A"),
            technical_report=technical_report,
            fundamental_report=fundamental_report,
            fund_flow_report=fund_flow_report,
        )
        
        messages = [
            {"role": "system", "content": "你是一名资深的首席投资分析师，擅长综合不同维度的分析形成投资判断。"},
            {"role": "user", "content": prompt}
        ]
        
        return self.call_api(messages, max_tokens=6000)
    
    def final_decision(self, comprehensive_discussion: str, stock_info: Dict, 
                      indicators: Dict) -> Dict[str, Any]:
        """最终投资决策"""
        prompt = render_prompt(
            "final_decision",
            symbol=stock_info.get("symbol", "N/A"),
            name=stock_info.get("name", "N/A"),
            current_price=stock_info.get("current_price", "N/A"),
            comprehensive_discussion=comprehensive_discussion,
            ma20=indicators.get("ma20", "N/A"),
            bb_upper=indicators.get("bb_upper", "N/A"),
            bb_lower=indicators.get("bb_lower", "N/A"),
        )
        
        messages = [
            {"role": "system", "content": "你是一名专业的投资决策专家，需要给出明确、可执行的投资建议。"},
            {"role": "user", "content": prompt}
        ]
        
        response = self.call_api(messages, temperature=0.3, max_tokens=4000)
        
        try:
            # 尝试解析JSON响应
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                decision_json = json.loads(json_match.group())
                return decision_json
            else:
                # 如果无法解析JSON，返回文本响应
                return {"decision_text": response}
        except Exception:
            return {"decision_text": response}
