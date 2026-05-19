"""股票监测数据库管理模块 — 已迁移到 db.base。"""
from __future__ import annotations

import json
import sqlite3
from typing import Dict, List, Optional

from core.logging_setup import get_logger
from db.base import fetch_all, get_conn, run_migrations

logger = get_logger(__name__)

_MIGRATIONS = (
    """
    CREATE TABLE IF NOT EXISTS monitored_stocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        name TEXT NOT NULL,
        rating TEXT NOT NULL,
        entry_range TEXT NOT NULL,
        take_profit REAL,
        stop_loss REAL,
        current_price REAL,
        last_checked TIMESTAMP,
        check_interval INTEGER DEFAULT 30,
        notification_enabled BOOLEAN DEFAULT TRUE,
        trading_hours_only BOOLEAN DEFAULT TRUE,
        quant_enabled BOOLEAN DEFAULT FALSE,
        quant_config TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_id INTEGER,
        price REAL NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (stock_id) REFERENCES monitored_stocks (id)
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_id INTEGER,
        type TEXT NOT NULL,
        message TEXT NOT NULL,
        triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        sent BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (stock_id) REFERENCES monitored_stocks (id)
    );
    """,
)


def _ensure_legacy_columns(db_path: str) -> None:
    """对老数据库补齐缺失列(向后兼容)。"""
    with get_conn(db_path) as conn:
        try:
            conn.execute("SELECT trading_hours_only FROM monitored_stocks LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(
                "ALTER TABLE monitored_stocks ADD COLUMN trading_hours_only BOOLEAN DEFAULT TRUE"
            )
            logger.info("已为 %s 补齐 trading_hours_only 列", db_path)


