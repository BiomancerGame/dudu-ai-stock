"""
智能盯盘 - DeepSeek AI 决策引擎
适配A股T+1交易规则的AI决策系统
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, time
import pytz
import config


class SmartMonitorDeepSeek:
    """A股智能盯盘 - DeepSeek AI决策引擎"""

    def __init__(self, api_key: str):
        """
        初始化DeepSeek客户端
        
        Args:
            api_key: DeepSeek API密钥
        """
        self.api_key = api_key
        self.base_url = config.DEEPSEEK_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.logger = logging.getLogger(__name__)

    def is_trading_time(self) -> bool:
        """
        判断当前是否在A股交易时间内
        
        Returns:
            bool: 是否可以交易
        """
        beijing_tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(beijing_tz)
        current_time = now.time()
        
        # 排除周末
        if now.weekday() >= 5:
            return False
        
        # 上午：9:30-11:30
        morning_start = time(9, 30)
        morning_end = time(11, 30)
        
        # 下午：13:00-15:00
        afternoon_start = time(13, 0)
        afternoon_end = time(15, 0)
        
        is_trading = (
            (morning_start <= current_time <= morning_end) or
            (afternoon_start <= current_time <= afternoon_end)
        )
        
        return is_trading

    def get_trading_session(self) -> Dict:
        """
        获取当前交易时段信息（A股版本）
        
        Returns:
            Dict: 时段信息
        """
        beijing_tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(beijing_tz)
        current_time = now.time()
        
        # 判断是否交易日
        if now.weekday() >= 5:
            return {
                'session': '休市',
                'volatility': 'none',
                'recommendation': '周末不可交易',
                'beijing_hour': now.hour,
                'can_trade': False
            }
        
        # 开盘前（9:00-9:30）：集合竞价时段
        if time(9, 0) <= current_time < time(9, 30):
            return {
                'session': '集合竞价',
                'volatility': 'high',
                'recommendation': '可观察盘面情绪，准备开盘交易',
                'beijing_hour': now.hour,
                'can_trade': False
            }
        
        # 上午盘（9:30-11:30）
        elif time(9, 30) <= current_time <= time(11, 30):
            return {
                'session': '上午盘',
                'volatility': 'high',
                'recommendation': '交易活跃，波动较大',
                'beijing_hour': now.hour,
                'can_trade': True
            }
        
        # 午间休市（11:30-13:00）
        elif time(11, 30) < current_time < time(13, 0):
            return {
                'session': '午间休市',
                'volatility': 'none',
                'recommendation': '不可交易，可分析上午盘面',
                'beijing_hour': now.hour,
                'can_trade': False
            }
        
        # 下午盘（13:00-15:00）
        elif time(13, 0) <= current_time <= time(15, 0):
            # 尾盘最后半小时（14:30-15:00）
            if current_time >= time(14, 30):
                return {
                    'session': '尾盘',
                    'volatility': 'high',
                    'recommendation': '尾盘波动大，谨慎操作',
                    'beijing_hour': now.hour,
                    'can_trade': True
                }
            else:
                return {
                    'session': '下午盘',
                    'volatility': 'medium',
                    'recommendation': '波动趋缓，适合布局',
                    'beijing_hour': now.hour,
                    'can_trade': True
                }
        
        # 盘后（15:00之后）
        else:
            return {
                'session': '盘后',
                'volatility': 'none',
                'recommendation': '收盘后，可复盘分析',
                'beijing_hour': now.hour,
                'can_trade': False
            }

    def chat_completion(self, messages: List[Dict], model: str = None,
                       temperature: float = 0.7, max_tokens: int = 2000) -> Dict:
        """
        调用DeepSeek API
        
        Args:
            messages: 对话消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            API响应
        """
        import requests
        
        model = model or config.DEFAULT_MODEL_NAME
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"DeepSeek API调用失败: {e}")
            raise

    def analyze_stock_and_decide(self, stock_code: str, market_data: Dict,
                                 account_info: Dict, has_position: bool = False,
                                 position_cost: float = 0, position_quantity: int = 0) -> Dict:
        """
        分析股票并做出交易决策（A股T+1规则）
        
        Args:
            stock_code: 股票代码（如：600519）
            market_data: 市场数据
            account_info: 账户信息
            has_position: 是否已持有该股票
            position_cost: 持仓成本价格
            position_quantity: 持仓数量
            
        Returns:
            交易决策
        """
        # 获取交易时段
        session_info = self.get_trading_session()
        
        # 构建Prompt
        prompt = self._build_a_stock_prompt(
            stock_code, market_data, account_info, 
            has_position, session_info, position_cost, position_quantity
        )
        
        system_prompt = """你是一位资深的A股量化交易专家，拥有15年实战经验。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ A股交易规则（与币圈完全不同！）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[CRITICAL] T+1规则：
