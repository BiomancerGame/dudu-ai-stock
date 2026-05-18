"""统一配置(pydantic-settings)。

向后兼容: 旧的 ``config.py`` 仍可用,本模块提供更结构化的访问入口。
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DeepSeekConfig(BaseSettings):
    api_key: str = Field("", alias="DEEPSEEK_API_KEY")
    base_url: str = Field("https://api.deepseek.com/v1", alias="DEEPSEEK_BASE_URL")
    default_model: str = Field("deepseek-chat", alias="DEFAULT_MODEL_NAME")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)


class TushareConfig(BaseSettings):
    token: str = Field("", alias="TUSHARE_TOKEN")
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)


class MiniQMTConfig(BaseSettings):
    enabled: bool = Field(False, alias="MINIQMT_ENABLED")
    account_id: str = Field("", alias="MINIQMT_ACCOUNT_ID")
    host: str = Field("127.0.0.1", alias="MINIQMT_HOST")
    port: int = Field(58610, alias="MINIQMT_PORT")
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)


class TDXConfig(BaseSettings):
    enabled: bool = Field(False, alias="TDX_ENABLED")
    base_url: str = Field("http://127.0.0.1:5000", alias="TDX_BASE_URL")
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)


class Settings:
    """聚合配置入口。延迟实例化避免循环导入。"""

    def __init__(self) -> None:
        self.deepseek = DeepSeekConfig()
        self.tushare = TushareConfig()
        self.miniqmt = MiniQMTConfig()
        self.tdx = TDXConfig()


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
