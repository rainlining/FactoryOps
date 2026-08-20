# Risk Decision Fusion Subject 规格增量

### Requirement: Risk Decision 必须明确且互斥地绑定 Subject

v1.1 Risk Decision 必须声明 `subject_type`。Recommendation subject 必须逐字段绑定 Recommendation；Fusion subject 必须逐字段绑定 Fusion 的 id/key/run/coordinator execution/round。跨 subject、缺失字段或错配必须拒绝。

### Requirement: Fusion Risk Decision 必须保留 Coordinator Provenance

Fusion subject 不得退化为只保存 opaque key；必须保留 run、Coordinator Execution 和 round，且 decision key 必须由 Fusion key 确定性派生。
