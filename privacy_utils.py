import json
import os
from typing import Any

import pandas as pd


PRIVACY_CONFIG_PATH = os.path.join(".streamlit", "privacy_config.json")

DEFAULT_PRIVACY_CONFIG = {
    "mask_stock_identity": False,
}


def load_privacy_config() -> dict:
    config = DEFAULT_PRIVACY_CONFIG.copy()
    try:
        if os.path.exists(PRIVACY_CONFIG_PATH):
            with open(PRIVACY_CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            config.update({key: bool(saved.get(key, config[key])) for key in config})
    except Exception:
        pass
    return config


def save_privacy_config(config: dict) -> None:
    os.makedirs(os.path.dirname(PRIVACY_CONFIG_PATH), exist_ok=True)
    normalized = DEFAULT_PRIVACY_CONFIG.copy()
    normalized.update({key: bool(config.get(key, normalized[key])) for key in normalized})
    with open(PRIVACY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)


def is_mask_stock_identity_enabled() -> bool:
    return bool(load_privacy_config().get("mask_stock_identity", False))


def mask_stock_code(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if not text or text == "N/A":
        return text

    suffix = ""
    base = text
    if "." in text:
        base, suffix = text.split(".", 1)
        suffix = f".{suffix}"

    if len(base) <= 2:
        return "*" * len(base) + suffix
    if len(base) <= 4:
        return f"{base[0]}{'*' * (len(base) - 1)}{suffix}"
    return f"{base[:2]}{'*' * (len(base) - 4)}{base[-2:]}{suffix}"


def mask_stock_name(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if not text or text == "N/A":
        return text
    if len(text) <= 1:
        return "*"
    if len(text) == 2:
        return f"{text[0]}*"
    return f"{text[0]}{'*' * (len(text) - 2)}{text[-1]}"


def mask_stock_identity(code: Any = None, name: Any = None) -> tuple[str, str]:
    if not is_mask_stock_identity_enabled():
        return str(code or ""), str(name or "")
    return mask_stock_code(code), mask_stock_name(name)


def mask_dataframe_stock_identity(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or not is_mask_stock_identity_enabled():
        return df

    masked = df.copy()
    for col in masked.columns:
        col_text = str(col).lower()
        if any(token in col_text for token in ["股票代码", "证券代码", "symbol"]):
            masked[col] = masked[col].map(mask_stock_code)
        elif any(token in col_text for token in ["股票简称", "股票名称", "证券简称", "stock_name", "name"]):
            masked[col] = masked[col].map(mask_stock_name)
    return masked
