# Change 任务：2026-08-14-persist-quality-incident-outbox

## 设计与学习预检

- [x] 完成事务一致性、数据模型、重放、迁移和失败路径讨论。
- [x] 项目所有者 review 并接受书面 OpenSpec 设计。
- [x] 完成 Deep Change 编码前讲解；理解讨论与最终 Learning Gate 转交独立 Review/Learning 会话。

## 实现

- [x] 以失败测试冻结 Event Factory 输出和 Java→Schema Contract。
- [x] 新增 Outbox migration、历史回填和数据库约束测试。
- [x] 新增 Outbox Domain/Repository 与精确内容核对。
- [x] 将 Incident 创建和 Outbox INSERT 接入同一事务。
- [x] 覆盖顺序 replay、并发 replay、缺失、冲突和完整回滚。
- [x] 执行格式化、完整验证、diff 与 dataset scope 检查。

## Handoff

- [x] verification 与 review-handoff 已填写；远端推送仍待网络恢复，本地 Review/Learning 已完成。
- [x] 独立 Review/Learning 会话完成 owner 修改、故障实验与 Deep Learning Gate。
