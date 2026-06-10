"""智囊团游资龙虎榜数据库模块 — 已迁移到 db.base。

存储龙虎榜历史数据和 AI 分析报告。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from core.logging_setup import get_logger
from db.base import get_conn, run_migrations

logger = get_logger(__name__)

_MIGRATIONS = (
    """
    CREATE TABLE IF NOT EXISTS longhubang_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT,
        youzi_name TEXT,
        yingye_bu TEXT,
        list_type TEXT,
        buy_amount REAL,
        sell_amount REAL,
        net_inflow REAL,
        concepts TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(date, stock_code, youzi_name, yingye_bu)
    );
    CREATE INDEX IF NOT EXISTS idx_date ON longhubang_records(date);
    CREATE INDEX IF NOT EXISTS idx_stock_code ON longhubang_records(stock_code);
    CREATE INDEX IF NOT EXISTS idx_youzi_name ON longhubang_records(youzi_name);
    CREATE INDEX IF NOT EXISTS idx_net_inflow ON longhubang_records(net_inflow);
    CREATE TABLE IF NOT EXISTS longhubang_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_date TEXT NOT NULL,
        data_date_range TEXT,
        analysis_content TEXT,
        recommended_stocks TEXT,
        summary TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS stock_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_id INTEGER,
        stock_code TEXT NOT NULL,
        stock_name TEXT,
        recommended_date TEXT,
        recommended_price REAL,
        target_price REAL,
        stop_loss_price REAL,
        current_price REAL,
        profit_loss_pct REAL,
        status TEXT,
        notes TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(analysis_id) REFERENCES longhubang_analysis(id)
    );
    """,
)


class LonghubangDatabase:
    """龙虎榜数据库管理类。"""

    def __init__(self, db_path: str = "longhubang.db") -> None:
        self.db_path = db_path
        self.logger = logger
        run_migrations(self.db_path, _MIGRATIONS)
        logger.info("[智囊团游资龙虎榜] 数据库初始化完成")

    def get_connection(self):
        """兼容旧 API:返回带 WAL pragma 的原生连接。"""
        from db.base import legacy_connect
        return legacy_connect(self.db_path)

    # ---------- 龙虎榜原始数据 ----------

    def save_longhubang_data(self, data_list: List[Dict]) -> int:
        if not data_list:
            return 0
        saved = 0
        with get_conn(self.db_path) as conn:
            for record in data_list:
                try:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO longhubang_records
                        (date, stock_code, stock_name, youzi_name, yingye_bu, list_type,
                         buy_amount, sell_amount, net_inflow, concepts)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record.get("rq") or record.get("日期"),
                            record.get("gpdm") or record.get("股票代码"),
                            record.get("gpmc") or record.get("股票名称"),
                            record.get("yzmc") or record.get("游资名称"),
                            record.get("yyb") or record.get("营业部"),
                            record.get("sblx") or record.get("榜单类型"),
                            float(record.get("mrje") or record.get("买入金额") or 0),
                            float(record.get("mcje") or record.get("卖出金额") or 0),
                            float(record.get("jlrje") or record.get("净流入金额") or 0),
                            record.get("gl") or record.get("概念"),
                        ),
                    )
                    saved += 1
                except Exception as e:
                    logger.exception("保存记录失败: %s", e)
        logger.info("[智囊团游资龙虎榜] 成功保存 %s 条龙虎榜记录", saved)
        return saved

    def get_longhubang_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        stock_code: Optional[str] = None,
    ) -> pd.DataFrame:
        query = "SELECT * FROM longhubang_records WHERE 1=1"
        params: list = []
        if start_date:
            query += " AND date >= ?"; params.append(start_date)
        if end_date:
            query += " AND date <= ?"; params.append(end_date)
        if stock_code:
            query += " AND stock_code = ?"; params.append(stock_code)
        query += " ORDER BY date DESC, net_inflow DESC"
        with get_conn(self.db_path, row_factory=False) as conn:
            return pd.read_sql_query(query, conn, params=params)

    def get_top_youzi(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
    ) -> pd.DataFrame:
        query = """
        SELECT
            youzi_name,
            COUNT(*) as trade_count,
            SUM(buy_amount) as total_buy,
            SUM(sell_amount) as total_sell,
            SUM(net_inflow) as total_net_inflow
        FROM longhubang_records
        WHERE 1=1
        """
        params: list = []
        if start_date:
            query += " AND date >= ?"; params.append(start_date)
        if end_date:
            query += " AND date <= ?"; params.append(end_date)
        query += " GROUP BY youzi_name ORDER BY total_net_inflow DESC LIMIT ?"
        params.append(limit)
        with get_conn(self.db_path, row_factory=False) as conn:
            return pd.read_sql_query(query, conn, params=params)

    def get_top_stocks(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 20,
    ) -> pd.DataFrame:
        query = """
        SELECT
            stock_code,
            stock_name,
            COUNT(DISTINCT youzi_name) as youzi_count,
            SUM(buy_amount) as total_buy,
            SUM(sell_amount) as total_sell,
            SUM(net_inflow) as total_net_inflow,
            GROUP_CONCAT(DISTINCT concepts) as all_concepts
        FROM longhubang_records
        WHERE 1=1
        """
        params: list = []
        if start_date:
            query += " AND date >= ?"; params.append(start_date)
        if end_date:
            query += " AND date <= ?"; params.append(end_date)
        query += """
        GROUP BY stock_code, stock_name
        ORDER BY total_net_inflow DESC
        LIMIT ?
        """
        params.append(limit)
        with get_conn(self.db_path, row_factory=False) as conn:
            return pd.read_sql_query(query, conn, params=params)

    # ---------- AI 分析报告 ----------

    def save_analysis_report(
        self,
        data_date_range: str,
        analysis_content,
        recommended_stocks,
        summary: str,
        full_result=None,
    ) -> int:
        if isinstance(analysis_content, dict):
            analysis_content = json.dumps(analysis_content, ensure_ascii=False, indent=2)
        with get_conn(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO longhubang_analysis
                (analysis_date, data_date_range, analysis_content, recommended_stocks, summary)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    data_date_range,
                    analysis_content,
                    json.dumps(recommended_stocks, ensure_ascii=False),
                    summary,
                ),
            )
            report_id = int(cur.lastrowid)
        logger.info("[智囊团游资龙虎榜] 分析报告已保存 (ID: %s)", report_id)
        return report_id

    def get_analysis_reports(self, limit: int = 10) -> pd.DataFrame:
        with get_conn(self.db_path, row_factory=False) as conn:
            return pd.read_sql_query(
                "SELECT * FROM longhubang_analysis ORDER BY created_at DESC LIMIT ?",
                conn,
                params=[limit],
            )

    def get_analysis_report(self, report_id: int) -> Optional[Dict]:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM longhubang_analysis WHERE id = ?", (report_id,)
            ).fetchone()
        if not row:
            return None
        report = dict(row)
        if report.get("recommended_stocks"):
            try:
                report["recommended_stocks"] = json.loads(report["recommended_stocks"])
            except Exception as e:
                logger.warning("推荐股票JSON解析失败: %s", e)
        if report.get("analysis_content"):
            try:
                report["analysis_content_parsed"] = json.loads(report["analysis_content"])
            except json.JSONDecodeError as e:
                report["analysis_content_parsed"] = None
                logger.debug("analysis_content 不是 JSON,保持文本: %s", str(e)[:100])
            except Exception as e:
                report["analysis_content_parsed"] = None
                logger.warning("analysis_content 解析失败: %s", str(e)[:100])
        return report

    def delete_analysis_report(self, report_id: int) -> bool:
        try:
            with get_conn(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM stock_tracking WHERE analysis_id = ?", (report_id,)
                )
                cur = conn.execute(
                    "DELETE FROM longhubang_analysis WHERE id = ?", (report_id,)
                )
                deleted = cur.rowcount
            if deleted > 0:
                logger.info("[智囊团游资龙虎榜] 成功删除分析报告 (ID: %s)", report_id)
                return True
            logger.warning("[智囊团游资龙虎榜] 未找到要删除的分析报告 (ID: %s)", report_id)
            return False
        except Exception as e:
            logger.error("[智囊团游资龙虎榜] 删除分析报告失败: %s", e)
            return False

    def update_stock_tracking(
        self,
        analysis_id: int,
        stock_code: str,
        current_price: float,
        status: str,
        notes: Optional[str] = None,
    ) -> None:
        with get_conn(self.db_path) as conn:
            conn.execute(
                """
                UPDATE stock_tracking
                SET current_price = ?, status = ?, notes = ?, updated_at = ?
                WHERE analysis_id = ? AND stock_code = ?
                """,
                (current_price, status, notes,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 analysis_id, stock_code),
            )

    def get_statistics(self) -> Dict:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM longhubang_records) AS total_records,
                    (SELECT COUNT(DISTINCT stock_code) FROM longhubang_records) AS total_stocks,
                    (SELECT COUNT(DISTINCT youzi_name) FROM longhubang_records) AS total_youzi,
                    (SELECT COUNT(*) FROM longhubang_analysis) AS total_reports,
                    (SELECT MIN(date) FROM longhubang_records) AS date_min,
                    (SELECT MAX(date) FROM longhubang_records) AS date_max
                """
            ).fetchone()
        return {
            "total_records": row["total_records"],
            "total_stocks": row["total_stocks"],
            "total_youzi": row["total_youzi"],
            "total_reports": row["total_reports"],
            "date_range": {"start": row["date_min"], "end": row["date_max"]},
        }
