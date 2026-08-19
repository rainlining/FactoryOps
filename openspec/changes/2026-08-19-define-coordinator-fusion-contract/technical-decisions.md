# 技术选型

- Fusion 是确定性聚合 Contract，不是 LLM 自由文本总结。
- Recommendation 通过 stable key 引用，禁止把完整模型原文嵌入 Fusion。
- 候选动作使用显式连续 rank，不在 Contract 中发明跨领域评分算法；排名不等于授权。
- 同一 Run 与 Coordinator Execution 是聚合边界；Coordinator 按现有 Contract 没有 Task，不能虚构 task_id。
- Fusion 先于 Risk。现有 Risk v1 subject 不兼容 Fusion，留给后续独立 Contract Change，不在本 Change 中倒置架构顺序。
