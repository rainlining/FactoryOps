# Review Handoff：2026-08-13-establish-batch-lifecycle

## 恢复信息

- 学习等级：`deep`
- 分支：`codex/establish-batch-lifecycle`
- Worktree：`C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\establish-batch-lifecycle`
- Base commit：`3bed2fc1c95e406f1bae240342d3a47dfd8ba26b`
- 实现 head：`2d7e6a0`（本 handoff 文档另有后续提交）
- 恢复命令：`git -C "C:\Users\小霖\Desktop\work\project2\FactoryOps\.worktrees\establish-batch-lifecycle" status`
- 禁止实现会话与 Review 会话并发修改此 worktree。

## 已实现范围

- Batch 不可变身份及 `OPEN → HELD → RELEASED` 单向状态机。
- Batch 创建、查询、HOLD HTTP API；RELEASE 仅为 Java 内部应用服务。
- HOLD 原因快照、命令 replay/conflict 和 QUALITY_ANOMALY 精确证据校验。
- V3 MySQL Schema、历史 Inspection 占位 Batch 回填、CHECK/FK/索引。
- Inspection 强制不可变 `batch_id`，创建时锁父 Batch；RELEASED 后旧请求仍可 replay，新 Inspection 被拒绝。
- 并发创建、并发 HOLD、迁移及事务负向测试。

非目标：Quality Incident、Approval、Audit、Kafka/Outbox、Redis、Agent Tool、Release HTTP、权限和列表分页。

## 建议阅读顺序与真实调用链

1. `BatchController#create/hold/get`：HTTP 入口、响应与稳定错误码。
2. `BatchApplicationService#create/hold/release`：读写事务、行锁、证据验证、幂等分类。
3. `Batch#hold/release`、`HoldCommand`、`ReleaseCommand`：状态机与命令不变量。
4. `BatchJdbcRepository#findForUpdate/holdOpen/releaseHeld`：父行锁和带状态条件的 SQL。
5. `InspectionApplicationService#create` 与 `InspectionJdbcRepository`：先判旧请求 replay，再锁父 Batch 处理新请求。
6. `V3__create_batches_and_assign_inspections.sql`：Schema、占位 Batch、历史回填与外键。
7. `BatchLifecycleHttpIT`、`BatchMigrationIT`：成功、失败和并发证据。

成功 HOLD：Controller → Application 写事务 → `findForUpdate` →（异常原因时）Inspection/Result 证据关系校验 → Domain `hold` → `UPDATE ... WHERE status='OPEN'` → 查询并响应。

失败路径：证据不存在/关系错误/非异常会在更新前抛错并回滚；不同 HOLD 命令对 HELD Batch 返回 conflict；RELEASED Batch 拒绝状态迁移。

## 验证证据与限制

- `mvn verify`：Java 38 项通过，其中单元 14、MySQL 集成 24。
- Python Vision Contract：17 项通过。
- `git diff --check`：通过。
- Docker/MySQL 已真实运行；没有 Docker 阻断。
- 仍待 Review 会话完成 owner 修改、故障实验、真实 Walkthrough 和最终 diff 接受；因此不得合并 main 或归档。

## Learning Gate 任务

所有者修改：为 Batch 查询响应增加 `inspection_count`，在只读事务中由 Result/Inspection 边界提供计数，覆盖 0、1、2；不得改写事务、状态机和锁。

Failure/debug exercise：临时从 HOLD SQL 删除 `AND status='OPEN'`，运行并发不同 HOLD 测试，观察首次原因/时间被覆盖或两个调用误判成功；随后恢复条件并重新运行测试。详细步骤见 `learning.md`。
