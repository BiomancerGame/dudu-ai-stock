"""数据访问层 — 统一 SQLite 访问。

后续应将根目录下的 ``*_db.py`` 模块逐步迁移到本包。
当前提供两类基础设施:
- ``base.get_conn(path)``: 统一的连接上下文管理器,启用 WAL、外键
- ``base.run_migrations(path, migrations)``: 简单 schema 版本管理

迁移策略 (示例见 ``database.py``):
    from db.base import get_conn
    with get_conn("stock_analysis.db") as conn:
        conn.execute("INSERT INTO ...", (...))
"""
