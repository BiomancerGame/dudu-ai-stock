#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""低价擒牛策略监控模块 — 已迁移到 db.base。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from core.logging_setup import get_logger
from db.base import fetch_all, get_conn, run_migrations

logger = get_logger(__name__)

_MIGRATIONS = (
    """
    CREATE TABLE IF NOT EXISTS monitored_stocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        stock_name TEXT NOT NULL,
        buy_price REAL NOT NULL,
        buy_date TEXT NOT NULL,
        holding_days INTEGER DEFAULT 0,
        status TEXT DEFAULT 'holding',
        add_time TEXT NOT NULL,
        remove_time TEXT,
        remove_reason TEXT,
        UNIQUE(stock_code, status)
    );
    CREATE TABLE IF NOT EXISTS sell_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        stock_name TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        alert_reason TEXT NOT NULL,
        current_price REAL,
        ma5 REAL,
        ma20 REAL,
        holding_days INTEGER,
        alert_time TEXT NOT NULL,
        is_sent INTEGER DEFAULT 0
    );
    """,
)


class LowPriceBullMonitor:
    """低价擒牛策略监控器。"""

    def __init__(self, db_path: str = "low_price_bull_monitor.db") -> None:
        self.db_path = db_path
        self.logger = logger
        run_migrations(self.db_path, _MIGRATIONS)
        logger.info("低价擒牛监控数据库初始化完成")

    def add_stock(
        self,
        stock_code: str,
        stock_name: str,
        buy_price: float,
        buy_date: Optional[str] = None,
    ) -> Tuple[bool, str]:
        try:
            buy_date = buy_date or datetime.now().strftime("%Y-%m-%d")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with get_conn(self.db_path) as conn:
                if conn.execute(
                    "SELECT id FROM monitored_stocks WHERE stock_code = ? AND status = 'holding'",
                    (stock_code,),
                ).fetchone():
                    return False, f"股票 {stock_code} 已在监控列表中"
                conn.execute(
                    """
                    INSERT INTO monitored_stocks
                    (stock_code, stock_name, buy_price, buy_date, add_time)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (stock_code, stock_name, buy_price, buy_date, now),
                )
            logger.info("添加股票到监控: %s %s", stock_code, stock_name)
            return True, f"成功添加 {stock_code} {stock_name} 到监控列表"
        except Exception as e:
            logger.error("添加股票失败: %s", e)
            return False, f"添加失败: {e}"

    def remove_stock(self, stock_code: str, reason: str = "手动移除") -> Tuple[bool, str]:
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with get_conn(self.db_path) as conn:
                if not conn.execute(
                    "SELECT id FROM monitored_stocks WHERE stock_code = ? AND status = 'holding'",
                    (stock_code,),
                ).fetchone():
                    return False, f"股票 {stock_code} 不在监控列表中"
                conn.execute(
                    "DELETE FROM monitored_stocks WHERE stock_code = ? AND status = 'removed'",
                    (stock_code,),
                )
                conn.execute(
                    """
                    UPDATE monitored_stocks
                    SET status = 'removed', remove_time = ?, remove_reason = ?
                    WHERE stock_code = ? AND status = 'holding'
                    """,
                    (now, reason, stock_code),
                )
            logger.info("移除股票: %s, 原因: %s", stock_code, reason)
            return True, f"成功移除 {stock_code}"
        except Exception as e:
            logger.error("移除股票失败: %s", e)
            return False, f"移除失败: {e}"

    def get_monitored_stocks(self) -> List[Dict]:
        try:
            rows = fetch_all(
                self.db_path,
                "SELECT * FROM monitored_stocks WHERE status = 'holding' ORDER BY add_time DESC",
            )
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error("获取监控列表失败: %s", e)
            return []

    def update_holding_days(self) -> None:
        try:
            today = datetime.now().date()
            with get_conn(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT stock_code, buy_date FROM monitored_stocks WHERE status = 'holding'"
                ).fetchall()
                for r in rows:
                    code, buy_date = r["stock_code"], r["buy_date"]
                    days = (today - datetime.strptime(buy_date, "%Y-%m-%d").date()).days
                    conn.execute(
                        """
                        UPDATE monitored_stocks SET holding_days = ?
                        WHERE stock_code = ? AND status = 'holding'
                        """,
                        (days, code),
                    )
            logger.info("持有天数更新完成")
        except Exception as e:
            logger.error("更新持有天数失败: %s", e)

    def add_sell_alert(
        self,
        stock_code: str,
        stock_name: str,
        alert_type: str,
        alert_reason: str,
        current_price: Optional[float] = None,
        ma5: Optional[float] = None,
        ma20: Optional[float] = None,
        holding_days: Optional[int] = None,
    ) -> bool:
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with get_conn(self.db_path) as conn:
                if conn.execute(
                    """
                    SELECT id FROM sell_alerts
                    WHERE stock_code = ? AND alert_type = ? AND is_sent = 0
                    """,
                    (stock_code, alert_type),
                ).fetchone():
                    return False
                conn.execute(
                    """
                    INSERT INTO sell_alerts
                    (stock_code, stock_name, alert_type, alert_reason,
                     current_price, ma5, ma20, holding_days, alert_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (stock_code, stock_name, alert_type, alert_reason,
                     current_price, ma5, ma20, holding_days, now),
                )
            logger.info("添加卖出提醒: %s - %s", stock_code, alert_reason)
            return True
        except Exception as e:
            logger.error("添加卖出提醒失败: %s", e)
            return False

    def get_pending_alerts(self) -> List[Dict]:
        try:
            rows = fetch_all(
                self.db_path,
                "SELECT * FROM sell_alerts WHERE is_sent = 0 ORDER BY alert_time DESC",
            )
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error("获取提醒失败: %s", e)
            return []

    def mark_alert_sent(self, alert_id: int) -> None:
        try:
            with get_conn(self.db_path) as conn:
                conn.execute("UPDATE sell_alerts SET is_sent = 1 WHERE id = ?", (alert_id,))
        except Exception as e:
            logger.error("标记提醒失败: %s", e)

    def get_history_alerts(self, limit: int = 50) -> List[Dict]:
        try:
            rows = fetch_all(
                self.db_path,
                "SELECT * FROM sell_alerts ORDER BY alert_time DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error("获取历史提醒失败: %s", e)
            return []

    def clear_old_alerts(self, days: int = 30) -> None:
        try:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            with get_conn(self.db_path) as conn:
                cur = conn.execute(
                    "DELETE FROM sell_alerts WHERE alert_time < ? AND is_sent = 1",
                    (cutoff,),
                )
                deleted = cur.rowcount
            logger.info("清理了 %s 条旧提醒记录", deleted)
        except Exception as e:
            logger.error("清理旧提醒失败: %s", e)


# 全局监控器实例
low_price_bull_monitor = LowPriceBullMonitor()
