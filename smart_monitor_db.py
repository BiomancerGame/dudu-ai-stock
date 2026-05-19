"""智能盯盘 — 数据库模块(已迁移到 db.base)。

记录 AI 决策、交易记录、监控配置、持仓、通知与日志。
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Union

from core.logging_setup import get_logger
from db.base import fetch_all, get_conn, run_migrations

logger = get_logger(__name__)

_MIGRATIONS = (
    """
    CREATE TABLE IF NOT EXISTS monitor_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_name TEXT NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT,
        enabled INTEGER DEFAULT 1,
        check_interval INTEGER DEFAULT 300,
        auto_trade INTEGER DEFAULT 0,
        trading_hours_only INTEGER DEFAULT 1,
        position_size_pct REAL DEFAULT 20,
        stop_loss_pct REAL DEFAULT 5,
        take_profit_pct REAL DEFAULT 10,
        qmt_account_id TEXT,
        notify_email TEXT,
        notify_webhook TEXT,
        has_position INTEGER DEFAULT 0,
        position_cost REAL DEFAULT 0,
        position_quantity INTEGER DEFAULT 0,
        position_date TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(stock_code)
    );
    CREATE TABLE IF NOT EXISTS ai_decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        stock_name TEXT,
        decision_time TEXT NOT NULL,
        trading_session TEXT,
        action TEXT NOT NULL,
        confidence INTEGER,
        reasoning TEXT,
        position_size_pct REAL,
        stop_loss_pct REAL,
        take_profit_pct REAL,
        risk_level TEXT,
        key_price_levels TEXT,
        market_data TEXT,
        account_info TEXT,
        executed INTEGER DEFAULT 0,
        execution_result TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS trade_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        stock_name TEXT,
        trade_type TEXT NOT NULL,
        quantity INTEGER,
        price REAL,
        amount REAL,
        order_id TEXT,
        order_status TEXT,
        ai_decision_id INTEGER,
        trade_time TEXT NOT NULL,
        commission REAL DEFAULT 0,
        tax REAL DEFAULT 0,
        profit_loss REAL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(ai_decision_id) REFERENCES ai_decisions(id)
    );
    CREATE TABLE IF NOT EXISTS position_monitor (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        stock_name TEXT,
        quantity INTEGER,
        cost_price REAL,
        current_price REAL,
        profit_loss REAL,
        profit_loss_pct REAL,
        holding_days INTEGER,
        buy_date TEXT,
        stop_loss_price REAL,
        take_profit_price REAL,
        last_check_time TEXT,
        status TEXT DEFAULT 'holding',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(stock_code)
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT,
        notify_type TEXT NOT NULL,
        notify_target TEXT,
        subject TEXT,
        content TEXT,
        status TEXT DEFAULT 'pending',
        error_msg TEXT,
        sent_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS system_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_level TEXT,
        module TEXT,
        message TEXT,
        details TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """,
)

_LEGACY_COLUMNS = (
    ("monitor_tasks", "has_position", "INTEGER DEFAULT 0"),
    ("monitor_tasks", "position_cost", "REAL DEFAULT 0"),
    ("monitor_tasks", "position_quantity", "INTEGER DEFAULT 0"),
    ("monitor_tasks", "position_date", "TEXT"),
    ("monitor_tasks", "trading_hours_only", "INTEGER DEFAULT 1"),
)

# 允许通过 update_monitor_task 批量更新的字段白名单
_UPDATE_TASK_FIELDS = {
    "task_name", "stock_name", "enabled", "check_interval", "auto_trade",
    "trading_hours_only", "position_size_pct", "stop_loss_pct", "take_profit_pct",
    "qmt_account_id", "notify_email", "notify_webhook",
    "has_position", "position_cost", "position_quantity", "position_date",
}


def _ensure_legacy_columns(db_path: str) -> None:
    """对老库幂等地补齐缺失列。"""
    with get_conn(db_path) as conn:
        for table, col, decl in _LEGACY_COLUMNS:
            try:
                conn.execute(f"SELECT {col} FROM {table} LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
                logger.info("已为 %s.%s 补齐列", table, col)


class SmartMonitorDB:
    """智能盯盘数据库。"""

    def __init__(self, db_file: str = "smart_monitor.db") -> None:
        self.db_file = db_file
        self.logger = logger
        run_migrations(self.db_file, _MIGRATIONS)
        _ensure_legacy_columns(self.db_file)
        logger.info("数据库初始化完成: %s", self.db_file)

    # ========== 监控任务 ==========

    def add_monitor_task(self, task_data: Dict) -> int:
        with get_conn(self.db_file) as conn:
            cur = conn.execute(
                """
                INSERT INTO monitor_tasks
                (task_name, stock_code, stock_name, enabled, check_interval,
                 auto_trade, trading_hours_only, position_size_pct, stop_loss_pct,
                 take_profit_pct, qmt_account_id, notify_email, notify_webhook,
                 has_position, position_cost, position_quantity, position_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_data.get("task_name"),
                    task_data.get("stock_code"),
                    task_data.get("stock_name"),
                    task_data.get("enabled", 1),
                    task_data.get("check_interval", 300),
                    task_data.get("auto_trade", 0),
                    task_data.get("trading_hours_only", 1),
                    task_data.get("position_size_pct", 20),
                    task_data.get("stop_loss_pct", 5),
                    task_data.get("take_profit_pct", 10),
                    task_data.get("qmt_account_id"),
                    task_data.get("notify_email"),
                    task_data.get("notify_webhook"),
                    task_data.get("has_position", 0),
                    task_data.get("position_cost", 0),
                    task_data.get("position_quantity", 0),
                    task_data.get("position_date"),
                ),
            )
            task_id = int(cur.lastrowid)
        pos = (
            f"(持仓: {task_data.get('position_quantity')}股 @ {task_data.get('position_cost')}元)"
            if task_data.get("has_position") else ""
        )
        logger.info(
            "添加监控任务: %s - %s %s",
            task_data.get("stock_code"), task_data.get("task_name"), pos,
        )
        return task_id

    def get_monitor_tasks(self, enabled_only: bool = True) -> List[Dict]:
        sql = "SELECT * FROM monitor_tasks"
        if enabled_only:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY id DESC"
        return [dict(r) for r in fetch_all(self.db_file, sql)]

    def update_monitor_task(
        self,
        task_key: Union[int, str],
        updates: Dict,
    ) -> None:
        """更新监控任务。

        ``task_key`` 为 ``int`` 时按 ``id`` 匹配,为 ``str`` 时按 ``stock_code`` 匹配。
        ``updates`` 中只有 ``_UPDATE_TASK_FIELDS`` 白名单内的字段才会生效。
        """
        clean = {k: v for k, v in updates.items() if k in _UPDATE_TASK_FIELDS}
        if not clean:
            logger.warning("update_monitor_task: 无可更新字段 (task_key=%s)", task_key)
            return
        set_clause = ", ".join(f"{k} = ?" for k in clean)
        where_col = "id" if isinstance(task_key, int) else "stock_code"
        values = list(clean.values()) + [task_key]
        with get_conn(self.db_file) as conn:
            conn.execute(
                f"""
                UPDATE monitor_tasks
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE {where_col} = ?
                """,
                values,
            )
        logger.info("更新监控任务: %s (%s 字段)", task_key, len(clean))

    def delete_monitor_task(self, task_id: int) -> None:
        with get_conn(self.db_file) as conn:
            conn.execute("DELETE FROM monitor_tasks WHERE id = ?", (task_id,))

    # ========== AI 决策 ==========

    def save_ai_decision(self, decision_data: Dict) -> int:
        with get_conn(self.db_file) as conn:
            cur = conn.execute(
                """
                INSERT INTO ai_decisions
                (stock_code, stock_name, decision_time, trading_session,
                 action, confidence, reasoning, position_size_pct,
                 stop_loss_pct, take_profit_pct, risk_level,
                 key_price_levels, market_data, account_info)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_data.get("stock_code"),
                    decision_data.get("stock_name"),
                    decision_data.get("decision_time",
                                      datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    decision_data.get("trading_session"),
                    decision_data.get("action"),
                    decision_data.get("confidence"),
                    decision_data.get("reasoning"),
                    decision_data.get("position_size_pct"),
                    decision_data.get("stop_loss_pct"),
                    decision_data.get("take_profit_pct"),
                    decision_data.get("risk_level"),
                    json.dumps(decision_data.get("key_price_levels", {})),
                    json.dumps(decision_data.get("market_data", {})),
                    json.dumps(decision_data.get("account_info", {})),
                ),
            )
            return int(cur.lastrowid)

    def get_ai_decisions(
        self, stock_code: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        if stock_code:
            sql = """
                SELECT * FROM ai_decisions
                WHERE stock_code = ?
                ORDER BY decision_time DESC
                LIMIT ?
            """
            params = (stock_code, limit)
        else:
            sql = "SELECT * FROM ai_decisions ORDER BY decision_time DESC LIMIT ?"
            params = (limit,)
        decisions = []
        for r in fetch_all(self.db_file, sql, params):
            d = dict(r)
            d["key_price_levels"] = json.loads(d["key_price_levels"]) if d["key_price_levels"] else {}
            d["market_data"] = json.loads(d["market_data"]) if d["market_data"] else {}
            d["account_info"] = json.loads(d["account_info"]) if d["account_info"] else {}
            decisions.append(d)
        return decisions

    def update_decision_execution(self, decision_id: int, executed: bool, result: str) -> None:
        with get_conn(self.db_file) as conn:
            conn.execute(
                """
                UPDATE ai_decisions
                SET executed = ?, execution_result = ?
                WHERE id = ?
                """,
                (1 if executed else 0, result, decision_id),
            )

    # ========== 交易记录 ==========

    def save_trade_record(self, trade_data: Dict) -> int:
        with get_conn(self.db_file) as conn:
            cur = conn.execute(
                """
                INSERT INTO trade_records
                (stock_code, stock_name, trade_type, quantity, price, amount,
                 order_id, order_status, ai_decision_id, trade_time,
                 commission, tax, profit_loss)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade_data.get("stock_code"),
                    trade_data.get("stock_name"),
                    trade_data.get("trade_type"),
                    trade_data.get("quantity"),
                    trade_data.get("price"),
                    trade_data.get("amount"),
                    trade_data.get("order_id"),
                    trade_data.get("order_status"),
                    trade_data.get("ai_decision_id"),
                    trade_data.get("trade_time",
                                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    trade_data.get("commission", 0),
                    trade_data.get("tax", 0),
                    trade_data.get("profit_loss", 0),
                ),
            )
            return int(cur.lastrowid)

    def get_trade_records(
        self, stock_code: Optional[str] = None, limit: int = 100
    ) -> List[Dict]:
        if stock_code:
            sql = """
                SELECT * FROM trade_records
                WHERE stock_code = ?
                ORDER BY trade_time DESC
                LIMIT ?
            """
            params = (stock_code, limit)
        else:
            sql = "SELECT * FROM trade_records ORDER BY trade_time DESC LIMIT ?"
            params = (limit,)
        return [dict(r) for r in fetch_all(self.db_file, sql, params)]

    # ========== 持仓监控 ==========

    def save_position(self, position_data: Dict) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with get_conn(self.db_file) as conn:
            row = conn.execute(
                "SELECT id FROM position_monitor WHERE stock_code = ?",
                (position_data.get("stock_code"),),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE position_monitor
                    SET stock_name = ?, quantity = ?, cost_price = ?,
                        current_price = ?, profit_loss = ?, profit_loss_pct = ?,
                        holding_days = ?, stop_loss_price = ?, take_profit_price = ?,
                        last_check_time = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE stock_code = ?
                    """,
                    (
                        position_data.get("stock_name"),
                        position_data.get("quantity"),
                        position_data.get("cost_price"),
                        position_data.get("current_price"),
                        position_data.get("profit_loss"),
                        position_data.get("profit_loss_pct"),
                        position_data.get("holding_days"),
                        position_data.get("stop_loss_price"),
                        position_data.get("take_profit_price"),
                        now,
                        position_data.get("stock_code"),
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO position_monitor
                    (stock_code, stock_name, quantity, cost_price, current_price,
                     profit_loss, profit_loss_pct, holding_days, buy_date,
                     stop_loss_price, take_profit_price, last_check_time, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        position_data.get("stock_code"),
                        position_data.get("stock_name"),
                        position_data.get("quantity"),
                        position_data.get("cost_price"),
                        position_data.get("current_price"),
                        position_data.get("profit_loss"),
                        position_data.get("profit_loss_pct"),
                        position_data.get("holding_days"),
                        position_data.get("buy_date"),
                        position_data.get("stop_loss_price"),
                        position_data.get("take_profit_price"),
                        now,
                        "holding",
                    ),
                )

    def get_positions(self) -> List[Dict]:
        rows = fetch_all(
            self.db_file,
            "SELECT * FROM position_monitor WHERE status = 'holding' ORDER BY id DESC",
        )
        return [dict(r) for r in rows]

    def close_position(self, stock_code: str) -> None:
        with get_conn(self.db_file) as conn:
            conn.execute(
                """
                UPDATE position_monitor
                SET status = 'closed', updated_at = CURRENT_TIMESTAMP
                WHERE stock_code = ?
                """,
                (stock_code,),
            )

    # ========== 通知 ==========

    def save_notification(self, notify_data: Dict) -> int:
        with get_conn(self.db_file) as conn:
            cur = conn.execute(
                """
                INSERT INTO notifications
                (stock_code, notify_type, notify_target, subject, content, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    notify_data.get("stock_code"),
                    notify_data.get("notify_type"),
                    notify_data.get("notify_target"),
                    notify_data.get("subject"),
                    notify_data.get("content"),
                    notify_data.get("status", "pending"),
                ),
            )
            return int(cur.lastrowid)

    def update_notification_status(
        self, notify_id: int, status: str, error_msg: Optional[str] = None
    ) -> None:
        with get_conn(self.db_file) as conn:
            conn.execute(
                """
                UPDATE notifications
                SET status = ?, error_msg = ?, sent_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, error_msg, notify_id),
            )

    # ========== 系统日志 ==========

    def log_system_event(
        self, level: str, module: str, message: str, details: Optional[str] = None
    ) -> None:
        with get_conn(self.db_file) as conn:
            conn.execute(
                """
                INSERT INTO system_logs (log_level, module, message, details)
                VALUES (?, ?, ?, ?)
                """,
                (level, module, message, details),
            )
