"""智策板块数据库模块 — 已迁移到 db.base。

存储板块策略历史数据、新闻数据、AI 分析报告与板块追踪。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from core.logging_setup import get_logger
from db.base import get_conn, run_migrations

logger = get_logger(__name__)

_MIGRATIONS = (
    """
    CREATE TABLE IF NOT EXISTS sector_raw_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_date TEXT NOT NULL,
        sector_code TEXT NOT NULL,
        sector_name TEXT,
        price REAL,
        change_pct REAL,
        volume REAL,
        turnover REAL,
        market_cap REAL,
        pe_ratio REAL,
        pb_ratio REAL,
        data_type TEXT,
        data_version INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(data_date, sector_code, data_type)
    );
    CREATE INDEX IF NOT EXISTS idx_sector_data_date ON sector_raw_data(data_date);
    CREATE INDEX IF NOT EXISTS idx_sector_code ON sector_raw_data(sector_code);
    CREATE INDEX IF NOT EXISTS idx_data_type ON sector_raw_data(data_type);
    CREATE INDEX IF NOT EXISTS idx_data_version ON sector_raw_data(data_version);
    CREATE TABLE IF NOT EXISTS sector_news_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        news_date TEXT NOT NULL,
        title TEXT,
        content TEXT,
        source TEXT,
        url TEXT,
        related_sectors TEXT,
        sentiment_score REAL,
        importance_score REAL,
        data_version INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS sector_analysis_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_date TEXT NOT NULL,
        data_date_range TEXT,
        analysis_content TEXT,
        recommended_sectors TEXT,
        summary TEXT,
        confidence_score REAL,
        risk_level TEXT,
        investment_horizon TEXT,
        market_outlook TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS sector_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_id INTEGER,
        sector_code TEXT NOT NULL,
        sector_name TEXT,
        recommended_date TEXT,
        recommended_price REAL,
        target_price REAL,
        stop_loss_price REAL,
        current_price REAL,
        profit_loss_pct REAL,
        status TEXT,
        notes TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (analysis_id) REFERENCES sector_analysis_reports (id)
    );
    CREATE TABLE IF NOT EXISTS data_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_type TEXT NOT NULL,
        data_date TEXT NOT NULL,
        version INTEGER NOT NULL,
        status TEXT DEFAULT 'active',
        fetch_success BOOLEAN DEFAULT 1,
        error_message TEXT,
        record_count INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(data_type, data_date, version)
    );
    """,
)


def _f(row, *keys, default: float = 0.0) -> float:
    """从 row 中按 keys 依次尝试取数,返回浮点数(NaN/None 视为 default)。"""
    for k in keys:
        v = row.get(k) if hasattr(row, "get") else None
        if v is None:
            continue
        try:
            if pd.notna(v):
                return float(v)
        except Exception:
            try:
                return float(v)
            except Exception:
                continue
    return default


def _s(row, *keys, default: str = "") -> str:
    for k in keys:
        v = row.get(k) if hasattr(row, "get") else None
        if v is not None and (not isinstance(v, float) or not pd.isna(v)):
            return str(v)
    return default


# 各 data_type 对 sector_raw_data 各字段的取值键
_SECTOR_RAW_KEY_MAPS: Dict[str, Dict[str, tuple]] = {
    "industry": {
        "sector_code": ("板块代码", "sector_code"),
        "sector_name": ("板块名称", "sector_name"),
        "price": ("最新价", "price"),
        "change_pct": ("涨跌幅", "change_pct"),
        "volume": ("成交量", "volume"),
        "turnover": ("成交额", "turnover"),
        "market_cap": ("总市值", "market_cap"),
        "pe_ratio": ("市盈率", "pe_ratio"),
        "pb_ratio": ("市净率", "pb_ratio"),
    },
    "concept": {  # 与 industry 同结构
        "sector_code": ("板块代码", "sector_code"),
        "sector_name": ("板块名称", "sector_name"),
        "price": ("最新价", "price"),
        "change_pct": ("涨跌幅", "change_pct"),
        "volume": ("成交量", "volume"),
        "turnover": ("成交额", "turnover"),
        "market_cap": ("总市值", "market_cap"),
        "pe_ratio": ("市盈率", "pe_ratio"),
        "pb_ratio": ("市净率", "pb_ratio"),
    },
    "fund_flow": {
        "sector_code": ("行业",),
        "sector_name": ("行业",),
        "price": ("主力净流入-净额",),
        "change_pct": ("主力净流入-净占比",),
        "volume": ("超大单净流入-净额",),
        "turnover": ("超大单净流入-净占比",),
        "market_cap": ("大单净流入-净额",),
        "pe_ratio": ("大单净流入-净占比",),
        "pb_ratio": (),  # 留 0
    },
    "market_overview": {
        "sector_code": ("名称",),
        "sector_name": ("名称",),
        "price": ("最新价",),
        "change_pct": ("涨跌幅",),
        "volume": ("成交量",),
        "turnover": ("成交额",),
        "market_cap": (),
        "pe_ratio": (),
        "pb_ratio": (),
    },
    "north_fund": {
        "sector_code": ("代码",),
        "sector_name": ("名称",),
        "price": ("收盘价",),
        "change_pct": ("涨跌幅",),
        "volume": ("持股数量",),
        "turnover": ("持股市值",),
        "market_cap": ("持股变化",),
        "pe_ratio": (),
        "pb_ratio": (),
    },
}


class SectorStrategyDatabase:
    """智策板块数据库管理类。"""

    def __init__(self, db_path: str = "sector_strategy.db") -> None:
        self.db_path = db_path
        self.logger = logger
        run_migrations(self.db_path, _MIGRATIONS)
        logger.info("[智策板块] 数据库初始化完成")

    def get_connection(self):
        """兼容旧 API:返回带 WAL pragma 的原生连接。"""
        from db.base import legacy_connect
        return legacy_connect(self.db_path)

    # ---------- 通用 raw_data 写入 ----------

    @staticmethod
    def _row_to_sector_raw(row, data_type: str) -> tuple:
        """根据 data_type 把一行 DataFrame -> sector_raw_data 元组。"""
        m = _SECTOR_RAW_KEY_MAPS[data_type]
        return (
            _s(row, *m["sector_code"]),
            _s(row, *m["sector_name"]),
            _f(row, *m["price"]),
            _f(row, *m["change_pct"]),
            _f(row, *m["volume"]),
            _f(row, *m["turnover"]),
            _f(row, *m["market_cap"]),
            _f(row, *m["pe_ratio"]),
            _f(row, *m["pb_ratio"]),
        )

    @staticmethod
    def _next_version_in_conn(conn, data_date: str, data_type: str) -> int:
        row = conn.execute(
            """
            SELECT COALESCE(MAX(version), 0) + 1 FROM data_versions
            WHERE data_type = ? AND data_date = ?
            """,
            (data_type, data_date),
        ).fetchone()
        return int(row[0] or 1)

    def _get_next_version(self, data_date: str, data_type: str) -> int:
        with get_conn(self.db_path) as conn:
            return self._next_version_in_conn(conn, data_date, data_type)

    # ---------- 旧 API: save_raw_data (向后兼容) ----------

    def save_raw_data(
        self,
        data_date: str,
        data_type: str,
        data_df: pd.DataFrame,
        version: Optional[int] = None,
    ) -> int:
        try:
            with get_conn(self.db_path) as conn:
                if version is None:
                    version = self._next_version_in_conn(conn, data_date, data_type)
                if data_type == "sector_data":
                    self._insert_sector_data(conn, data_date, data_df, version)
                elif data_type == "news_data":
                    self._insert_news_data(conn, data_date, data_df, version)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO data_versions
                    (data_type, data_date, version, status, fetch_success, record_count)
                    VALUES (?, ?, ?, 'active', 1, ?)
                    """,
                    (data_type, data_date, version, len(data_df)),
                )
            logger.info(
                "[智策板块] 保存 %s 数据成功 (日期: %s, 版本: %s, 记录数: %s)",
                data_type, data_date, version, len(data_df),
            )
            return version
        except Exception as e:
            try:
                with get_conn(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO data_versions
                        (data_type, data_date, version, status, fetch_success,
                         error_message, record_count)
                        VALUES (?, ?, ?, 'failed', 0, ?, 0)
                        """,
                        (data_type, data_date, version or 1, str(e)),
                    )
            except Exception:
                pass
            logger.error("[智策板块] 保存 %s 数据失败: %s", data_type, e)
            raise

    @staticmethod
    def _insert_sector_data(conn, data_date, data_df, version) -> None:
        for _, row in data_df.iterrows():
            conn.execute(
                """
                INSERT OR REPLACE INTO sector_raw_data
                (data_date, sector_code, sector_name, price, change_pct, volume,
                 turnover, market_cap, pe_ratio, pb_ratio, data_type, data_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'sector_data', ?)
                """,
                (
                    data_date,
                    row.get("sector_code", ""),
                    row.get("sector_name", ""),
                    row.get("price", 0),
                    row.get("change_pct", 0),
                    row.get("volume", 0),
                    row.get("turnover", 0),
                    row.get("market_cap", 0),
                    row.get("pe_ratio", 0),
                    row.get("pb_ratio", 0),
                    version,
                ),
            )

    @staticmethod
    def _insert_news_data(conn, data_date, data_df, version) -> None:
        for _, row in data_df.iterrows():
            conn.execute(
                """
                INSERT OR REPLACE INTO sector_news_data
                (news_date, title, content, source, url, related_sectors,
                 sentiment_score, importance_score, data_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data_date,
                    row.get("title", ""),
                    row.get("content", ""),
                    row.get("source", ""),
                    row.get("url", ""),
                    json.dumps(row.get("related_sectors", []), ensure_ascii=False),
                    row.get("sentiment_score", 0),
                    row.get("importance_score", 0),
                    version,
                ),
            )

    # ---------- 高层 raw_data 保存 (新 API) ----------

    def save_sector_raw_data(
        self, data_date: str, data_type: str, data_df: pd.DataFrame
    ) -> None:
        # 空判断
        if data_df is None:
            is_empty = True
        elif hasattr(data_df, "empty"):
            is_empty = data_df.empty
        elif isinstance(data_df, (list, tuple, set, dict)):
            is_empty = len(data_df) == 0
        else:
            is_empty = False
        if is_empty:
            logger.warning("[智策板块] %s 数据为空,跳过保存", data_type)
            return
        try:
            with get_conn(self.db_path) as conn:
                version = self._next_version_in_conn(conn, data_date, data_type)
                if data_type in _SECTOR_RAW_KEY_MAPS:
                    for _, row in data_df.iterrows():
                        sc, sn, pr, ch, vo, tu, mc, pe, pb = self._row_to_sector_raw(
                            row, data_type
                        )
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO sector_raw_data
                            (data_date, sector_code, sector_name, price, change_pct,
                             volume, turnover, market_cap, pe_ratio, pb_ratio,
                             data_type, data_version)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (data_date, sc, sn, pr, ch, vo, tu, mc, pe, pb,
                             data_type, version),
                        )
                elif data_type == "news":
                    for _, row in data_df.iterrows():
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO sector_news_data
                            (news_date, title, content, source, url, related_sectors,
                             sentiment_score, importance_score, data_version)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                data_date,
                                _s(row, "新闻标题", "title"),
                                _s(row, "新闻内容", "content"),
                                _s(row, "新闻来源", "source"),
                                _s(row, "新闻链接", "url"),
                                json.dumps([], ensure_ascii=False),
                                0,
                                0,
                                version,
                            ),
                        )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO data_versions
                    (data_date, data_type, version, fetch_success, record_count)
                    VALUES (?, ?, ?, 1, ?)
                    """,
                    (data_date, data_type, version, len(data_df)),
                )
            logger.info(
                "[智策板块] %s 数据保存成功 (日期: %s, 版本: %s, 记录数: %s)",
                data_type, data_date, version, len(data_df),
            )
        except Exception as e:
            logger.error("[智策板块] 保存 %s 数据失败: %s", data_type, e)
            raise

    def save_news_data(
        self, news_list: List[Dict], news_date, source: str = "akshare"
    ) -> int:
        if not news_list:
            logger.warning("[智策板块] 新闻列表为空,跳过保存")
            return 0
        try:
            inserted = 0
            with get_conn(self.db_path) as conn:
                version = self._next_version_in_conn(conn, str(news_date), "news")
                for item in news_list:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO sector_news_data
                        (news_date, title, content, source, url, related_sectors,
                         sentiment_score, importance_score, data_version)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(news_date),
                            str(item.get("title", "")),
                            str(item.get("content", "")),
                            str(item.get("source", source)),
                            str(item.get("url", "")),
                            json.dumps(item.get("related_sectors", []), ensure_ascii=False),
                            float(item.get("sentiment_score", 0) or 0),
                            float(item.get("importance_score", 0) or 0),
                            version,
                        ),
                    )
                    inserted += 1
                conn.execute(
                    """
                    INSERT OR REPLACE INTO data_versions
                    (data_date, data_type, version, fetch_success, record_count)
                    VALUES (?, ?, ?, 1, ?)
                    """,
                    (str(news_date), "news", version, inserted),
                )
            logger.info(
                "[智策板块] 保存新闻数据成功 (日期: %s, 版本: %s, 记录数: %s)",
                news_date, version, inserted,
            )
            return inserted
        except Exception as e:
            logger.error("[智策板块] 保存新闻数据失败: %s", e)
            return 0

    # ---------- 读取 ----------

    def get_latest_data(
        self, data_type: str, data_date: Optional[str] = None
    ) -> pd.DataFrame:
        try:
            with get_conn(self.db_path, row_factory=False) as conn:
                if data_date:
                    version_df = pd.read_sql_query(
                        """
                        SELECT version FROM data_versions
                        WHERE data_type = ? AND data_date = ? AND fetch_success = 1
                        ORDER BY version DESC LIMIT 1
                        """,
                        conn, params=[data_type, data_date],
                    )
                else:
                    version_df = pd.read_sql_query(
                        """
                        SELECT data_date, version FROM data_versions
                        WHERE data_type = ? AND fetch_success = 1
                        ORDER BY data_date DESC, version DESC LIMIT 1
                        """,
                        conn, params=[data_type],
                    )
                if version_df.empty:
                    logger.warning("[智策板块] 未找到 %s 的成功数据", data_type)
                    return pd.DataFrame()
                if data_date is None:
                    data_date = version_df.iloc[0]["data_date"]
                version = int(version_df.iloc[0]["version"])
                if data_type == "sector_data":
                    sql = """
                        SELECT * FROM sector_raw_data
                        WHERE data_date = ? AND data_version = ?
                        ORDER BY sector_code
                    """
                elif data_type == "news_data":
                    sql = """
                        SELECT * FROM sector_news_data
                        WHERE news_date = ? AND data_version = ?
                        ORDER BY importance_score DESC
                    """
                else:
                    return pd.DataFrame()
                data_df = pd.read_sql_query(sql, conn, params=[data_date, version])
            logger.info(
                "[智策板块] 获取 %s 数据成功 (日期: %s, 版本: %s, 记录数: %s)",
                data_type, data_date, version, len(data_df),
            )
            return data_df
        except Exception as e:
            logger.error("[智策板块] 获取 %s 数据失败: %s", data_type, e)
            return pd.DataFrame()

    def get_data_versions(self, data_type: str, limit: int = 10) -> pd.DataFrame:
        with get_conn(self.db_path, row_factory=False) as conn:
            return pd.read_sql_query(
                """
                SELECT * FROM data_versions
                WHERE data_type = ?
                ORDER BY data_date DESC, version DESC
                LIMIT ?
                """,
                conn, params=[data_type, limit],
            )

    # ---------- 分析报告 ----------

    def save_analysis_report(
        self,
        data_date_range: str,
        analysis_content: Any,
        recommended_sectors: List,
        summary: str,
        confidence_score: Optional[float] = None,
        risk_level: Optional[str] = None,
        investment_horizon: Optional[str] = None,
        market_outlook: Optional[str] = None,
    ) -> int:
        if isinstance(analysis_content, dict):
            analysis_content = json.dumps(analysis_content, ensure_ascii=False, indent=2)
        with get_conn(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO sector_analysis_reports
                (analysis_date, data_date_range, analysis_content, recommended_sectors,
                 summary, confidence_score, risk_level, investment_horizon, market_outlook)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    data_date_range,
                    analysis_content,
                    json.dumps(recommended_sectors, ensure_ascii=False),
                    summary,
                    confidence_score,
                    risk_level,
                    investment_horizon,
                    market_outlook,
                ),
            )
            report_id = int(cur.lastrowid)
        logger.info("[智策板块] 分析报告已保存 (ID: %s)", report_id)
        return report_id

    def get_analysis_reports(self, limit: int = 10) -> pd.DataFrame:
        with get_conn(self.db_path, row_factory=False) as conn:
            return pd.read_sql_query(
                """
                SELECT * FROM sector_analysis_reports
                ORDER BY created_at DESC
                LIMIT ?
                """,
                conn, params=[limit],
            )

    def get_analysis_report(self, report_id: int) -> Optional[Dict]:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM sector_analysis_reports WHERE id = ?",
                (report_id,),
            ).fetchone()
        if not row:
            return None
        report = dict(row)
        try:
            if report.get("analysis_content"):
                report["analysis_content_parsed"] = json.loads(report["analysis_content"])
            if report.get("recommended_sectors"):
                report["recommended_sectors_parsed"] = json.loads(report["recommended_sectors"])
        except json.JSONDecodeError as e:
            logger.warning("[智策板块] JSON 解析失败: %s", e)
        return report

    def delete_analysis_report(self, report_id: int) -> bool:
        try:
            with get_conn(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM sector_tracking WHERE analysis_id = ?", (report_id,)
                )
                cur = conn.execute(
                    "DELETE FROM sector_analysis_reports WHERE id = ?", (report_id,)
                )
                deleted = cur.rowcount
            if deleted > 0:
                logger.info("[智策板块] 报告删除成功 (ID: %s)", report_id)
                return True
            logger.warning("[智策板块] 未找到要删除的报告 (ID: %s)", report_id)
            return False
        except Exception as e:
            logger.error("[智策板块] 删除报告失败: %s", e)
            return False

    # ---------- 清理 ----------

    def cleanup_old_data(self, data_type: str, keep_days: int = 30) -> int:
        try:
            cutoff_date = (datetime.now() - pd.Timedelta(days=keep_days)).strftime("%Y-%m-%d")
            with get_conn(self.db_path) as conn:
                if data_type == "sector_data":
                    cur = conn.execute(
                        "DELETE FROM sector_raw_data WHERE data_date < ?", (cutoff_date,)
                    )
                elif data_type == "news_data":
                    cur = conn.execute(
                        "DELETE FROM sector_news_data WHERE news_date < ?", (cutoff_date,)
                    )
                else:
                    return 0
                deleted = cur.rowcount
                conn.execute(
                    "DELETE FROM data_versions WHERE data_type = ? AND data_date < ?",
                    (data_type, cutoff_date),
                )
            logger.info("[智策板块] 清理 %s 旧数据完成,删除 %s 条记录", data_type, deleted)
            return deleted
        except Exception as e:
            logger.error("[智策板块] 清理 %s 旧数据失败: %s", data_type, e)
            return 0

    # ---------- 最近原始数据缓存读取 ----------

    def get_latest_raw_data(self, key: str, within_hours: int = 24) -> Optional[Dict]:
        key_map = {
            "sectors": "industry",
            "concepts": "concept",
            "fund_flow": "fund_flow",
            "market_overview": "market_overview",
            "north_flow": "north_fund",
        }
        data_type = key_map.get(key)
        if not data_type:
            return None
        try:
            cutoff = (pd.Timestamp.now() - pd.Timedelta(hours=within_hours)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            with get_conn(self.db_path, row_factory=False) as conn:
                version_df = pd.read_sql_query(
                    """
                    SELECT data_date, version FROM data_versions
                    WHERE data_type = ? AND fetch_success = 1
                    AND datetime(created_at) >= datetime(?)
                    ORDER BY data_date DESC, version DESC LIMIT 1
                    """,
                    conn, params=[data_type, cutoff],
                )
                if version_df.empty:
                    return None
                data_date = version_df.iloc[0]["data_date"]
                version = int(version_df.iloc[0]["version"])
                raw_df = pd.read_sql_query(
                    """
                    SELECT * FROM sector_raw_data
                    WHERE data_type = ? AND data_date = ? AND data_version = ?
                    """,
                    conn, params=[data_type, data_date, version],
                )
            if raw_df.empty:
                return None
            return self._assemble_latest_payload(key, data_date, raw_df)
        except Exception as e:
            logger.error("[智策板块] 获取最近原始数据失败: %s", e)
            return None

    @staticmethod
    def _assemble_latest_payload(
        key: str, data_date: str, raw_df: pd.DataFrame
    ) -> Optional[Dict]:
        if key in ("sectors", "concepts"):
            result = {}
            for _, row in raw_df.iterrows():
                name = str(row.get("sector_name", ""))
                result[name] = {
                    "name": name,
                    "change_pct": float(row.get("change_pct", 0) or 0),
                    "price": float(row.get("price", 0) or 0),
                    "volume": float(row.get("volume", 0) or 0),
                    "turnover": float(row.get("turnover", 0) or 0),
                    "market_cap": float(row.get("market_cap", 0) or 0),
                    "pe_ratio": float(row.get("pe_ratio", 0) or 0),
                    "pb_ratio": float(row.get("pb_ratio", 0) or 0),
                }
            return {"data_date": data_date, "data_content": result}
        if key == "fund_flow":
            today = []
            for _, row in raw_df.iterrows():
                name = str(row.get("sector_name", ""))
                today.append(
                    {
                        "sector": name,
                        "main_net_inflow": float(row.get("price", 0) or 0),
                        "main_net_inflow_pct": float(row.get("change_pct", 0) or 0),
                        "super_large_net_inflow": float(row.get("volume", 0) or 0),
                        "super_large_net_inflow_pct": float(row.get("turnover", 0) or 0),
                        "large_net_inflow": float(row.get("market_cap", 0) or 0),
                        "large_net_inflow_pct": float(row.get("pe_ratio", 0) or 0),
                        "medium_net_inflow": 0,
                        "small_net_inflow": 0,
                    }
                )
            return {"data_date": data_date, "data_content": {"today": today}}
        if key == "market_overview":
            overview: Dict[str, Dict] = {}
            for _, row in raw_df.iterrows():
                name = str(row.get("sector_name", ""))
                entry = {
                    "price": float(row.get("price", 0) or 0),
                    "change_pct": float(row.get("change_pct", 0) or 0),
                    "turnover": float(row.get("turnover", 0) or 0),
                    "volume": float(row.get("volume", 0) or 0),
                }
                if "上证" in name or "沪指" in name or "SH" in name:
                    overview["sh_index"] = entry
                elif "深证" in name or "SZ" in name:
                    overview["sz_index"] = entry
                elif "创业" in name or "CYB" in name:
                    overview["cyb_index"] = entry
            return {"data_date": data_date, "data_content": overview}
        if key == "north_flow":
            total_value = float(raw_df["turnover"].sum()) if not raw_df.empty else 0
            return {
                "data_date": data_date,
                "data_content": {"north_total_amount": total_value, "history": []},
            }
        return None

    def get_latest_news_data(self, within_hours: int = 24) -> Optional[Dict]:
        try:
            cutoff = (pd.Timestamp.now() - pd.Timedelta(hours=within_hours)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            with get_conn(self.db_path, row_factory=False) as conn:
                df = pd.read_sql_query(
                    """
                    SELECT * FROM sector_news_data
                    WHERE datetime(created_at) >= datetime(?)
                    ORDER BY importance_score DESC, created_at DESC
                    """,
                    conn, params=[cutoff],
                )
            if df.empty:
                return None
            news = []
            for _, row in df.iterrows():
                try:
                    related = json.loads(row.get("related_sectors", "[]"))
                except Exception:
                    related = []
                news.append(
                    {
                        "title": row.get("title", ""),
                        "content": row.get("content", ""),
                        "source": row.get("source", ""),
                        "url": row.get("url", ""),
                        "related_sectors": related,
                        "sentiment_score": float(row.get("sentiment_score", 0) or 0),
                        "importance_score": float(row.get("importance_score", 0) or 0),
                        "news_date": row.get("news_date", ""),
                    }
                )
            return {
                "data_date": df.iloc[0]["news_date"] if not df.empty else None,
                "data_content": news,
            }
        except Exception as e:
            logger.error("[智策板块] 获取最近新闻数据失败: %s", e)
            return None