- 今天买入的股票，**今天不能卖出**，必须等到下一个交易日
- 这意味着：一旦买入，至少要持有到明天才能卖出
- 因此买入决策必须**极其谨慎**，不能像币圈那样快进快出

[CRITICAL] 涨跌停限制：
- 主板/中小板：±10%涨跌停
- 创业板/科创板：±20%涨跌停
- ST股票：±5%涨跌停
- 一旦涨停，很难买入；一旦跌停，很难卖出

[CRITICAL] 交易时间：
- 上午：9:30-11:30
- 下午：13:00-15:00
- 其他时间不能交易

[CRITICAL] 只能做多：
- A股不能做空（融券门槛高，散户基本不用）
- 只有买入和卖出两个动作

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 你的交易哲学（适配T+1）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**因为T+1限制，你的策略必须更加稳健！**

1. **买入前三思**：
   - 买入后至少持有1天，所以必须确保趋势向上
   - 不能像币圈那样"试探性开仓"，一旦买入就是承诺
   - 最好在尾盘或第二天开盘前决策，避免盲目追高

2. **止损更困难**：
   - 如果今天买入后下跌，今天无法止损（T+1）
   - 只能等明天再卖，可能面临更大亏损
   - 因此：**宁可错过，不可做错**

3. **技术分析更重要**：
   - 日线级别趋势确认
   - 支撑位/阻力位
   - 成交量配合
   - 量价关系判断

4. **风险控制严格**：
   - 单只股票仓位 ≤ 30%（T+1风险大）
   - 止损位：-5%（明天开盘立即执行）
   - 止盈位：+8-15%（分批止盈）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 可选的交易动作
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**如果当前无持仓**：
- action = "BUY"（买入）- 必须确保技术面强势，趋势向上
- action = "HOLD"（观望）- 信号不明确时选择观望

**如果当前有持仓**：
- action = "SELL"（卖出）- 达到止盈/止损条件，或技术面转弱
- action = "HOLD"（持有）- 趋势未改变，继续持有
- ⚠️ 注意：如果股票是今天买入的，受T+1限制无法卖出，只能选择HOLD

**绝对禁止**：
- 不要在开盘前5分钟（9:30-9:35）买入，容易追高
- 不要在尾盘最后5分钟（14:55-15:00）买入，可能被套
- 不要逆趋势交易（趋势向下时买入）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 买入信号（必须满足至少3个条件）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ✅ 趋势向上：价格 > MA5 > MA20 > MA60（多头排列）
2. ✅ 量价配合：成交量 > 5日均量的120%（放量上涨）
3. ✅ MACD金叉：MACD > 0 且DIF上穿DEA
4. ✅ RSI健康：RSI在50-70区间（不超买不超卖）
5. ✅ 突破关键位：突破前期高点或重要阻力位
6. ✅ 布林带位置：价格接近布林中轨上方，有上行空间

**加分项**：
- 行业板块同步上涨
- 有重大利好消息
- 机构调研增加

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📉 卖出信号（满足任一条件立即卖出）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 🔴 止损触发：亏损 ≥ -5%（明天开盘立即卖出）
2. 🟢 止盈触发：盈利 ≥ +10%（分批止盈，先卖一半）
3. 🔴 趋势转弱：跌破MA20或MA60，且MACD死叉
4. 🔴 放量下跌：成交量放大但价格下跌（主力出货）
5. 🔴 技术破位：跌破重要支撑位
6. 🔴 重大利空：公司公告重大利空消息

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💬 返回格式（必须严格JSON）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{
    "action": "BUY" | "SELL" | "HOLD",
    "confidence": 0-100,
    "reasoning": "详细的决策理由，包括技术分析、风险评估等，200-300字",
    "position_size_pct": 10-30,  // 建议仓位百分比（因为T+1，建议≤30%）
    "stop_loss_pct": 5.0,  // 止损百分比（建议5%）
    "take_profit_pct": 10.0,  // 止盈百分比（建议10-15%）
    "risk_level": "low" | "medium" | "high",
    "key_price_levels": {
        "support": 支撑位价格,
        "resistance": 阻力位价格,
        "stop_loss": 止损位价格
    }
}

