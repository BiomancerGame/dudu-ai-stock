[TIMER] 当前交易时段
═══════════════════════════════════════════════════════════
当前时段: {session} (北京时间{beijing_hour}:00)
市场状态: {volatility}
时段建议: {recommendation}
可交易: {can_trade}

[STOCK] 股票基本信息
═══════════════════════════════════════════════════════════
股票代码: {stock_code}
股票名称: {name}
当前价格: ¥{current_price}
今日涨跌: {change_pct}%
今日涨跌额: ¥{change_amount}
最高价: ¥{high}
最低价: ¥{low}
开盘价: ¥{open}
昨收价: ¥{pre_close}
成交量: {volume}手
成交额: ¥{amount}万

[TECHNICAL] 技术指标
═══════════════════════════════════════════════════════════
MA5: ¥{ma5}
MA20: ¥{ma20}
MA60: ¥{ma60}
趋势判断: {trend_text}

MACD:
  DIF: {macd_dif}
  DEA: {macd_dea}
  MACD: {macd} ({macd_signal})

RSI(6): {rsi6} {rsi6_signal}
RSI(12): {rsi12}
RSI(24): {rsi24}

KDJ:
  K: {kdj_k}
  D: {kdj_d}
  J: {kdj_j}

布林带:
  上轨: ¥{boll_upper}
  中轨: ¥{boll_mid}
  下轨: ¥{boll_lower}
  位置: {boll_position}

[VOLUME] 量能分析
═══════════════════════════════════════════════════════════
今日成交量: {volume}手
5日均量: {vol_ma5}手
量比: {volume_ratio} ({volume_signal})
换手率: {turnover_rate}%

[ACCOUNT] 账户状态
═══════════════════════════════════════════════════════════
可用资金: ¥{available_cash}
总资产: ¥{total_value}
持仓数量: {positions_count}
{position_block}
请基于以上数据，给出交易决策（JSON格式）。
