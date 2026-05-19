# Prompt 外置迁移手册

适用于把 `*_agents.py` / `smart_monitor_deepseek.py` 里残留的 30 处内嵌 `prompt = f"""..."""` 迁出到 `prompts/*.md`。

## 步骤(每个 prompt 都按下面 4 步)

### 1. 创建 `.md` 模板

把原 f-string 内容复制到 `prompts/<descriptive_name>.md`,**把 Python 表达式替换成平面占位符**:

```python
# 旧
prompt = f"""
股票代码：{stock_info.get('symbol', 'N/A')}
评级：{result.get('rating', '未知')}
"""
```

```markdown
<!-- 新: prompts/foo.md -->
股票代码：{symbol}
评级：{rating}
```

### 2. 改写 Python 调用处

```python
from prompts import render as render_prompt
# ...
prompt = render_prompt(
    "foo",
    symbol=stock_info.get("symbol", "N/A"),
    rating=result.get("rating", "未知"),
)
```

### 3. JSON 大括号要转义

模板里若含示例 JSON,把 `{` `}` 写成 `{{` `}}` —— 见 `prompts/final_decision.md` 已有的示例。

### 4. 跑测试 + 启动 streamlit 验证

```bash
pytest tests/ -q
streamlit run app.py
```

## 已迁移完成

| 文件 | Prompt | 模板 |
|---|---|---|
| `deepseek_client.py` | technical_analysis | `prompts/technical_analysis.md` |
| `deepseek_client.py` | fundamental_analysis | `prompts/fundamental_analysis.md` |
| `deepseek_client.py` | fund_flow_analysis | `prompts/fund_flow_analysis.md` |
| `deepseek_client.py` | comprehensive_discussion | `prompts/comprehensive_discussion.md` |
| `deepseek_client.py` | final_decision | `prompts/final_decision.md` |

## 待迁移清单(30 处)

按文件 + 内含 prompt 数量,推荐顺序由易到难:

| 文件 | prompts | 备注 |
|---|---|---|
| `smart_monitor_deepseek.py` | 1 | 最简单,先做 |
| `ai_agents.py` | 4 | 中等 |
| `news_flow_agents.py` | 5 | 中等 |
| `longhubang_agents.py` | 5 | 中等 |
| `sector_strategy_agents.py` | 4 | 中等 |
| `macro_cycle_agents.py` | 4 | 中等 |
| `macro_analysis_agents.py` | 7 | 最多,最后做 |

定位命令:

```bash
grep -n 'prompt = f"""' *_agents.py smart_monitor_deepseek.py
```
