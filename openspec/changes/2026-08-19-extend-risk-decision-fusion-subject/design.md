# 设计：Fusion Subject Binding

Risk Decision v1.1 的 identity 使用互斥 subject：`subject_type=RECOMMENDATION` 时保持 v1.0 的 recommendation 字段；`subject_type=FUSION` 时使用 fusion_id、fusion_key、run_id、coordinator_execution_id、round。公开 validator 接收对应 source identity 并逐字段比对，禁止跨 subject 混用。

Decision key 按 subject key 派生：Recommendation 仍为 `RDK-SHA256("v1\n<recommendation_key>")`；Fusion 使用 `RDK-SHA256("v1\n<fusion_key>")`。Canonical 与 relation 仍按 decision key 分类。

本 Change 只冻结 Contract；持久化层如何存储 Fusion FK/typed columns 留给后续独立 Change。
