"""共性追踪数据库模块

场景：用户每个交易日选一只股票，形成日期序列。
AI分析这些历史选股的共性规律，预测下一个交易日的那只股票。
不断追加数据、验证、学习。

表结构：
- daily_picks: 每日选股记录（日期、代码、名称、买入价）
- analysis_rounds: 每次分析轮次（输入数据范围、共性结论、预测）
- verifications: 预测验证记录
- learning_rules: 从验证中学到的规则
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

from db.base import get_conn, run_migrations

DB_PATH = "commonality_tracker.db"

_MIGRATIONS_V2 = (
    # v0: 新版表结构
    """
    CREATE TABLE IF NOT EXISTS daily_picks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pick_date TEXT NOT NULL,
        symbol TEXT NOT NULL,
        name TEXT DEFAULT '',
        entry_price REAL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(pick_date, symbol)
    );

    CREATE TABLE IF NOT EXISTS analysis_rounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_range TEXT NOT NULL,
        pick_count INTEGER DEFAULT 0,
        technical_common TEXT,
        sector_common TEXT,
        pattern_common TEXT,
        capital_common TEXT,
        overall_summary TEXT,
        predict_date TEXT,
        predict_symbol TEXT,
        predict_name TEXT,
        predict_reason TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        round_id INTEGER NOT NULL,
        predict_symbol TEXT,
        actual_symbol TEXT,
        actual_name TEXT,
        is_hit INTEGER DEFAULT 0,
        feedback TEXT,
        new_rules TEXT,
        verified_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (round_id) REFERENCES analysis_rounds(id)
    );

    CREATE TABLE IF NOT EXISTS learning_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_content TEXT NOT NULL,
        confidence REAL DEFAULT 0.5,
        hit_times INTEGER DEFAULT 0,
        miss_times INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """,
)


def init_db():
    """初始化数据库（使用v2表结构）"""
    # 如果旧表存在，先删掉再建新表
    _ensure_v2_schema()


def _ensure_v2_schema():
    """确保使用v2表结构"""
    os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
    with get_conn(DB_PATH) as conn:
        # 检查是否有新表
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_picks'"
        )
        if not cur.fetchone():
            # 没有新表 → 执行建表
            conn.executescript(_MIGRATIONS_V2[0])


# ─────────── 每日选股 ───────────

def save_picks(picks: List[Dict]) -> int:
    """批量保存每日选股记录
    picks: [{"date": "3.02", "symbol": "300835", "name": "龙磁科技", "price": 97.48}, ...]
    """
    init_db()
    count = 0
    with get_conn(DB_PATH) as conn:
        for p in picks:
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO daily_picks (pick_date, symbol, name, entry_price) VALUES (?,?,?,?)",
                    (p["date"], p["symbol"], p.get("name", ""), p.get("price", 0))
                )
                count += 1
            except Exception:
                pass
    return count


def get_all_picks() -> List[Dict]:
    """获取全部每日选股记录，按日期排序"""
    init_db()
    with get_conn(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT * FROM daily_picks ORDER BY pick_date ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_picks_range(start_date: str = "", end_date: str = "") -> List[Dict]:
    """获取指定日期范围内的选股"""
    init_db()
    with get_conn(DB_PATH) as conn:
        if start_date and end_date:
            rows = conn.execute(
                "SELECT * FROM daily_picks WHERE pick_date >= ? AND pick_date <= ? ORDER BY pick_date ASC",
                (start_date, end_date)
            ).fetchall()
        elif start_date:
            rows = conn.execute(
                "SELECT * FROM daily_picks WHERE pick_date >= ? ORDER BY pick_date ASC",
                (start_date,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM daily_picks ORDER BY pick_date ASC"
            ).fetchall()
        return [dict(r) for r in rows]


def clear_all_picks():
    """清空所有选股记录"""
    init_db()
    with get_conn(DB_PATH) as conn:
        conn.execute("DELETE FROM daily_picks")


# ─────────── 分析轮次 ───────────

def save_round(data_range: str, pick_count: int, analysis: Dict) -> int:
    """保存一次分析轮次"""
    init_db()
    with get_conn(DB_PATH) as conn:
        cur = conn.execute(
            """INSERT INTO analysis_rounds
               (data_range, pick_count, technical_common, sector_common,
                pattern_common, capital_common, overall_summary,
                predict_date, predict_symbol, predict_name, predict_reason)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data_range, pick_count,
                analysis.get("technical_common", ""),
                analysis.get("sector_common", ""),
                analysis.get("pattern_common", ""),
                analysis.get("capital_common", ""),
                analysis.get("overall_summary", ""),
                analysis.get("predict_date", ""),
                analysis.get("predict_symbol", ""),
                analysis.get("predict_name", ""),
                analysis.get("predict_reason", ""),
            )
        )
        return cur.lastrowid


