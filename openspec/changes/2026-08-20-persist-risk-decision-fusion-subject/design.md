# 设计：Risk Decision 双 Subject 持久化

主表保留已有 Recommendation typed columns，并新增 nullable Fusion typed columns 与 `subject_type`。Migration 约束保证 Recommendation/Fusion 字段互斥；应用层根据 subject type 锁定并解码 Specialist Recommendation 或 Coordinator Fusion，随后调用 v1.0/v1.1 validator。key/ID advisory locks、existing replay、单事务 insert 和 IntegrityError recovery 保持不变。

读取必须验证 payload canonical/hash、subject typed columns、源 Recommendation/Fusion payload 与 run/provenance 绑定。历史事实 replay 不要求父 Execution 仍 RUNNING。
