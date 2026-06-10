"""Optional integration checks for a local TDX API service.

These tests are skipped by default because they require an external service.
Run them with RUN_TDX_INTEGRATION_TESTS=1 after starting the TDX API.
"""
from __future__ import annotations

import os

import pandas as pd
import pytest
import requests


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_TDX_INTEGRATION_TESTS") != "1",
    reason="set RUN_TDX_INTEGRATION_TESTS=1 and start TDX API to run",
)

TDX_API_URL = os.getenv("TDX_BASE_URL", "http://127.0.0.1:5000").rstrip("/")


def test_tdx_api_health():
    response = requests.get(f"{TDX_API_URL}/api/health", timeout=5)
    assert response.status_code == 200


def test_tdx_api_kline_and_ma_calculation():
    kline_list = None
    for code in ("SZ000001", "000001", "SH600000", "600000"):
        response = requests.get(
            f"{TDX_API_URL}/api/kline",
            params={"code": code, "type": "day"},
            timeout=10,
        )
        if response.status_code != 200:
            continue

        payload = response.json()
        if isinstance(payload, dict) and payload.get("code") == 0:
            kline_list = payload.get("data", {}).get("List", [])
        elif isinstance(payload, list):
            kline_list = payload

        if kline_list:
            break

    assert kline_list, "TDX API returned no kline data for sample stocks"

    df = pd.DataFrame(kline_list)
    if "Close" in df.columns and "close" not in df.columns:
        df["close"] = df["Close"]

    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["MA5"] = df["close"].rolling(window=5).mean()
    df["MA20"] = df["close"].rolling(window=20).mean()

    latest = df.iloc[-1]
    assert pd.notna(latest["MA5"])
    assert pd.notna(latest["MA20"])
