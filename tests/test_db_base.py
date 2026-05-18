"""db.base 与 database 的基础冒烟测试。"""
from __future__ import annotations

import os

import pytest

from db.base import execute, fetch_all, get_conn, run_migrations


def test_get_conn_creates_file(tmp_path):
    p = tmp_path / "x.db"
    with get_conn(str(p)) as conn:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO t (name) VALUES (?)", ("alice",))
    assert os.path.exists(p)
    rows = fetch_all(str(p), "SELECT name FROM t")
    assert [r["name"] for r in rows] == ["alice"]


def test_run_migrations_idempotent(tmp_path):
    p = tmp_path / "m.db"
    migrations = (
        "CREATE TABLE a (id INTEGER PRIMARY KEY);",
        "CREATE TABLE b (id INTEGER PRIMARY KEY);",
    )
    run_migrations(str(p), migrations)
    run_migrations(str(p), migrations)  # 再跑一次不应出错
    rows = fetch_all(str(p), "SELECT version FROM schema_version ORDER BY version")
    assert [r["version"] for r in rows] == [0, 1]


def test_database_save_and_get(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from database import StockAnalysisDatabase

    db = StockAnalysisDatabase(db_path=str(tmp_path / "test_analysis.db"))
    rid = db.save_analysis(
        symbol="000001",
        stock_name="测试",
        period="1y",
        stock_info={"k": "v"},
        agents_results={"a": 1},
        discussion_result={"d": 2},
        final_decision={"rating": "买入"},
    )
    assert rid > 0
    assert db.get_record_count() == 1
    rec = db.get_record_by_id(rid)
    assert rec is not None
    assert rec["symbol"] == "000001"
    assert rec["final_decision"]["rating"] == "买入"
    assert db.delete_record(rid) is True
    assert db.get_record_count() == 0