**reasoning 示例**：
"茅台当前价格1650元，日线级别呈多头排列（MA5 1645 > MA20 1620 > MA60 1580），
MACD金叉且柱状图持续放大，RSI 62处于健康区间。今日成交量较5日均量放大135%，
显示有增量资金入场。技术面支撑位在1630元附近，阻力位在1680元。综合判断短期
趋势向上，但考虑T+1规则，建议仓位控制在20%，止损位设在1568元（-5%），
止盈目标1815元（+10%）。风险提示：如明日低开需谨慎..."
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        try:
            response = self.chat_completion(messages, temperature=0.3)
            ai_response = response['choices'][0]['message']['content']
            
            # 解析JSON决策
            decision = self._parse_decision(ai_response)
            
            return {
                'success': True,
                'decision': decision,
                'raw_response': ai_response
            }
            
        except Exception as e:
            self.logger.error(f"AI决策失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _build_a_stock_prompt(self, stock_code: str, market_data: Dict,
                             account_info: Dict, has_position: bool,
                             session_info: Dict, position_cost: float = 0,
                             position_quantity: int = 0) -> str:
        """构建A股分析提示词。模板见 prompts/smart_monitor_a_stock.md。"""
        from prompts import render as render_prompt

        # 趋势 / MACD / RSI / 量比 文字标签
        trend = market_data.get('trend')
        trend_text = '多头排列' if trend == 'up' else '空头排列' if trend == 'down' else '震荡'

        macd_val = market_data.get('macd', 0)
        macd_signal = '金叉' if macd_val > 0 else '死叉'

        rsi6_val = market_data.get('rsi6', 50)
        rsi6_signal = '[超买]' if rsi6_val > 80 else '[超卖]' if rsi6_val < 20 else '[正常]'

        vol_ratio = market_data.get('volume_ratio', 0)
        volume_signal = '放量' if vol_ratio > 1.2 else '缩量' if vol_ratio < 0.8 else '正常'

        # 持仓块 (条件性段落)
        if has_position and position_cost > 0 and position_quantity > 0:
            current_price = market_data.get('current_price', 0)
            cost_total = position_cost * position_quantity
            current_total = current_price * position_quantity
            profit_loss = current_total - cost_total
            profit_loss_pct = (profit_loss / cost_total * 100) if cost_total > 0 else 0
            position_block = (
                f"\n[POSITION] 当前持仓（{stock_code}） ⭐ 重要\n"
                f"═══════════════════════════════════════════════════════════\n"
                f"持仓数量: {position_quantity}股\n"
                f"成本价: ¥{position_cost:.2f}\n"
                f"当前价: ¥{current_price:.2f}\n"
                f"持仓市值: ¥{current_total:,.2f}\n"
                f"浮动盈亏: ¥{profit_loss:,.2f} ({profit_loss_pct:+.2f}%)\n\n"
                f"⚠️ T+1限制: 该股票可以卖出（不受T+1限制）\n\n"
                f"💡 决策建议：\n"
                f"- 如果盈利且技术指标转弱 → 建议止盈卖出\n"
                f"- 如果亏损超过止损线（通常-5%）→ 建议止损卖出\n"
                f"- 如果技术指标强势且未到止盈位 → 建议继续持有\n"
                f"- 如果盈利且看好后市 → 可考虑加仓（但注意仓位控制）\n"
            )
        else:
            position_block = (
                "\n[POSITION] 当前无持仓\n"
                "═══════════════════════════════════════════════════════════\n"
                "可考虑买入，但必须确保：\n"
                "1. 技术面强势（满足至少3个买入信号）\n"
                "2. 有足够的安全边际\n"
                "3. 考虑T+1规则，买入后至少持有1天\n"
                "4. 控制仓位，建议单只股票仓位≤30%\n"
            )

        return render_prompt(
            "smart_monitor_a_stock",
            session=session_info['session'],
            beijing_hour=session_info['beijing_hour'],
            volatility=session_info['volatility'].upper(),
            recommendation=session_info['recommendation'],
            can_trade='是' if session_info['can_trade'] else '否',
            stock_code=stock_code,
            name=market_data.get('name', 'N/A'),
            current_price=f"{market_data.get('current_price', 0):.2f}",
            change_pct=f"{market_data.get('change_pct', 0):+.2f}",
            change_amount=f"{market_data.get('change_amount', 0):+.2f}",
            high=f"{market_data.get('high', 0):.2f}",
            low=f"{market_data.get('low', 0):.2f}",
            open=f"{market_data.get('open', 0):.2f}",
            pre_close=f"{market_data.get('pre_close', 0):.2f}",
            volume=f"{market_data.get('volume', 0):,.0f}",
            amount=f"{market_data.get('amount', 0):,.2f}",
            ma5=f"{market_data.get('ma5', 0):.2f}",
            ma20=f"{market_data.get('ma20', 0):.2f}",
            ma60=f"{market_data.get('ma60', 0):.2f}",
            trend_text=trend_text,
            macd_dif=f"{market_data.get('macd_dif', 0):.4f}",
            macd_dea=f"{market_data.get('macd_dea', 0):.4f}",
            macd=f"{macd_val:.4f}",
            macd_signal=macd_signal,
            rsi6=f"{rsi6_val:.2f}",
            rsi6_signal=rsi6_signal,
            rsi12=f"{market_data.get('rsi12', 50):.2f}",
            rsi24=f"{market_data.get('rsi24', 50):.2f}",
            kdj_k=f"{market_data.get('kdj_k', 50):.2f}",
            kdj_d=f"{market_data.get('kdj_d', 50):.2f}",
            kdj_j=f"{market_data.get('kdj_j', 50):.2f}",
            boll_upper=f"{market_data.get('boll_upper', 0):.2f}",
            boll_mid=f"{market_data.get('boll_mid', 0):.2f}",
            boll_lower=f"{market_data.get('boll_lower', 0):.2f}",
            boll_position=market_data.get('boll_position', 'N/A'),
            vol_ma5=f"{market_data.get('vol_ma5', 0):,.0f}",
            volume_ratio=f"{vol_ratio:.2f}",
            volume_signal=volume_signal,
            turnover_rate=f"{market_data.get('turnover_rate', 0):.2f}",
            available_cash=f"{account_info.get('available_cash', 0):,.2f}",
            total_value=f"{account_info.get('total_value', 0):,.2f}",
            positions_count=account_info.get('positions_count', 0),
            position_block=position_block,
        )

    def _parse_decision(self, ai_response: str) -> Dict:
        """解析AI决策响应"""
        import json
        
        try:
            # 尝试多种提取方式
            if "```json" in ai_response.lower():
                json_start = ai_response.lower().find("```json") + 7
                json_end = ai_response.find("```", json_start)
                json_str = ai_response[json_start:json_end].strip()
            elif "```" in ai_response:
                first_tick = ai_response.find("```")
                json_start = ai_response.find("\n", first_tick) + 1
                json_end = ai_response.find("```", json_start)
                json_str = ai_response[json_start:json_end].strip()
            elif "{" in ai_response and "}" in ai_response:
                start_idx = ai_response.find('{')
                end_idx = ai_response.rfind('}') + 1
                json_str = ai_response[start_idx:end_idx]
            else:
                json_str = ai_response
            
            decision = json.loads(json_str)
            
            # 验证必需字段
            required_fields = ['action', 'confidence', 'reasoning']
            for field in required_fields:
                if field not in decision:
                    raise ValueError(f"缺少必需字段: {field}")
            
            # 设置默认值
            decision.setdefault('position_size_pct', 20)
            decision.setdefault('stop_loss_pct', 5.0)
            decision.setdefault('take_profit_pct', 10.0)
            decision.setdefault('risk_level', 'medium')
            
            return decision
            
        except Exception as e:
            self.logger.error(f"解析AI决策失败: {e}")
            # 返回保守决策
            return {
                'action': 'HOLD',
                'confidence': 0,
                'reasoning': f'AI响应解析失败: {str(e)}',
                'position_size_pct': 0,
                'stop_loss_pct': 5.0,
                'take_profit_pct': 10.0,
                'risk_level': 'high'
            }

