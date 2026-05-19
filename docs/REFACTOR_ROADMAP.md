# 未来重构路线图

P0-P6 已完成基础设施。以下两项**需要专门时间块**,本会话未执行。

## R1. 9 个 db 模块完整重写(目前仅做了 WAL 兼容)

### 现状

`legacy_connect()` 已让所有 db 模块获得 WAL/pragma,但每个模块仍然自己处理:
- 手写 `try/finally` 关闭连接
- 手写 schema 创建 / ALTER 迁移
- 散落的 `cursor.execute()` 无统一封装

### 目标

仿 `database.py` 的写法,把 9 个文件改成 `db.base.get_conn()` + `run_migrations()`。

### 步骤(以单个文件为例)

1. 把所有 `CREATE TABLE` / `ALTER TABLE` / `CREATE INDEX` 收集到一个 `_MIGRATIONS = (...)` 元组,每个版本一条 SQL 字符串
2. 调用 `run_migrations(self.db_path, _MIGRATIONS)` 替代 `_init_database`
3. 每个查询方法改成 `with get_conn(...) as conn:` 上下文
4. `cur.fetchall()` 改用 `db.base.fetch_all` 辅助
5. 删除 `_get_connection` 私有方法

### 验证

每个文件迁移后:
- `python -c "import <module>; <module>.<Class>()" `
- 运行其对应的 UI 模块,人工 smoke test 关键 CRUD

### 难点

- `monitor_db.py` (573 行) 和 `smart_monitor_db.py` (640 行) 含多次 ALTER 兼容老库,迁移时要保留所有 ALTER 逻辑
- 部分模块的连接对象会跨方法传递,需要重构调用链

### 工作量预估

每文件 30-60 分钟 + 测试 → **5-8 小时**

---

## R2. 拆分 app.py 剩余 2761 行到 Streamlit pages/

### 现状

`app.py` 主 `main()` 内通过 `st.session_state['show_xxx']` 切换 17 个视图。所有视图渲染函数(`display_xxx`)都内联在 `app.py`。

### 目标

转 Streamlit 原生多页应用:

```
app.py                # 主入口,仅 ~100 行(set_page_config + 导航)
pages/
  01_💰_主力选股.py
  02_🐂_低价擒牛.py
  03_📊_小市值策略.py
  ...
  17_⚙️_环境配置.py
ui/components/
  stock_card.py       # 抽出复用组件
  process_panel.py    # create_analysis_process_panel
```

### 步骤

1. 给 `ui/menu.py` 的每个 `VIEW_TO_PAGE_KEY` 对应建一个 `pages/NN_xxx.py`
2. 把 `app.py` 里对应的 `if st.session_state.get('show_xxx'): display_xxx(...)` 块剪到对应 page 文件,作为顶层代码
3. 抽出共享辅助:`create_analysis_process_panel`、`display_stock_identity`、`display_stock_info`、`display_stock_chart`、`display_agents_analysis` 等到 `ui/components/`
4. `app.py` 只剩首页 + 全局设置注入
5. **重要**:Streamlit 多页应用对 `st.session_state` 有不同的初始化顺序,需要在每个 page 顶部 `from ui.styles import inject_styles; inject_styles()` 注入样式

### 难点

- 大量 `display_xxx` 函数互相调用,要谨慎理清依赖
- 现有 query param `?view=xxx` 导航与 Streamlit pages 的导航语义不同,需要重新设计
- `session_state` 在多页之间共享但需要规划清楚 page 启停时机

### 工作量预估

**1-2 天**(含手动 QA)

---

## 推荐执行顺序

1. **R1.a 易模块先做**:`portfolio_db.py`、`main_force_batch_db.py`、`longhubang_db.py`、`news_flow_db.py`、`sector_strategy_db.py`(每个仅 1 处 `sqlite3.connect`,基本上重写 init 即可)
2. **R1.b 难模块后做**:`monitor_db.py`、`smart_monitor_db.py`、`low_price_bull_monitor.py`、`profit_growth_monitor.py`(多 ALTER)
3. **prompt 残余迁移**:见 `PROMPT_MIGRATION_GUIDE.md`
4. **R2 拆 app.py**:作为独立 PR

每一步完成后跑:`pytest tests/ -q` + 启动 streamlit 手动 smoke test。
