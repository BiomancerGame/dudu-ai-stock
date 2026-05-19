"""持仓股票数据库管理模块 — 已迁移到 db.base。"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from core.logging_setup import get_logger
from db.base import execute, fetch_all, get_conn, run_migrations

logger = get_logger(__name__)

DB_PATH = "portfolio_stocks.db"

_MIGRATIONS = (
    """
    CREATE TABLE IF NOT EXISTS portfolio_stocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        cost_price REAL,
        quantity INTEGER,
        note TEXT,
        auto_monitor BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS portfolio_analysis_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        portfolio_stock_id INTEGER NOT NULL,
        analysis_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        rating TEXT,
        confidence REAL,
        current_price REAL,
        target_price REAL,
        entry_min REAL,
        entry_max REAL,
        take_profit REAL,
        stop_loss REAL,
        summary TEXT,
        FOREIGN KEY (portfolio_stock_id) REFERENCES portfolio_stocks(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_portfolio_analysis_stock_id
        ON portfolio_analysis_history(portfolio_stock_id);
    CREATE INDEX IF NOT EXISTS idx_portfolio_analysis_time
        ON portfolio_analysis_history(analysis_time DESC);
    """,
)


class PortfolioDB:
    """持仓股票数据库管理类。"""

    _ALLOWED_UPDATE_FIELDS = ("code", "name", "cost_price", "quantity", "note", "auto_monitor")

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        run_migrations(self.db_path, _MIGRATIONS)
        logger.info("持仓数据库初始化完成: %s", self.db_path)

    # ==================== 持仓股票 CRUD ====================

    def add_stock(
        self,
        code: str,
        name: str,
        cost_price: Optional[float] = None,
        quantity: Optional[int] = None,
        note: str = "",
        auto_monitor: bool = True,
    ) -> int:
        try:
            with get_conn(self.db_path) as conn:
                cur = conn.execute(
                    """
                    INSERT INTO portfolio_stocks
                    (code, name, cost_price, quantity, note, auto_monitor, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (code, name, cost_price, quantity, note, auto_monitor,
                     datetime.now(), datetime.now()),
                )
                stock_id = cur.lastrowid
            logger.info("添加持仓股票成功: %s %s (ID: %s)", code, name, stock_id)
            return int(stock_id)
        except sqlite3.IntegrityError as e:
            logger.error("股票代码已存在: %s", code)
            raise ValueError(f"股票代码 {code} 已存在") from e

    def update_stock(self, stock_id: int, **kwargs) -> bool:
        update_fields = {k: v for k, v in kwargs.items() if k in self._ALLOWED_UPDATE_FIELDS}
        if not update_fields:
            logger.warning("没有需要更新的字段")
            return False
        update_fields["updated_at"] = datetime.now()
        set_clause = ", ".join(f"{f} = ?" for f in update_fields)
        values = list(update_fields.values()) + [stock_id]
        with get_conn(self.db_path) as conn:
            cur = conn.execute(
                f"UPDATE portfolio_stocks SET {set_clause} WHERE id = ?",
                values,
            )
            return cur.rowcount > 0

    def delete_stock(self, stock_id: int) -> bool:
        with get_conn(self.db_path) as conn:
            cur = conn.execute("DELETE FROM portfolio_stocks WHERE id = ?", (stock_id,))
            return cur.rowcount > 0

    def get_stock(self, stock_id: int) -> Optional[Dict]:
        rows = fetch_all(self.db_path, "SELECT * FROM portfolio_stocks WHERE id = ?", (stock_id,))
        return dict(rows[0]) if rows else None

    def get_stock_by_code(self, code: str) -> Optional[Dict]:
        rows = fetch_all(self.db_path, "SELECT * FROM portfolio_stocks WHERE code = ?", (code,))
        return dict(rows[0]) if rows else None

    def get_all_stocks(self, auto_monitor_only: bool = False) -> List[Dict]:
        if auto_monitor_only:
            sql = """
                SELECT * FROM portfolio_stocks
                WHERE auto_monitor = 1
                ORDER BY created_at DESC
            """
        else:
            sql = "SELECT * FROM portfolio_stocks ORDER BY created_at DESC"
        rows = fetch_all(self.db_path, sql)
        return [dict(r) for r in rows]

    def search_stocks(self, keyword: str) -> List[Dict]:
        pat = f"%{keyword}%"
        rows = fetch_all(
            self.db_path,
            """
            SELECT * FROM portfolio_stocks
            WHERE code LIKE ? OR name LIKE ?
            ORDER BY created_at DESC
            """,
            (pat, pat),
        )
        return [dict(r) for r in rows]

    def get_stock_count(self) -> int:
        with get_conn(self.db_path) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM portfolio_stocks").fetchone()[0])

    # ==================== 分析历史 ====================

    def save_analysis(
        self,
        stock_id: int,
        rating: str,
        confidence: float,
        current_price: float,
        target_price: Optional[float] = None,
        entry_min: Optional[float] = None,
        entry_max: Optional[float] = None,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        summary: str = "",
    ) -> int:
        return int(
            execute(
                self.db_path,
                """
                INSERT INTO portfolio_analysis_history
                (portfolio_stock_id, analysis_time, rating, confidence, current_price,
                 target_price, entry_min, entry_max, take_profit, stop_loss, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (stock_id, datetime.now(), rating, confidence, current_price,
                 target_price, entry_min, entry_max, take_profit, stop_loss, summary),
            )
        )

    def get_analysis_history(self, stock_id: int, limit: int = 10) -> List[Dict]:
        rows = fetch_all(
            self.db_path,
            """
            SELECT * FROM portfolio_analysis_history
            WHERE portfolio_stock_id = ?
            ORDER BY analysis_time DESC
            LIMIT ?
            """,
            (stock_id, limit),
        )
        return [dict(r) for r in rows]

    # 兼容别名
    def get_latest_analysis_history(self, stock_id: int, limit: int = 10) -> List[Dict]:
        return self.get_analysis_history(stock_id, limit)

    def get_latest_analysis(self, stock_id: int) -> Optional[Dict]:
        rows = fetch_all(
            self.db_path,
            """
            SELECT * FROM portfolio_analysis_history
            WHERE portfolio_stock_id = ?
            ORDER BY analysis_time DESC
            LIMIT 1
            """,
            (stock_id,),
        )
        return dict(rows[0]) if rows else None

    def get_rating_changes(self, stock_id: int, days: int = 30) -> List[Tuple[str, str, str]]:
        rows = fetch_all(
            self.db_path,
            """
            SELECT analysis_time, rating
            FROM portfolio_analysis_history
            WHERE portfolio_stock_id = ?
            AND analysis_time >= datetime('now', '-' || ? || ' days')
            ORDER BY analysis_time ASC
            """,
            (stock_id, days),
        )
        changes = []
        for i in range(1, len(rows)):
            prev = rows[i - 1]["rating"]
            curr = rows[i]["rating"]
            if prev != curr:
                changes.append((rows[i]["analysis_time"], prev, curr))
        return changes

    def delete_old_analysis(self, days: int = 90) -> int:
        with get_conn(self.db_path) as conn:
            cur = conn.execute(
                """
                DELETE FROM portfolio_analysis_history
                WHERE analysis_time < datetime('now', '-' || ? || ' days')
                """,
                (days,),
            )
            return cur.rowcount

    def get_all_latest_analysis(self) -> List[Dict]:
        rows = fetch_all(
            self.db_path,
            """
            SELECT
                s.*,
                h.rating, h.confidence, h.current_price, h.target_price,
                h.entry_min, h.entry_max, h.take_profit, h.stop_loss,
                h.analysis_time
            FROM portfolio_stocks s
            LEFT JOIN (
                SELECT h1.*
                FROM portfolio_analysis_history h1
                INNER JOIN (
                    SELECT portfolio_stock_id, MAX(analysis_time) as max_time
                    FROM portfolio_analysis_history
                    GROUP BY portfolio_stock_id
                ) h2
                ON h1.portfolio_stock_id = h2.portfolio_stock_id
                AND h1.analysis_time = h2.max_time
            ) h ON s.id = h.portfolio_stock_id
            ORDER BY s.created_at DESC
            """,
        )
        return [dict(r) for r in rows]


# 创建全局数据库实例
portfolio_db = PortfolioDB()
