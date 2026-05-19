#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""净利增长策略监控数据库管理模块 — 已迁移到 db.base。"""
from __future__ import annotations

from datetime import datetime
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
        alert_reason TEXT,
        current_price REAL,
        kdj_k REAL,
        kdj_d REAL,
        kdj_j REAL,
        holding_days INTEGER,
        alert_time TEXT NOT NULL,
        is_processed INTEGER DEFAULT 0
    );
    """,
)


class ProfitGrowthMonitor:
    """净利增长策略监控数据库管理。"""

    def __init__(self, db_path: str = "profit_growth_monitor.db") -> None:
        self.db_path = db_path
        self.logger = logger
        try:
            run_migrations(self.db_path, _MIGRATIONS)
            logger.info("净利增长监控数据库初始化成功")
        except Exception as e:
            logger.error("数据库初始化失败: %s", e)

    def add_stock(
        self,
        stock_code: str,
        stock_name: str,
        buy_price: float,
        buy_date: Optional[str] = None,
    ) -> Tuple[bool, str]:
        try:
            buy_date = buy_date or datetime.now().strftime("%Y-%m-%d")
            add_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
                    (stock_code, stock_name, buy_price, buy_date, add_time),
                )
            logger.info("添加股票到监控: %s %s", stock_code, stock_name)
            return True, f"成功添加 {stock_name} 到监控列表"
        except Exception as e:
            logger.error("添加股票失败: %s", e)
            return False, f"添加失败: {e}"

    def get_monitoring_stocks(self) -> List[Dict]:
        try:
            rows = fetch_all(
                self.db_path,
                "SELECT * FROM monitored_stocks WHERE status = 'holding' ORDER BY add_time DESC",
            )
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error("获取监控股票失败: %s", e)
            return []

    def update_holding_days(self, stock_code: str, days: int) -> bool:
        try:
            with get_conn(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE monitored_stocks SET holding_days = ?
                    WHERE stock_code = ? AND status = 'holding'
                    """,
                    (days, stock_code),
                )
            return True
        except Exception as e:
            logger.error("更新持股天数失败: %s", e)
            return False

    def add_sell_alert(
        self,
        stock_code: str,
        stock_name: str,
        alert_type: str,
        alert_reason: Optional[str] = None,
        current_price: Optional[float] = None,
        kdj_k: Optional[float] = None,
        kdj_d: Optional[float] = None,
        kdj_j: Optional[float] = None,
        holding_days: Optional[int] = None,
    ) -> Tuple[bool, str]:
        try:
            alert_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with get_conn(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO sell_alerts
                    (stock_code, stock_name, alert_type, alert_reason,
                     current_price, kdj_k, kdj_d, kdj_j, holding_days, alert_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (stock_code, stock_name, alert_type, alert_reason,
                     current_price, kdj_k, kdj_d, kdj_j, holding_days, alert_time),
                )
            logger.info("添加卖出提醒: %s - %s", stock_code, alert_type)
            return True, "提醒添加成功"
        except Exception as e:
            logger.error("添加卖出提醒失败: %s", e)
            return False, str(e)

    def get_unprocessed_alerts(self) -> List[Dict]:
        try:
            rows = fetch_all(
                self.db_path,
                "SELECT * FROM sell_alerts WHERE is_processed = 0 ORDER BY alert_time DESC",
            )
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error("获取卖出提醒失败: %s", e)
            return []

    def get_all_alerts(self, limit: int = 50) -> List[Dict]:
        try:
            rows = fetch_all(
                self.db_path,
                "SELECT * FROM sell_alerts ORDER BY alert_time DESC LIMIT ?",
                (limit,),
            )
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error("获取提醒历史失败: %s", e)
            return []

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

    def get_removed_stocks(self, limit: int = 50) -> List[Dict]:
        try:
            rows = fetch_all(
                self.db_path,
                """
                SELECT * FROM monitored_stocks
                WHERE status = 'removed'
                ORDER BY remove_time DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error("获取移除历史失败: %s", e)
            return []


# 全局实例
profit_growth_monitor = ProfitGrowthMonitor()
