# Learning

- `learning_level`: `standard`
- 理解待审批事实与实际业务副作用的区别。
- 能沿 `WAITING_FOR_APPROVAL → API → SQLite transaction → queue status/history` 定位调用链。
- Review 时核对幂等、冲突拒绝、复检派生 Run 与“不伪称停线”。
- Learning Gate 按项目所有者当前节奏后置，本 Change 先停在 review-handoff-ready。
