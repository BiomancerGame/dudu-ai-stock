"""SQLite 连接基础设施。

特性:
- 上下文管理器自动 commit/rollback/close
- 自动启用 WAL 模式提升并发读
- 外键约束默认启用
- 可选 schema 版本管理
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterable, Iterator, Sequence

from core.errors import DatabaseError
from core.logging_setup import get_logger

logger = get_logger(__name__)

_PRAGMAS = (
    "PRAGMA journal_mode=WAL;",
    "PRAGMA foreign_keys=ON;",
    "PRAGMA synchronous=NORMAL;",
)


def _ensure_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


@contextmanager
def get_conn(db_path: str, *, row_factory: bool = True) -> Iterator[sqlite3.Connection]:
    """打开 SQLite 连接,使用完毕自动提交/回滚并关闭。

    用法::

        with get_conn("stock_analysis.db") as conn:
            conn.execute("INSERT INTO t VALUES (?)", (1,))
    """
    _ensure_dir(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    if row_factory:
        conn.row_factory = sqlite3.Row
    try:
        for pragma in _PRAGMAS:
            conn.execute(pragma)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_migrations(db_path: str, migrations: Sequence[str]) -> None:
    """按顺序执行 ``migrations`` 中尚未应用的 SQL 脚本。

    每个元素为完整 SQL 字符串,索引即版本号。
    """
    try:
        with get_conn(db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
            )
            cur = conn.execute("SELECT COALESCE(MAX(version), -1) FROM schema_version")
            current = cur.fetchone()[0]
            for idx, sql in enumerate(migrations):
                if idx <= current:
                    continue
                logger.info("应用迁移 %s -> %d on %s", current, idx, db_path)
                conn.executescript(sql)
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (idx,))
    except sqlite3.Error as e:
        raise DatabaseError(f"迁移失败 {db_path}: {e}") from e


def legacy_connect(db_path: str, *, timeout: float = 30.0) -> sqlite3.Connection:
    """旧代码迁移用:返回已应用 WAL/外键/同步级别的原生连接。

    用途:把 ``sqlite3.connect(path)`` 直接替换为 ``legacy_connect(path)``,
    业务代码无需变动即可获得性能与一致性提升。
    """
    _ensure_dir(db_path)
    conn = sqlite3.connect(db_path, timeout=timeout)
    for pragma in _PRAGMAS:
        try:
            conn.execute(pragma)
        except sqlite3.Error as e:
            logger.debug("pragma %s 失败: %s", pragma, e)
    return conn


def fetch_all(db_path: str, sql: str, params: Iterable = ()) -> list[sqlite3.Row]:
    with get_conn(db_path) as conn:
        return list(conn.execute(sql, tuple(params)))


def execute(db_path: str, sql: str, params: Iterable = ()) -> int:
    with get_conn(db_path) as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.lastrowid if cur.lastrowid else cur.rowcount
