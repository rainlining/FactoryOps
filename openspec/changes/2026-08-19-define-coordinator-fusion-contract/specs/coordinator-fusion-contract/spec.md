# Coordinator Fusion Contract 规格增量

## ADDED Requirements

### Requirement: Fusion 必须绑定同一工作上下文

Fusion 必须绑定一个 Run、Coordinator Execution、round 和唯一的 Specialist Recommendation identities；公开接收边界必须逐项比对源 Recommendation。跨 Run、key 错配、重复角色或重复引用必须拒绝，present/missing roles 必须完整覆盖三个 Specialist 角色。

### Requirement: Fusion 输出必须区分候选与授权

输出必须结构化表达候选动作、连续 rank、冲突摘要和 provenance；rank 1 必须等于 proposed action，`authorization_state` 必须为 `NOT_EVALUATED`，不得声称 Risk approval 或 Business Action 已执行。

### Requirement: Fusion 必须确定性规范化并可分类

相同输入 canonical identical，不同输入 conflicting；整数与等值整数浮点必须规范化，未知字段、ground truth 和模型原文必须拒绝。
