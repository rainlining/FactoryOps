# Design

## 边界与数据流

入口为 `POST /internal/api/v1/approvals/{approvalKey}/execute`，只接受既有 service token，不接受 body target。服务先非锁定读取 Approval 得到候选 incident，再在一个 Java 写事务内按以下顺序处理：

1. 以 hash+原值 `FOR SHARE` 锁定 Quality Incident；
2. `FOR UPDATE` 锁定 Approval，重做 schema/hash/typed/history 完整性校验；
3. 要求 v1.1、revision 2、`APPROVED`、`HOLD_BATCH` 且 incident 未漂移；
4. 读取或创建以 `approval_id` 为唯一键的 action receipt；
5. 从 Incident 取得 batch/inspection/result，调用既有 Batch domain 的 `QUALITY_ANOMALY` hold；
6. 同事务写入 EXECUTED receipt 后提交。

锁序固定为 `Incident → Approval → receipt → Batch`，与 Approval create 的 `Incident → Approval` 前缀一致。Approval row 把同一审批的首次执行串行化；数据库事务保证 Batch 与 receipt 同成同败。

## 幂等与失败

- 已存在且完整一致的 receipt 返回 replay，不重复 hold。
- PENDING/REJECTED、非 HOLD_BATCH、未知/漂移 incident 均 fail closed，零副作用。
- Batch 已被相同 evidence hold 可重放；不同 hold、released/legacy batch 由既有 Batch domain 拒绝，receipt 不落库。
- 不捕获并伪装数据库 deadlock；锁序与并发测试负责证明正常竞争不泄漏异常。

## 测试

真实 MySQL 覆盖成功、相同并发重放、未批准/错误动作、target substitution、receipt/Approval corruption、Batch 冲突与事务 rollback；全量 Java/Agent/Contract 回归。
