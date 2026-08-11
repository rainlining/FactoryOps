# Change 学习计划：<change-id>

## 学习元数据

- `learning_level`: `deep | standard | delegated`
- `pattern_stage`: `first-deep | repeated-standard | repeated-delegated | N/A`
- `first_deep_reference`: `N/A | <change-id>`

## 完成后应具备的能力

使用“能够解释、定位、修改、调试”的行为描述，不使用“熟悉某框架 API”作为主要目标。

## 编码前讲解清单

- [ ] 业务问题与工程问题
- [ ] 组件边界与所有权
- [ ] 数据流和状态迁移
- [ ] 事务、并发和关键不变量
- [ ] 失败、重试、幂等和恢复路径
- [ ] 测试与可观测性策略
- [ ] 替代方案与取舍

Standard 或 Delegated Change 可以标注不适用项及原因。

## 真实 Code Walkthrough 路线

实现后填写真实文件和符号：

1. 入口：
2. 编排：
3. 领域或核心规则：
4. 持久化、Event、Agent 或 Tool 边界：
5. 失败与恢复：
6. 对应测试：

## 项目所有者亲自修改任务

- 任务：
- 为什么需要理解而不是机械修改：
- 验收方法：
- 安全边界：

## Failure/Debug Exercise

- 注入故障：
- 操作步骤：
- 预期行为：
- 观察证据：
- 常见错误行为：
- 清理/复位：
- 完成后应能回答：

## Learning Gate

- [ ] 能解释真实设计和关键取舍。
- [ ] 能沿成功调用链定位核心代码。
- [ ] 能定位并解释至少一条失败路径。
- [ ] 已亲自完成约定的小修改。
- [ ] 已完成故障实验并根据证据判断结果。
- [ ] 能指出事务、幂等、权限或恢复逻辑的实际执行位置；不适用时能解释原因。
- [ ] 已 review 最终 diff 并明确接受。

`gate_status`: `not-started | in-progress | passed | N/A`
