"""统一异常类型。"""
from __future__ import annotations


class AppError(Exception):
    """项目所有自定义异常的基类。"""


class ConfigError(AppError):
    """配置缺失或非法。"""


class DeepSeekAPIError(AppError):
    """DeepSeek/OpenAI 兼容接口调用失败。"""

    def __init__(self, message: str, *, model: str | None = None, retriable: bool = True) -> None:
        super().__init__(message)
        self.model = model
        self.retriable = retriable


class DataSourceError(AppError):
    """股票数据源调用失败。"""


class DatabaseError(AppError):
    """数据库访问失败。"""
