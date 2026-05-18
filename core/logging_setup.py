"""统一日志初始化。

用法:
    from core.logging_setup import get_logger
    logger = get_logger(__name__)
    logger.info("hello")

特性:
- 控制台 + 文件 (logs/app.log) 双输出
- RotatingFileHandler 防止日志膨胀
- 仅初始化一次 (幂等)
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_INITIALIZED = False
_LOG_DIR = "logs"
_LOG_FILE = os.path.join(_LOG_DIR, "app.log")


def _init_root_logger(level: int = logging.INFO) -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return

    os.makedirs(_LOG_DIR, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # 清空已存在的 handler 防止重复输出
    for h in list(root.handlers):
        root.removeHandler(h)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.setLevel(level)
    root.addHandler(console)

    file_h = RotatingFileHandler(
        _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_h.setFormatter(fmt)
    file_h.setLevel(level)
    root.addHandler(file_h)

    # 抑制第三方库的过度日志
    for noisy in ("urllib3", "openai", "httpx", "akshare", "yfinance"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _INITIALIZED = True


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """获取一个已配置好的 logger。"""
    _init_root_logger(level)
    return logging.getLogger(name)
