"""向后兼容配置层 — 所有值统一来自 core.settings（pydantic-settings）。

下游代码仍可 ``import config; config.DEEPSEEK_API_KEY`` 使用，
但真正的配置解析、env 文件读取、类型校验由 ``core.settings`` 负责。
"""
from dotenv import load_dotenv

# 确保 .env 被加载（pydantic-settings 也会读，但 load_dotenv 优先保证覆盖）
load_dotenv(override=True)

from core.settings import get_settings as _get_settings

_s = _get_settings()

# DeepSeek API配置
DEEPSEEK_API_KEY: str = _s.deepseek.api_key
DEEPSEEK_BASE_URL: str = _s.deepseek.base_url

# 默认AI模型名称（支持任何OpenAI兼容的模型）
DEFAULT_MODEL_NAME: str = _s.deepseek.default_model

# 其他配置
TUSHARE_TOKEN: str = _s.tushare.token

# 股票数据源配置
DEFAULT_PERIOD = "1y"  # 默认获取1年数据
DEFAULT_INTERVAL = "1d"  # 默认日线数据

# MiniQMT量化交易配置
MINIQMT_CONFIG = {
    'enabled': _s.miniqmt.enabled,
    'account_id': _s.miniqmt.account_id,
    'host': _s.miniqmt.host,
    'port': _s.miniqmt.port,
}

# TDX股票数据API配置项目地址github.com/oficcejo/tdx-api
TDX_CONFIG = {
    'enabled': _s.tdx.enabled,
    'base_url': _s.tdx.base_url,
}