class StockMonitorDatabase:
    """股票监测数据库管理类。"""

    def __init__(self, db_path: str = "stock_monitor.db") -> None:
        self.db_path = db_path
        run_migrations(self.db_path, _MIGRATIONS)
        _ensure_legacy_columns(self.db_path)

    # ---------- 监测股票 ----------

    def add_monitored_stock(
        self,
        symbol: str,
        name: str,
        rating: str,
        entry_range: Dict,
        take_profit: float,
        stop_loss: float,
        check_interval: int = 30,
        notification_enabled: bool = True,
        trading_hours_only: bool = True,
        quant_enabled: bool = False,
        quant_config: Optional[Dict] = None,
    ) -> int:
        with get_conn(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO monitored_stocks
                (symbol, name, rating, entry_range, take_profit, stop_loss,
                 check_interval, notification_enabled, trading_hours_only,
                 quant_enabled, quant_config)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol, name, rating, json.dumps(entry_range),
                    take_profit, stop_loss, check_interval,
                    notification_enabled, trading_hours_only,
                    quant_enabled,
                    json.dumps(quant_config) if quant_config else None,
                ),
            )
            return int(cur.lastrowid)

    @staticmethod
    def _row_to_stock(row: sqlite3.Row, *, full: bool = True) -> Dict:
        try:
            entry_range = json.loads(row["entry_range"]) if row["entry_range"] else None
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("股票 %s 的 entry_range JSON 解析失败: %s", row["symbol"], e)
            entry_range = None
        try:
            quant_config = json.loads(row["quant_config"]) if row["quant_config"] else None
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("股票 %s 的 quant_config JSON 解析失败: %s", row["symbol"], e)
            quant_config = None
        result = {
            "id": row["id"],
            "symbol": row["symbol"],
            "name": row["name"],
            "rating": row["rating"],
            "entry_range": entry_range,
            "take_profit": row["take_profit"],
            "stop_loss": row["stop_loss"],
            "current_price": row["current_price"],
            "last_checked": row["last_checked"],
            "check_interval": row["check_interval"],
            "notification_enabled": bool(row["notification_enabled"]),
            "trading_hours_only": bool(row["trading_hours_only"])
                if row["trading_hours_only"] is not None else True,
            "quant_enabled": bool(row["quant_enabled"]),
            "quant_config": quant_config,
        }
        if full:
            result["created_at"] = row["created_at"]
            result["updated_at"] = row["updated_at"]
        return result

    def get_monitored_stocks(self) -> List[Dict]:
        rows = fetch_all(
            self.db_path,
            "SELECT * FROM monitored_stocks ORDER BY created_at DESC",
        )
        return [self._row_to_stock(r) for r in rows]

    def get_stock_by_id(self, stock_id: int) -> Optional[Dict]:
        rows = fetch_all(
            self.db_path,
            "SELECT * FROM monitored_stocks WHERE id = ?",
            (stock_id,),
        )
        return self._row_to_stock(rows[0], full=False) if rows else None

    def get_monitor_by_code(self, symbol: str) -> Optional[Dict]:
        rows = fetch_all(
            self.db_path,
            "SELECT * FROM monitored_stocks WHERE symbol = ?",
            (symbol,),
        )
        return self._row_to_stock(rows[0], full=False) if rows else None

    def update_stock_price(self, stock_id: int, price: float) -> None:
        with get_conn(self.db_path) as conn:
            conn.execute(
                """
                UPDATE monitored_stocks
                SET current_price = ?, last_checked = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (price, stock_id),
            )
            conn.execute(
                "INSERT INTO price_history (stock_id, price) VALUES (?, ?)",
                (stock_id, price),
            )

    def update_last_checked(self, stock_id: int) -> None:
        with get_conn(self.db_path) as conn:
            conn.execute(
                """
                UPDATE monitored_stocks
                SET last_checked = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (stock_id,),
            )

    def update_monitored_stock(
        self,
        stock_id: int,
        rating: str,
        entry_range: Dict,
        take_profit: float,
        stop_loss: float,
        check_interval: int,
        notification_enabled: bool,
        trading_hours_only: Optional[bool] = None,
        quant_enabled: Optional[bool] = None,
        quant_config: Optional[Dict] = None,
    ) -> bool:
        sets = [
            "rating = ?", "entry_range = ?", "take_profit = ?", "stop_loss = ?",
            "check_interval = ?", "notification_enabled = ?",
        ]
        params: list = [rating, json.dumps(entry_range), take_profit, stop_loss,
                        check_interval, notification_enabled]
        if quant_enabled is not None and quant_config is not None:
            sets += ["quant_enabled = ?", "quant_config = ?"]
            params += [quant_enabled, json.dumps(quant_config) if quant_config else None]
        if trading_hours_only is not None:
            sets.append("trading_hours_only = ?")
            params.append(trading_hours_only)
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(stock_id)
        with get_conn(self.db_path) as conn:
            cur = conn.execute(
                f"UPDATE monitored_stocks SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            return cur.rowcount > 0

    def toggle_notification(self, stock_id: int, enabled: bool) -> bool:
        with get_conn(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE monitored_stocks
                SET notification_enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (enabled, stock_id),
            )
            return cur.rowcount > 0

    def remove_monitored_stock(self, stock_id: int) -> bool:
        try:
            with get_conn(self.db_path) as conn:
                conn.execute("DELETE FROM price_history WHERE stock_id = ?", (stock_id,))
                conn.execute("DELETE FROM notifications WHERE stock_id = ?", (stock_id,))
                cur = conn.execute(
                    "DELETE FROM monitored_stocks WHERE id = ?", (stock_id,)
                )
                return cur.rowcount > 0
        except Exception as e:
            logger.error("删除股票失败: %s", e)
            return False

    # ---------- 通知 ----------

    def has_recent_notification(
        self, stock_id: int, notification_type: str, minutes: int = 60
    ) -> bool:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) FROM notifications
                WHERE stock_id = ? AND type = ?
                AND datetime(triggered_at) > datetime('now', '-' || ? || ' minutes')
                """,
                (stock_id, notification_type, minutes),
            ).fetchone()
            return row[0] > 0

    def add_notification(self, stock_id: int, notification_type: str, message: str) -> None:
        with get_conn(self.db_path) as conn:
            conn.execute(
                "INSERT INTO notifications (stock_id, type, message) VALUES (?, ?, ?)",
                (stock_id, notification_type, message),
            )

    def get_pending_notifications(self) -> List[Dict]:
        rows = fetch_all(
            self.db_path,
            """
            SELECT n.id, n.stock_id, s.symbol, s.name, n.type, n.message, n.triggered_at
            FROM notifications n
            JOIN monitored_stocks s ON n.stock_id = s.id
            WHERE n.sent = 0
            ORDER BY n.triggered_at
            """,
        )
        return [
            {
                "id": r["id"], "stock_id": r["stock_id"], "symbol": r["symbol"],
                "name": r["name"], "type": r["type"], "message": r["message"],
                "triggered_at": r["triggered_at"],
            }
            for r in rows
        ]

    def get_all_recent_notifications(self, limit: int = 10) -> List[Dict]:
        rows = fetch_all(
            self.db_path,
            """
            SELECT n.id, n.stock_id, s.symbol, s.name, n.type, n.message,
                   n.triggered_at, n.sent
            FROM notifications n
            JOIN monitored_stocks s ON n.stock_id = s.id
            ORDER BY n.triggered_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            {
                "id": r["id"], "stock_id": r["stock_id"], "symbol": r["symbol"],
                "name": r["name"], "type": r["type"], "message": r["message"],
                "triggered_at": r["triggered_at"], "sent": bool(r["sent"]),
            }
            for r in rows
        ]

    def mark_notification_sent(self, notification_id: int) -> None:
        with get_conn(self.db_path) as conn:
            conn.execute(
                "UPDATE notifications SET sent = 1 WHERE id = ?", (notification_id,)
            )

    def mark_all_notifications_sent(self) -> int:
        with get_conn(self.db_path) as conn:
            cur = conn.execute("UPDATE notifications SET sent = 1 WHERE sent = 0")
            return cur.rowcount

    def clear_all_notifications(self) -> int:
        with get_conn(self.db_path) as conn:
            cur = conn.execute("DELETE FROM notifications")
            return cur.rowcount

    # ---------- 批量 ----------

    def batch_add_or_update_monitors(self, monitors_data: List[Dict]) -> Dict[str, int]:
        added = updated = failed = 0
        for data in monitors_data:
            try:
                symbol = data.get("code") or data.get("symbol")
                name = data.get("name", symbol)
                rating = data.get("rating", "持有")
                entry_min = data.get("entry_min")
                entry_max = data.get("entry_max")
                take_profit = data.get("take_profit")
                stop_loss = data.get("stop_loss")
                check_interval = data.get("check_interval", 60)
                notification_enabled = data.get("notification_enabled", True)
                trading_hours_only = data.get("trading_hours_only", True)
                if not symbol or not all([entry_min, entry_max, take_profit, stop_loss]):
                    logger.warning("%s 参数不完整,跳过", symbol)
                    failed += 1
                    continue
                entry_range = {"min": entry_min, "max": entry_max}
                existing = self.get_monitor_by_code(symbol)
                if existing:
                    self.update_monitored_stock(
                        existing["id"],
                        rating=rating, entry_range=entry_range,
                        take_profit=take_profit, stop_loss=stop_loss,
                        check_interval=check_interval,
                        notification_enabled=notification_enabled,
                        trading_hours_only=trading_hours_only,
                    )
                    updated += 1
                else:
                    self.add_monitored_stock(
                        symbol=symbol, name=name, rating=rating,
                        entry_range=entry_range, take_profit=take_profit,
                        stop_loss=stop_loss, check_interval=check_interval,
                        notification_enabled=notification_enabled,
                        trading_hours_only=trading_hours_only,
                    )
                    added += 1
            except Exception as e:
                sym = data.get("code") or data.get("symbol", "Unknown")
                logger.error("处理监测失败 (%s): %s", sym, e)
                failed += 1
        logger.info("批量同步完成: 新增 %s, 更新 %s, 失败 %s", added, updated, failed)
        return {"added": added, "updated": updated, "failed": failed,
                "total": added + updated + failed}


# 全局数据库实例
monitor_db = StockMonitorDatabase()
