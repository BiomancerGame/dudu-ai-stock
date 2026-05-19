# 文档导航

本目录保留核心文档,其余 66 篇历史文档已归档到 `archive/` 子目录(未删除,可随时查阅)。

## 核心文档

| 文档 | 用途 |
|---|---|
| [README.md](./README.md) | 项目总览(中文) |
| [QUICK_START.md](./QUICK_START.md) | 快速开始 |
| [AGENTS.md](./AGENTS.md) | AI 智能体说明 |
| [UNIFIED_ANALYSIS_SPEC.md](./UNIFIED_ANALYSIS_SPEC.md) | 统一分析规范 |
| [DOCKER_README.md](./DOCKER_README.md) | Docker 部署概览 |
| [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md) | Docker 详细部署 |
| [UPDATE_LOG.md](./UPDATE_LOG.md) | 更新日志 |

## 架构与重构

本次 P0-P6 重构后新增的基础设施:

- **核心层** `core/`:`logging_setup`、`settings`、`errors`、`cache`、`concurrent`
- **数据访问** `db/base.py`:统一 SQLite 连接、WAL、迁移
- **UI 组件** `ui/`:`menu`、`styles` (CSS 已外置到 `styles.css`)
- **Prompt 模板** `prompts/*.md`:技术/基本/资金/讨论/决策 5 个外置 prompt
- **测试** `tests/`:14 个 pytest 用例
- **CI** `.github/workflows/ci.yml`

## 归档目录

`archive/` 含 66 篇按主题分类的历史文档(主力选股 / 龙虎榜 / 新闻流量 / 智策板块 / 智能盯盘 / 低价擒牛 / Webhook / TDX / Tushare / MiniQMT 等),命名保留原始中文标题。需要哪一项功能详细说明时直接到 `archive/` 检索。
