# Learning

- `learning_level`: `standard`
- 状态：Owner Review/Learning 延后至 demo milestone。

Walkthrough：`ApprovedWorkflowCompletionService.complete` → resume saga → provenance/readiness locks → Coordinator result/history → Run result/history → replay validation。

Owner 修改任务：为 completion reason message 增加一个不含敏感信息的稳定 display code，并补断言。

故障实验：在 Coordinator update 后、Run update 前注入异常，确认两个 current snapshot 与两条 completion history 均未提交；移除注入后相同请求恢复成功。