def get_all_rounds() -> List[Dict]:
    """获取所有分析轮次"""
    init_db()
    with get_conn(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT * FROM analysis_rounds ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_latest_round() -> Optional[Dict]:
    """获取最近一次分析"""
    init_db()
    with get_conn(DB_PATH) as conn:
        row = conn.execute(
            "SELECT * FROM analysis_rounds ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


# ─────────── 验证 ───────────

def save_verification(round_id: int, predict_symbol: str,
                      actual_symbol: str, actual_name: str,
                      is_hit: bool, feedback: str, new_rules: List[str]) -> int:
    """保存验证记录"""
    init_db()
    with get_conn(DB_PATH) as conn:
        cur = conn.execute(
            """INSERT INTO verifications
               (round_id, predict_symbol, actual_symbol, actual_name, is_hit, feedback, new_rules)
               VALUES (?,?,?,?,?,?,?)""",
            (round_id, predict_symbol, actual_symbol, actual_name,
             1 if is_hit else 0, feedback,
             json.dumps(new_rules, ensure_ascii=False))
        )
        return cur.lastrowid


def get_verifications() -> List[Dict]:
    """获取所有验证记录"""
    init_db()
    with get_conn(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT * FROM verifications ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ─────────── 学习规则 ───────────

def save_learning_rule(rule_content: str, confidence: float = 0.5) -> int:
    """保存学习规则（带去重：如果已存在相似规则则强化而非新增）"""
    init_db()
    with get_conn(DB_PATH) as conn:
        # 去重：检查是否已有内容高度相似的规则
        existing = conn.execute(
            "SELECT id, rule_content, hit_times FROM learning_rules"
        ).fetchall()

        # 简单相似度：提取关键词比较
        new_keywords = set(rule_content.replace("（", " ").replace("）", " ").split())
        for row in existing:
            old_keywords = set(row["rule_content"].replace("（", " ").replace("）", " ").split())
            # 计算jaccard相似度
            if old_keywords and new_keywords:
                intersection = old_keywords & new_keywords
                union = old_keywords | new_keywords
                similarity = len(intersection) / len(union) if union else 0
                if similarity > 0.5:
                    # 已有相似规则，强化它（hit+1）而非新增
                    conn.execute(
                        "UPDATE learning_rules SET hit_times = hit_times + 1, "
                        "confidence = CAST(hit_times + 1 AS REAL) / (hit_times + miss_times + 1), "
                        "updated_at = ? WHERE id = ?",
                        (datetime.now().isoformat(), row["id"])
                    )
                    return row["id"]

        # 没有相似规则，新增（根据初始置信度设置hit/miss初始值）
        if confidence >= 0.6:
            init_hit, init_miss = 1, 0
        elif confidence <= 0.4:
            init_hit, init_miss = 0, 1
        else:
            init_hit, init_miss = 0, 0
        cur = conn.execute(
            "INSERT INTO learning_rules (rule_content, confidence, hit_times, miss_times) VALUES (?, ?, ?, ?)",
            (rule_content, confidence, init_hit, init_miss)
        )
        return cur.lastrowid


def prune_low_confidence_rules(min_attempts: int = 3, threshold: float = 0.25) -> int:
    """淘汰低置信度规则：验证次数>=min_attempts且置信度<threshold的规则会被删除"""
    init_db()
    with get_conn(DB_PATH) as conn:
        result = conn.execute(
            "DELETE FROM learning_rules WHERE (hit_times + miss_times) >= ? AND confidence < ?",
            (min_attempts, threshold)
        )
        return result.rowcount


def update_learning_rule(rule_id: int, hit: bool):
    """更新规则命中"""
    with get_conn(DB_PATH) as conn:
        if hit:
            conn.execute(
                "UPDATE learning_rules SET hit_times = hit_times + 1, "
                "confidence = CAST(hit_times + 1 AS REAL) / (hit_times + miss_times + 1), "
                "updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), rule_id)
            )
        else:
            conn.execute(
                "UPDATE learning_rules SET miss_times = miss_times + 1, "
                "confidence = CAST(hit_times AS REAL) / (hit_times + miss_times + 1), "
                "updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), rule_id)
            )


def get_learning_rules(min_confidence: float = 0.0) -> List[Dict]:
    """获取学习规则"""
    init_db()
    with get_conn(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT * FROM learning_rules WHERE confidence >= ? ORDER BY confidence DESC",
            (min_confidence,)
        ).fetchall()
        return [dict(r) for r in rows]


# ─────────── 统计 ───────────

def get_stats() -> Dict:
    """获取统计摘要"""
    init_db()
    with get_conn(DB_PATH) as conn:
        pick_count = conn.execute("SELECT COUNT(*) FROM daily_picks").fetchone()[0]
        round_count = conn.execute("SELECT COUNT(*) FROM analysis_rounds").fetchone()[0]
        verify_count = conn.execute("SELECT COUNT(*) FROM verifications").fetchone()[0]
        hit_count = conn.execute("SELECT COUNT(*) FROM verifications WHERE is_hit=1").fetchone()[0]
        rule_count = conn.execute("SELECT COUNT(*) FROM learning_rules").fetchone()[0]
        hit_rate = hit_count / verify_count if verify_count > 0 else 0
        return {
            "pick_count": pick_count,
            "round_count": round_count,
            "verify_count": verify_count,
            "hit_count": hit_count,
            "hit_rate": round(hit_rate, 2),
            "rule_count": rule_count,
        }
