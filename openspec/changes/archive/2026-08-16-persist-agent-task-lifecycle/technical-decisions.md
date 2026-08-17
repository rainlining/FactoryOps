# 技术选型：Agent Task 生命周期持久化

## 决策摘要

| 主题 | 选择 | 理由 |
|---|---|---|
| 数据库 | 现有 MySQL 8.4 + SQLAlchemy Core | 延续 Agent Service 技术栈和真实事务测试 |
| 模型 | snapshot + append-only history | 快速恢复当前状态，同时保留审计事实 |
| 幂等 | 数据库唯一键 + 冲突后重读分类 | 支持 at-least-once 和并发竞态 |
| 并发 | status/revision 条件 UPDATE | 不持有长事务或分布式锁 |
| 依赖 | junction table + Task FK | 支持存在性、同 Run 校验和查询 |
| Evidence | MySQL JSON 数组 | 当前只是有序外部引用，无本地 FK 目标 |
| Contract | 写前候选验证 + 读后重建验证 | 数据库约束与跨字段语义双层防线 |

## Execution 引用

`created_by_execution_id`、`current_execution_id`、successful/failed execution ID 暂存为严格格式的逻辑引用。当前 stacked base 只有 Execution Contract，没有 Execution 数据表；提前建占位表会错误确定所有权和 migration 顺序。后续 Execution persistence Change 应新增同库 FK，并为已有数据定义上线前完整性检查。

## 依赖并发

创建事务使用父 Run 和依赖 Task 的一致读取并校验 `run_id`。表均为 InnoDB，依赖 Task 不允许删除（FK `ON DELETE RESTRICT`）。本阶段没有 Task 删除能力，因此校验后引用不会消失。

## JSON 边界

只将 `evidence_refs` 存为 JSON；Service 解码后必须得到字符串数组并再次通过 Contract Validator。assignment、lifecycle、attempt 和 failure 等参与查询/约束的字段均使用结构化列。

## 时间

Service clock 生成 UTC aware datetime，写入 `TIMESTAMP(6)`；读取时统一补回 UTC 并输出最多六位微秒的 `Z` 格式。候选 Contract 验证阻止时钟回退提交。
