# Coordinator Execution Start 规格增量

## ADDED Requirements

### Requirement: 启动必须原子建立 Run 与 Coordinator Execution

系统必须在同一 MySQL 事务中创建 Coordinator Execution snapshot/revision 0 history，并把 PENDING Run 更新为 RUNNING、revision 1、绑定该 Execution、`agent_execution_count=1`，再写入 Run revision 1 history。

#### Scenario: 启动成功

- **GIVEN** Run 为 PENDING revision 0 且没有 Coordinator Execution
- **WHEN** 收到合法启动命令
- **THEN** 四项持久化事实全部可见且引用同一 Execution

#### Scenario: history 写入失败

- **WHEN** 任一 Execution 或 Run history 写入失败
- **THEN** Run 与 Execution 的全部本次修改回滚

### Requirement: 启动请求必须幂等并可恢复

系统必须以全局唯一 `start_request_id` 标识启动意图。相同 request 和 payload 重放返回 `duplicate-identical`；相同 request 不同 payload 返回 `duplicate-conflicting`，不得产生新事实。

#### Scenario: 提交确认丢失后重试

- **GIVEN** 首次事务已提交但调用方未收到响应
- **WHEN** 使用相同 request 和 payload 重试
- **THEN** 返回原 Run 与 Execution，不增加 revision、history 或计数

### Requirement: 同一 Run 只能由一个启动请求获胜

系统必须锁定 Run 并要求其为 PENDING revision 0、Coordinator 为空且 Execution 计数为 0。并发不同 request 最多一个 `applied`，其他返回 `concurrency-conflict`。

#### Scenario: 两个 Worker 同时启动

- **WHEN** 两个不同 request 并发启动同一 Run
- **THEN** 只创建一个 Coordinator Execution 和一组 history

### Requirement: Coordinator 输入必须冻结且遵守 Contract

启动命令必须提供 `prompt_version`、`context_snapshot_id` 和 evidence refs；其他 provenance 必须从 Run 冻结事实复制，Execution 固定为 coordinator、attempt 1、task null。

#### Scenario: 输入违反 Execution Contract

- **WHEN** Context ID、版本或 evidence refs 非法
- **THEN** 启动在写数据库前被拒绝，Run 保持 PENDING

### Requirement: 非 PENDING Run 不得重新启动

不存在、已 RUNNING、终态、已有 Coordinator 或计数不为 0 的 Run 不得创建新的首个 Coordinator Execution。

#### Scenario: 已启动 Run 收到新 request

- **WHEN** 新 request 尝试启动已 RUNNING 的 Run
- **THEN** 返回 `concurrency-conflict` 且不创建第二个 Execution
