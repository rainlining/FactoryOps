# Change 任务：2026-08-14-persist-quality-incident-outbox

## 设计与学习预检

- [x] 完成事务一致性、数据模型、重放、迁移和失败路径讨论。
- [ ] 项目所有者 review 书面 OpenSpec 设计。
- [ ] 完成 Deep Change 编码前讲解与 learning preflight。

## 实现

- [ ] 以失败测试冻结 Event Factory 输出和 Java→Schema Contract。
- [ ] 新增 Outbox migration、历史回填和数据库约束测试。
- [ ] 新增 Outbox Domain/Repository 与精确内容核对。
- [ ] 将 Incident 创建和 Outbox INSERT 接入同一事务。
- [ ] 覆盖顺序 replay、并发 replay、缺失/冲突和完整回滚。
- [ ] 执行格式化、完整验证、diff 与 dataset scope 检查。

## Handoff

- [ ] 填写 verification 与 review-handoff，推送并停在 review-handoff-ready。
- [ ] 独立 Review/Learning 会话完成 owner 修改、故障实验与 Deep Learning Gate。
