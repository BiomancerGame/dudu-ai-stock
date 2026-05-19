"""新闻流量数据库模块 — 已迁移到 db.base。

存储和管理新闻流量监测数据:快照、新闻、情绪、预警、AI 分析、定时任务日志、预警配置。
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.logging_setup import get_logger
from db.base import fetch_all, get_conn, run_migrations

logger = get_logger(__name__)

_MIGRATIONS = (
    """
    CREATE TABLE IF NOT EXISTS flow_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fetch_time TEXT NOT NULL,
        total_platforms INTEGER NOT NULL,
        success_count INTEGER NOT NULL,
        total_score INTEGER NOT NULL,
        flow_level TEXT NOT NULL,
        social_score INTEGER,
        news_score INTEGER,
        finance_score INTEGER,
        tech_score INTEGER,
        analysis TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS platform_news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        platform TEXT NOT NULL,
        platform_name TEXT NOT NULL,
        category TEXT NOT NULL,
        weight INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT,
        url TEXT,
        source TEXT,
        publish_time TEXT,
        rank INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (snapshot_id) REFERENCES flow_snapshots(id)
    );
    CREATE TABLE IF NOT EXISTS stock_related_news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        platform TEXT NOT NULL,
        platform_name TEXT NOT NULL,
        category TEXT NOT NULL,
        weight INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT,
        url TEXT,
        source TEXT,
        publish_time TEXT,
        matched_keywords TEXT,
        keyword_count INTEGER,
        score INTEGER DEFAULT 0,
        rank INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (snapshot_id) REFERENCES flow_snapshots(id)
    );
    CREATE TABLE IF NOT EXISTS hot_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        topic TEXT NOT NULL,
        count INTEGER NOT NULL,
        heat INTEGER NOT NULL,
        cross_platform INTEGER,
        sources TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (snapshot_id) REFERENCES flow_snapshots(id)
    );
    CREATE TABLE IF NOT EXISTS flow_statistics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL UNIQUE,
        avg_score INTEGER,
        max_score INTEGER,
        min_score INTEGER,
        snapshot_count INTEGER,
        top_topics TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS sentiment_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER,
        sentiment_index INTEGER NOT NULL,
        sentiment_class TEXT NOT NULL,
        flow_stage TEXT NOT NULL,
        momentum REAL,
        viral_k REAL,
        flow_type TEXT,
        stage_analysis TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (snapshot_id) REFERENCES flow_snapshots(id)
    );
    CREATE TABLE IF NOT EXISTS flow_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type TEXT NOT NULL,
        alert_level TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT,
        related_topics TEXT,
        trigger_value TEXT,
        threshold_value TEXT,
        is_notified INTEGER DEFAULT 0,
        snapshot_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (snapshot_id) REFERENCES flow_snapshots(id)
    );
    CREATE TABLE IF NOT EXISTS ai_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER,
        affected_sectors TEXT,
        recommended_stocks TEXT,
        risk_level TEXT,
        risk_factors TEXT,
        advice TEXT,
        confidence INTEGER,
        summary TEXT,
        raw_response TEXT,
        model_used TEXT,
        analysis_time REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (snapshot_id) REFERENCES flow_snapshots(id)
    );
    CREATE TABLE IF NOT EXISTS scheduler_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_name TEXT NOT NULL,
        task_type TEXT,
        status TEXT NOT NULL,
        message TEXT,
        duration REAL,
        snapshot_id INTEGER,
        executed_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS alert_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_key TEXT NOT NULL UNIQUE,
        config_value TEXT NOT NULL,
        description TEXT,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """,
)

_DEFAULT_CONFIGS = (
    ("heat_threshold", "800", "热度飙升阈值"),
    ("rank_change_threshold", "10", "排名变化阈值"),
    ("sentiment_high_threshold", "90", "情绪高位阈值"),
    ("sentiment_low_threshold", "20", "情绪低位阈值"),
    ("viral_k_threshold", "1.5", "K值阈值"),
    ("alert_enabled", "true", "预警开关"),
    ("notification_enabled", "true", "通知开关"),
)

# 老库列兼容(向后兼容,对应原 _migrate_database)
_LEGACY_COLUMNS = (
    ("stock_related_news", "score", "INTEGER DEFAULT 0"),
    ("stock_related_news", "rank", "INTEGER"),
    ("platform_news", "rank", "INTEGER"),
    ("hot_topics", "cross_platform", "INTEGER"),
    ("hot_topics", "sources", "TEXT"),
)


def _ensure_legacy_columns(db_path: str) -> None:
    with get_conn(db_path) as conn:
        for table, col, decl in _LEGACY_COLUMNS:
            try:
                cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
                if col not in cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
                    logger.info("已为 %s 添加列 %s", table, col)
            except sqlite3.OperationalError as e:
                logger.warning("迁移列 %s.%s 时出错: %s", table, col, e)


def _parse_json_fields(d: Dict, *fields: str) -> Dict:
    """就地把 d 中的指定 JSON 字段解析为对象;空则用 [] 占位。"""
    for f in fields:
        try:
            d[f] = json.loads(d[f]) if d.get(f) else []
        except (TypeError, json.JSONDecodeError):
            d[f] = []
    return d


class NewsFlowDatabase:
    """新闻流量数据库管理类。"""

    def __init__(self, db_path: str = "news_flow.db") -> None:
        self.db_path = db_path
        run_migrations(self.db_path, _MIGRATIONS)
        _ensure_legacy_columns(self.db_path)
        with get_conn(self.db_path) as conn:
            for key, value, desc in _DEFAULT_CONFIGS:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO alert_config (config_key, config_value, description)
                    VALUES (?, ?, ?)
                    """,
                    (key, value, desc),
                )
        logger.info("新闻流量数据库初始化完成: %s", self.db_path)

    def get_connection(self):
        """兼容旧 API。"""
        from db.base import legacy_connect
        conn = legacy_connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ==================== 快照 ====================

    def save_flow_snapshot(
        self,
        flow_data: Dict,
        platforms_data: List[Dict],
        stock_news: List[Dict],
        hot_topics: List[Dict],
    ) -> int:
        try:
            with get_conn(self.db_path) as conn:
                cur = conn.execute(
                    """
                    INSERT INTO flow_snapshots
                    (fetch_time, total_platforms, success_count, total_score, flow_level,
                     social_score, news_score, finance_score, tech_score, analysis)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        len(platforms_data),
                        sum(1 for p in platforms_data if p.get("success")),
                        flow_data["total_score"],
                        flow_data["level"],
                        flow_data.get("social_score", 0),
                        flow_data.get("news_score", 0),
                        flow_data.get("finance_score", 0),
                        flow_data.get("tech_score", 0),
                        flow_data.get("analysis", ""),
                    ),
                )
                snapshot_id = int(cur.lastrowid)
                # 平台新闻
                for pd in platforms_data:
                    if not pd.get("success"):
                        continue
                    for news in pd.get("data", []):
                        conn.execute(
                            """
                            INSERT INTO platform_news
                            (snapshot_id, platform, platform_name, category, weight,
                             title, content, url, source, publish_time, rank)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                snapshot_id, pd["platform"], pd["platform_name"],
                                pd["category"], pd["weight"],
                                news.get("title") or "",
                                news.get("content") or "",
                                news.get("url") or "",
                                news.get("source") or "",
                                news.get("publish_time") or "",
                                news.get("rank", 0),
                            ),
                        )
                # 股票相关新闻
                for news in stock_news:
                    conn.execute(
                        """
                        INSERT INTO stock_related_news
                        (snapshot_id, platform, platform_name, category, weight,
                         title, content, url, source, publish_time, matched_keywords,
                         keyword_count, score)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            snapshot_id, news["platform"], news["platform_name"],
                            news["category"], news["weight"], news["title"],
                            news.get("content") or "",
                            news.get("url") or "",
                            news.get("source") or "",
                            news.get("publish_time") or "",
                            json.dumps(news.get("matched_keywords", []), ensure_ascii=False),
                            news.get("keyword_count", 0),
                            news.get("score", 0),
                        ),
                    )
                # 热门话题
                for topic in hot_topics:
                    conn.execute(
                        """
                        INSERT INTO hot_topics
                        (snapshot_id, topic, count, heat, cross_platform, sources)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            snapshot_id, topic["topic"], topic["count"], topic["heat"],
                            topic.get("cross_platform", 0),
                            json.dumps(topic.get("sources", []), ensure_ascii=False),
                        ),
                    )
                # 每日统计
                self._update_daily_statistics(conn, flow_data["total_score"], hot_topics)
            logger.info("保存流量快照成功,ID: %s", snapshot_id)
            return snapshot_id
        except Exception as e:
            logger.error("保存流量快照失败: %s", e)
            raise

    @staticmethod
    def _update_daily_statistics(conn, score: int, hot_topics: List[Dict]) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        row = conn.execute(
            """
            SELECT avg_score, max_score, min_score, snapshot_count, top_topics
            FROM flow_statistics WHERE date = ?
            """,
            (today,),
        ).fetchone()
        if row:
            old_avg = row["avg_score"] or 0
            old_count = row["snapshot_count"] or 0
            new_avg = int((old_avg * old_count + score) / (old_count + 1))
            new_max = max(row["max_score"] or 0, score)
            new_min = min(row["min_score"] or 999999, score)
            old_topics = json.loads(row["top_topics"]) if row["top_topics"] else []
            new_topics = old_topics + [t["topic"] for t in hot_topics[:10]]
            top_topics = [t for t, _ in Counter(new_topics).most_common(20)]
            conn.execute(
                """
                UPDATE flow_statistics
                SET avg_score = ?, max_score = ?, min_score = ?,
                    snapshot_count = ?, top_topics = ?
                WHERE date = ?
                """,
                (new_avg, new_max, new_min, old_count + 1,
                 json.dumps(top_topics, ensure_ascii=False), today),
            )
        else:
            top_topics = [t["topic"] for t in hot_topics[:20]]
            conn.execute(
                """
                INSERT INTO flow_statistics
                (date, avg_score, max_score, min_score, snapshot_count, top_topics)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (today, score, score, score, 1,
                 json.dumps(top_topics, ensure_ascii=False)),
            )

    def get_latest_snapshot(self) -> Optional[Dict]:
        rows = fetch_all(
            self.db_path,
            "SELECT * FROM flow_snapshots ORDER BY created_at DESC LIMIT 1",
        )
        return dict(rows[0]) if rows else None

    def get_recent_snapshots(self, limit: int = 10) -> List[Dict]:
        rows = fetch_all(
            self.db_path,
            "SELECT * FROM flow_snapshots ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in rows]

    def get_snapshot_detail(self, snapshot_id: int) -> Dict:
        with get_conn(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM flow_snapshots WHERE id = ?", (snapshot_id,)
            ).fetchone()
            if not row:
                return {}
            snapshot = dict(row)
            stock_news = [
                _parse_json_fields(dict(r), "matched_keywords")
                for r in conn.execute(
                    """
                    SELECT * FROM stock_related_news
                    WHERE snapshot_id = ?
                    ORDER BY COALESCE(score, 0) DESC, weight DESC
                    """,
                    (snapshot_id,),
                )
            ]
            hot_topics = [
                _parse_json_fields(dict(r), "sources")
                for r in conn.execute(
                    "SELECT * FROM hot_topics WHERE snapshot_id = ? ORDER BY heat DESC",
                    (snapshot_id,),
                )
            ]
            srow = conn.execute(
                """
                SELECT * FROM sentiment_records
                WHERE snapshot_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (snapshot_id,),
            ).fetchone()
            sentiment = dict(srow) if srow else None
            arow = conn.execute(
                """
                SELECT * FROM ai_analysis
                WHERE snapshot_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (snapshot_id,),
            ).fetchone()
            ai_analysis = (
                _parse_json_fields(
                    dict(arow), "affected_sectors", "recommended_stocks", "risk_factors"
                )
                if arow else None
            )
        return {
            "snapshot": snapshot,
            "stock_news": stock_news,
            "hot_topics": hot_topics,
            "sentiment": sentiment,
            "ai_analysis": ai_analysis,
        }

    def get_history_snapshots(self, limit: int = 50) -> List[Dict]:
        rows = fetch_all(
            self.db_path,
            """
            SELECT id, fetch_time, total_score, flow_level,
                   success_count, total_platforms, analysis
            FROM flow_snapshots
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in rows]

    def get_daily_statistics(self, days: int = 7) -> List[Dict]:
        rows = fetch_all(
            self.db_path,
            "SELECT * FROM flow_statistics ORDER BY date DESC LIMIT ?",
            (days,),
        )
        return [_parse_json_fields(dict(r), "top_topics") for r in rows]

    def get_recent_scores(self, hours: int = 24) -> List[Dict]:
        since = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        rows = fetch_all(
            self.db_path,
            """
            SELECT id, fetch_time, total_score, flow_level
            FROM flow_snapshots
            WHERE fetch_time >= ?
            ORDER BY fetch_time ASC
            """,
            (since,),
        )
        return [dict(r) for r in rows]

    def search_stock_news(self, keyword: str, limit: int = 50) -> List[Dict]:
        pat = f"%{keyword}%"
        rows = fetch_all(
            self.db_path,
            """
            SELECT srn.*, fs.fetch_time, fs.flow_level
            FROM stock_related_news srn
            JOIN flow_snapshots fs ON srn.snapshot_id = fs.id
            WHERE srn.title LIKE ? OR srn.content LIKE ?
            ORDER BY srn.created_at DESC
            LIMIT ?
            """,
            (pat, pat, limit),
        )
        return [_parse_json_fields(dict(r), "matched_keywords") for r in rows]

    # ==================== 情绪 ====================

    def save_sentiment_record(self, snapshot_id: int, sentiment_data: Dict) -> int:
        with get_conn(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO sentiment_records
                (snapshot_id, sentiment_index, sentiment_class, flow_stage,
                 momentum, viral_k, flow_type, stage_analysis)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    sentiment_data.get("sentiment_index", 50),
                    sentiment_data.get("sentiment_class", "中性"),
                    sentiment_data.get("flow_stage", "未知"),
                    sentiment_data.get("momentum", 0),
                    sentiment_data.get("viral_k", 1.0),
                    sentiment_data.get("flow_type", "未知"),
                    sentiment_data.get("stage_analysis", ""),
                ),
            )
            return int(cur.lastrowid)

    def get_sentiment_history(self, limit: int = 50) -> List[Dict]:
        rows = fetch_all(
            self.db_path,
            """
            SELECT sr.*, fs.fetch_time, fs.total_score
            FROM sentiment_records sr
            LEFT JOIN flow_snapshots fs ON sr.snapshot_id = fs.id
            ORDER BY sr.created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in rows]

    def get_latest_sentiment(self) -> Optional[Dict]:
        rows = fetch_all(
            self.db_path,
            """
            SELECT sr.*, fs.fetch_time, fs.total_score, fs.flow_level
            FROM sentiment_records sr
            LEFT JOIN flow_snapshots fs ON sr.snapshot_id = fs.id
            ORDER BY sr.created_at DESC
            LIMIT 1
            """,
        )
        return dict(rows[0]) if rows else None

    # ==================== 预警 ====================

    def save_alert(self, alert_data: Dict) -> int:
        with get_conn(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO flow_alerts
                (alert_type, alert_level, title, content, related_topics,
                 trigger_value, threshold_value, is_notified, snapshot_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert_data["alert_type"],
                    alert_data.get("alert_level", "info"),
                    alert_data["title"],
                    alert_data.get("content", ""),
                    json.dumps(alert_data.get("related_topics", []), ensure_ascii=False),
                    str(alert_data.get("trigger_value", "")),
                    str(alert_data.get("threshold_value", "")),
                    1 if alert_data.get("is_notified") else 0,
                    alert_data.get("snapshot_id"),
                ),
            )
            return int(cur.lastrowid)

    def get_alerts(self, days: int = 7, alert_type: Optional[str] = None) -> List[Dict]:
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        if alert_type:
            sql = """
                SELECT * FROM flow_alerts
                WHERE created_at >= ? AND alert_type = ?
                ORDER BY created_at DESC
            """
            params = (since, alert_type)
        else:
            sql = """
                SELECT * FROM flow_alerts
                WHERE created_at >= ?
                ORDER BY created_at DESC
            """
            params = (since,)
        rows = fetch_all(self.db_path, sql, params)
        return [_parse_json_fields(dict(r), "related_topics") for r in rows]

    def get_unnotified_alerts(self) -> List[Dict]:
        rows = fetch_all(
            self.db_path,
            "SELECT * FROM flow_alerts WHERE is_notified = 0 ORDER BY created_at DESC",
        )
        return [_parse_json_fields(dict(r), "related_topics") for r in rows]

    def mark_alert_notified(self, alert_id: int) -> None:
        with get_conn(self.db_path) as conn:
            conn.execute("UPDATE flow_alerts SET is_notified = 1 WHERE id = ?", (alert_id,))

    # ==================== AI 分析 ====================

    def save_ai_analysis(self, snapshot_id: int, analysis_data: Dict) -> int:
        with get_conn(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO ai_analysis
                (snapshot_id, affected_sectors, recommended_stocks, risk_level,
                 risk_factors, advice, confidence, summary, raw_response,
                 model_used, analysis_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    json.dumps(analysis_data.get("affected_sectors", []), ensure_ascii=False),
                    json.dumps(analysis_data.get("recommended_stocks", []), ensure_ascii=False),
                    analysis_data.get("risk_level", "未知"),
                    json.dumps(analysis_data.get("risk_factors", []), ensure_ascii=False),
                    analysis_data.get("advice", "观望"),
                    analysis_data.get("confidence", 50),
                    analysis_data.get("summary", ""),
                    analysis_data.get("raw_response", ""),
                    analysis_data.get("model_used", "unknown"),
                    analysis_data.get("analysis_time", 0),
                ),
            )
            return int(cur.lastrowid)

    def get_latest_ai_analysis(self) -> Optional[Dict]:
        rows = fetch_all(
            self.db_path,
            """
            SELECT aa.*, fs.fetch_time, fs.total_score, fs.flow_level
            FROM ai_analysis aa
            LEFT JOIN flow_snapshots fs ON aa.snapshot_id = fs.id
            ORDER BY aa.created_at DESC
            LIMIT 1
            """,
        )
        if not rows:
            return None
        return _parse_json_fields(
            dict(rows[0]), "affected_sectors", "recommended_stocks", "risk_factors"
        )

    def get_ai_analysis_history(self, limit: int = 20) -> List[Dict]:
        rows = fetch_all(
            self.db_path,
            """
            SELECT aa.*, fs.fetch_time, fs.total_score, fs.flow_level
            FROM ai_analysis aa
            LEFT JOIN flow_snapshots fs ON aa.snapshot_id = fs.id
            ORDER BY aa.created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [
            _parse_json_fields(
                dict(r), "affected_sectors", "recommended_stocks", "risk_factors"
            )
            for r in rows
        ]

    # ==================== 定时任务日志 ====================

    def save_scheduler_log(
        self,
        task_name: str,
        task_type: str,
        status: str,
        message: str = "",
        duration: float = 0,
        snapshot_id: Optional[int] = None,
    ) -> int:
        with get_conn(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO scheduler_logs
                (task_name, task_type, status, message, duration, snapshot_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_name, task_type, status, message, duration, snapshot_id),
            )
            return int(cur.lastrowid)

    def get_scheduler_logs(
        self, days: int = 7, task_type: Optional[str] = None
    ) -> List[Dict]:
        since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        if task_type:
            sql = """
                SELECT * FROM scheduler_logs
                WHERE executed_at >= ? AND task_type = ?
                ORDER BY executed_at DESC
            """
            params = (since, task_type)
        else:
            sql = """
                SELECT * FROM scheduler_logs
                WHERE executed_at >= ?
                ORDER BY executed_at DESC
            """
            params = (since,)
        return [dict(r) for r in fetch_all(self.db_path, sql, params)]

    # ==================== 预警配置 ====================

    def get_alert_config(self, key: str) -> Optional[str]:
        rows = fetch_all(
            self.db_path,
            "SELECT config_value FROM alert_config WHERE config_key = ?",
            (key,),
        )
        return rows[0]["config_value"] if rows else None

    def set_alert_config(
        self, key: str, value: str, description: Optional[str] = None
    ) -> None:
        with get_conn(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO alert_config
                (config_key, config_value, description, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (key, value, description,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )

    def get_all_alert_configs(self) -> Dict[str, str]:
        rows = fetch_all(
            self.db_path,
            "SELECT config_key, config_value FROM alert_config",
        )
        return {r["config_key"]: r["config_value"] for r in rows}


# 全局数据库实例
news_flow_db = NewsFlowDatabase()
