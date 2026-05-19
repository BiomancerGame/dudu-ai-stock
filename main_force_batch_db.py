#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主力选股批量分析历史记录数据库模块 — 已迁移到 db.base。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from core.logging_setup import get_logger
from db.base import execute, fetch_all, get_conn, run_migrations

logger = get_logger(__name__)

_MIGRATIONS = (
    """
    CREATE TABLE IF NOT EXISTS batch_analysis_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_date TEXT NOT NULL,
        batch_count INTEGER NOT NULL,
        analysis_mode TEXT NOT NULL,
        success_count INTEGER NOT NULL,
        failed_count INTEGER NOT NULL,
        total_time REAL NOT NULL,
        results_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_analysis_date ON batch_analysis_history(analysis_date);
    """,
)


class MainForceBatchDatabase:
    """主力选股批量分析历史数据库管理类。"""

    def __init__(self, db_path: str = "main_force_batch.db") -> None:
        self.db_path = db_path
        run_migrations(self.db_path, _MIGRATIONS)

    @staticmethod
    def _clean_results_for_json(results: List[Dict]) -> List[Dict]:
        """递归清理结果对象,确保可 JSON 序列化。"""

        def clean_value(value):
            if value is None:
                return None
            if isinstance(value, pd.DataFrame):
                if len(value) > 100:
                    return value.head(100).to_dict("records")
                return value.to_dict("records")
            if isinstance(value, pd.Series):
                return value.to_dict()
            if isinstance(value, dict):
                return {k: clean_value(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [clean_value(v) for v in value]
            if isinstance(value, (str, int, float, bool)):
                return value
            try:
                return str(value)
            except Exception:
                return "无法序列化"

        cleaned: List[Dict] = []
        for result in results:
            try:
                cleaned.append({k: clean_value(v) for k, v in result.items()})
            except Exception as e:
                cleaned.append(
                    {
                        "error": f"清理失败: {e}",
                        "original_keys": list(result.keys()) if isinstance(result, dict) else [],
                    }
                )
        return cleaned

    def save_batch_analysis(
        self,
        batch_count: int,
        analysis_mode: str,
        success_count: int,
        failed_count: int,
        total_time: float,
        results: List[Dict],
    ) -> int:
        analysis_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cleaned = self._clean_results_for_json(results)
        results_json = json.dumps(cleaned, ensure_ascii=False, default=str)

        return int(
            execute(
                self.db_path,
                """
                INSERT INTO batch_analysis_history
                (analysis_date, batch_count, analysis_mode, success_count,
                 failed_count, total_time, results_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (analysis_date, batch_count, analysis_mode, success_count,
                 failed_count, total_time, results_json),
            )
        )

    def get_all_history(self, limit: int = 50) -> List[Dict]:
        rows = fetch_all(
            self.db_path,
            """
            SELECT id, analysis_date, batch_count, analysis_mode,
                   success_count, failed_count, total_time, results_json, created_at
            FROM batch_analysis_history
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        history = []
        for r in rows:
            try:
                results = json.loads(r["results_json"])
            except (TypeError, ValueError, json.JSONDecodeError):
                results = []
            history.append(
                {
                    "id": r["id"],
                    "analysis_date": r["analysis_date"],
                    "batch_count": r["batch_count"],
                    "analysis_mode": r["analysis_mode"],
                    "success_count": r["success_count"],
                    "failed_count": r["failed_count"],
                    "total_time": r["total_time"],
                    "results": results,
                    "created_at": r["created_at"],
                }
            )
        return history

    def get_record_by_id(self, record_id: int) -> Optional[Dict]:
        rows = fetch_all(
            self.db_path,
            """
            SELECT id, analysis_date, batch_count, analysis_mode,
                   success_count, failed_count, total_time, results_json, created_at
            FROM batch_analysis_history
            WHERE id = ?
            """,
            (record_id,),
        )
        if not rows:
            return None
        r = rows[0]
        try:
            results = json.loads(r["results_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            results = []
        return {
            "id": r["id"],
            "analysis_date": r["analysis_date"],
            "batch_count": r["batch_count"],
            "analysis_mode": r["analysis_mode"],
            "success_count": r["success_count"],
            "failed_count": r["failed_count"],
            "total_time": r["total_time"],
            "results": results,
            "created_at": r["created_at"],
        }

    def delete_record(self, record_id: int) -> bool:
        with get_conn(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM batch_analysis_history WHERE id = ?",
                (record_id,),
            )
            return cur.rowcount > 0

    def get_statistics(self) -> Dict:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n,
                       COALESCE(SUM(batch_count), 0) AS total_stocks,
                       COALESCE(SUM(success_count), 0) AS total_success,
                       COALESCE(SUM(failed_count), 0) AS total_failed,
                       COALESCE(AVG(total_time), 0) AS avg_time
                FROM batch_analysis_history
                """
            ).fetchone()
        total_stocks = row["total_stocks"]
        total_success = row["total_success"]
        return {
            "total_records": row["n"],
            "total_stocks_analyzed": total_stocks,
            "total_success": total_success,
            "total_failed": row["total_failed"],
            "average_time": round(row["avg_time"], 2),
            "success_rate": (
                round(total_success / total_stocks * 100, 2) if total_stocks > 0 else 0
            ),
        }


# 全局数据库实例
batch_db = MainForceBatchDatabase()
