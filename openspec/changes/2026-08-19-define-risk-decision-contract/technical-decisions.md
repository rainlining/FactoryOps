# 技术选型

- Risk 独立于 Recommendation：专业建议可以被 Block，不能把建议本身当授权。
- Contract payload 无法仅靠自身证明跨对象 provenance；接收入口必须显式提供源 Recommendation identity，不能把格式合法误当成 binding 合法。
- `STOP_LINE` 强制 `REQUIRE_APPROVAL`，防止 LLM 输出绕过高风险审批。
- 允许动作数组必须是 V1 正式动作子集；不允许任意字符串扩展动作空间。
- `allowed_actions` 表示当前即可执行的动作，不包含被 Block 或仍待审批的 proposed action；批准后的授权转换留给后续 Approval/Execution Change。
- 不保存模型原文；诊断详情用 Artifact ref 留给后续边界。
- Canonical 与上游 Recommendation Contract 一致，将 `1.0` 等整数浮点规范化为 `1`。
