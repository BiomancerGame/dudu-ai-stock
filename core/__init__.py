"""核心基础设施层。

模块组织约定:
- core.logging_setup: 全局日志初始化
- core.settings: 统一配置(基于 pydantic-settings,向后兼容旧 config.py)
- core.errors: 统一异常类型
- core.cache: 磁盘 + 内存缓存
"""
