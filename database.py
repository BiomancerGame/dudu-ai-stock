"""分析记录数据库访问 — 已迁移到 ``db.base``。

向后兼容: 仍然导出 ``db`` 单例与 ``StockAnalysisDatabase``。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from core.logging_setup import get_logger
from db.base import execute, fetch_all, get_conn, run_migrations

logger = get_logger(__name__)

_MIGRATIONS = (
    """
    CREATE TABLE IF NOT EXISTS analysis_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        stock_name TEXT,
        analysis_date TEXT NOT NULL,
        period TEXT NOT NULL,
        stock_info TEXT,
        agents_results TEXT,
        discussion_result TEXT,
        final_decision TEXT,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_records_symbol ON analysis_records(symbol);
    CREATE INDEX IF NOT EXISTS idx_records_created ON analysis_records(created_at DESC);
    """,
)


class StockAnalysisDatabase:
    """股票分析记录数据库 (薄封装,所有访问走 ``db.base``)。"""

    def __init__(self, db_path: str = "stock_analysis.db") -> None:
        self.db_path = db_path
        run_migrations(self.db_path, _MIGRATIONS)

    # 向后兼容方法名
    def init_database(self) -> None:
        run_migrations(self.db_path, _MIGRATIONS)

    def save_analysis(
        self,
        symbol: str,
        stock_name: str,
        period: str,
        stock_info: Any,
        agents_results: Any,
        discussion_result: Any,
        final_decision: Any,
    ) -> int:
        analysis_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        created_at = datetime.now().isoformat()

        def _dump(o: Any) -> str:
            return json.dumps(o, ensure_ascii=False, default=str)

        return int(
            execute(
                self.db_path,
                """
                INSERT INTO analysis_records
                (symbol, stock_name, analysis_date, period, stock_info,
                 agents_results, discussion_result, final_decision, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    stock_name,
                    analysis_date,
                    period,
                    _dump(stock_info),
                    _dump(agents_results),
                    _dump(discussion_result),
                    _dump(final_decision),
                    created_at,
                ),
            )
        )

    def get_all_records(self) -> list[dict]:
        rows = fetch_all(
            self.db_path,
            """
            SELECT id, symbol, stock_name, analysis_date, period, final_decision, created_at
            FROM analysis_records
            ORDER BY created_at DESC
            """,
        )
        result = []
        for r in rows:
            try:
                fd = json.loads(r["final_decision"]) if r["final_decision"] else {}
            except json.JSONDecodeError:
                fd = {}
            rating = fd.get("rating", "未知") if isinstance(fd, dict) else "未知"
            result.append(
                {
                    "id": r["id"],
                    "symbol": r["symbol"],
                    "stock_name": r["stock_name"],
                    "analysis_date": r["analysis_date"],
                    "period": r["period"],
                    "rating": rating,
                    "created_at": r["created_at"],
                }
            )
        return result

    def get_record_count(self) -> int:
        with get_conn(self.db_path) as conn:
            return int(conn.execute("SELECT COUNT(*) FROM analysis_records").fetchone()[0])

    def get_record_by_id(self, record_id: int) -> dict | None:
        rows = fetch_all(
            self.db_path,
            "SELECT * FROM analysis_records WHERE id = ?",
            (record_id,),
        )
        if not rows:
            return None
        r = rows[0]

        def _load(s: str | None) -> Any:
            if not s:
                return {}
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return {}

        return {
            "id": r["id"],
            "symbol": r["symbol"],
            "stock_name": r["stock_name"],
            "analysis_date": r["analysis_date"],
            "period": r["period"],
            "stock_info": _load(r["stock_info"]),
            "agents_results": _load(r["agents_results"]),
            "discussion_result": _load(r["discussion_result"]),
            "final_decision": _load(r["final_decision"]),
            "created_at": r["created_at"],
        }

    def delete_record(self, record_id: int) -> bool:
        with get_conn(self.db_path) as conn:
            cur = conn.execute("DELETE FROM analysis_records WHERE id = ?", (record_id,))
            return cur.rowcount > 0


# 全局单例 (保持兼容)
db = StockAnalysisDatabase()
