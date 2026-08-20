# Execute Approved Batch Hold Design

本设计以 incident-bound APPROVED Approval 为唯一授权事实，按 `Incident → Approval → receipt → Batch` 锁序，在单个 Java/MySQL 事务内执行既有 Batch `QUALITY_ANOMALY` hold。入口无目标参数；V1 仅支持 HOLD_BATCH。
