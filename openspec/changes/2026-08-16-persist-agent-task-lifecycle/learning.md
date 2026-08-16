# Change 学习计划：2026-08-16-persist-agent-task-lifecycle

- `learning_level`: `standard`
- `pattern_stage`: `then-standard`
- `first_deep_reference`: `2026-08-15-persist-agent-run-lifecycle`
- `gate_status`: `not-started`

## 学习目标

- 能说明 Task snapshot、dependencies 和 history 的事务边界。
- 能沿创建与 transition 调用链定位幂等分类、Contract 校验和乐观锁。
- 能区分 request 重投冲突与 stale revision 并发冲突。
- 能解释为何 Execution 引用当前没有数据库 FK。

## Walkthrough 要求

- 从 Service 创建入口走到 Contract Validator、Repository 事务和三张表。
- 从 transition 入口走到纯规则、候选 Contract、条件 UPDATE 和 history INSERT。
- 用测试定位依赖跨 Run、并发赢家、history 注入失败和时钟回退。

## Owner 修改

standard Change 不要求强制亲自修改。Review 时可选调整一个非安全关键的 Task priority 测试边界，并运行局部测试。

## Failure/Debug Exercise

standard Change 不设置强制 Deep exercise。Review 应实际运行重复 transition 或 stale revision 测试，观察 identical/conflicting/concurrency-conflict 的区别。

## Learning Gate

- [ ] 解释边界、事务和主要取舍。
- [ ] 定位一条成功链和一条失败链。
- [ ] review 最终 diff 和真实验证证据。
- [ ] 明确接受 Change。

实现会话停在 `review-handoff-ready`；不得因与另外两个 Change 合并 review 而跳过本 Change 的独立 Gate。
