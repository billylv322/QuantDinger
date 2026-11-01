# 分叉立项：中国期货行情接入

本仓库是 billylv322 对 OpenByteInc/QuantDinger 的分叉。分叉目的只有一个：给平台增加中国期货行情能力，供 AI 投研、K 线图表与回测使用国内品种数据。仅行情与研究，不涉及国内期货交易通道（平台无 CTP，下单仍走天勤与自有量化栈）。

## v1 最小验证版（已完成，分支 feature/cn-futures）

- 新增数据源模块 `backend_api_python/app/data_sources/cn_futures.py`，数据经 AkShare 取新浪期货行情，覆盖上期所、大商所、郑商所、上期能源、中金所。
- 品种代码规范：主力连续 `<品种>0`（如 OI0 菜油、P0 棕榈油、NI0 沪镍、AG0 沪银、SC0 原油）；具体合约 `<品种><YYMM>`（如 P2701）；郑商所三位写法（OI701）自动规范为四位。
- 周期：1D 与 1W 全部支持；1m、5m、15m、30m、1H、4H 仅具体合约。限制：新浪分钟线单次上限 1023 根，主力连续没有分钟线。
- `FuturesDataSource` 在美国期货与加密路由之前分流国内代码；美国品种行为无变化（GC 已验仍走原通道）。
- 测试：`backend_api_python/tests/test_cn_futures.py`，覆盖代码规范、识别与误报排除，无网络依赖。

## 部署状态（2026-11-01）

- 已部署到本机实例（Billy，E:\QuantDinger）：模块文件放在 `custom/` 目录，经 `docker-compose.override.yml` 挂载进 backend 与各 worker 容器，官方 compose 文件未改动。
- 验活证据（容器内经 DataSourceFactory 真实调用路径）：OI0 日线收盘 10340，P2701 的 15 分钟线正常，AG0 报价 12093，与本地数据逐项一致；全栈 healthy。
- 本机实例的 AI 模型已配置为 DeepSeek（deepseek-chat）。

## 已知限制

- 数据为新浪公开行情（经 AkShare），非交易所直连，实时性按公开源看待。
- 分钟线只有近期约 1023 根，不适合长周期分钟级回测。
- 品种目录未播种国内品种，研究页需要手动输入代码。

## v2 候选（未排期）

- 天勤 TqSdk 以边车形式提供实时行情与更深历史，模块改为优先天勤、回退新浪。
- 国内品种播种进品种目录，支持搜索与自选。
- 用国内数据在回测引擎跑通一条策略，做端到端验证。

## 维护说明

- 上游更新频繁。同步上游时重点复核两处：`futures.py` 的国内分流点、`docker-compose.override.yml` 的挂载路径是否仍对齐。
- 凭据与 .env 不入库。
- 本仓库 Issues 未启用（GitHub 分叉默认关闭），项目跟踪以本文件为准；如需启用，在仓库 Settings 的 Features 里勾选 Issues。
