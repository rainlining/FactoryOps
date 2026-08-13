# Change 验证记录：2026-08-13-establish-inspection-lifecycle

- `status`: `technically-verified`
- `verified_at`: `2026-08-13`
- `verified_by`: `Codex`

## 实际验证

- `mvn -q verify`：退出码 0；Java 17 + MySQL 8.4 Testcontainers 完整构建通过。
- `mvn -q "-Dit.test=InspectionLifecycleHttpIT,InspectionResultHttpIT" verify`：退出码 0；13 个 HTTP/MySQL 场景通过，包含创建竞争、不同 Result 并发、插入故障事务回滚。
- `mvn -q "-Dit.test=InspectionMigrationIT" verify`：退出码 0；一致历史成功回填，冲突历史按预期使 V2 外键步骤失败。
- 最终 `mvn -q verify`：退出码 0；Surefire/Failsafe XML 合计 35 个测试，0 failure、0 error、0 skipped。
- `python -m unittest discover -s contracts/vision_inspection/tests -t .`：退出码 0；17 个 Vision Contract 回归测试通过。
- `git diff --check`：退出码 0；`git diff --name-only 2caf1c9..HEAD | Select-String '^dataset/'` 无输出，未混入 dataset。
- Review 后 `result_count` 修改：`mvn -q -DskipTests package` 退出码 0；`mvn -q -Dtest='*Test' -DfailIfNoTests=false test` 退出码 0；`git diff --check` 退出码 0。
- Review 后 HTTP/MySQL 集成测试：未执行。`docker info` 明确失败，Docker Desktop Linux Engine pipe 不存在；因此不声称新增的 0/1/2 `result_count` HTTP 断言已在本轮运行。

## 已验证不变量

- 同一 Inspection 身份并发创建只有一行，相同输入一方为 replay。
- Result 必须引用存在且图片 URI/SHA 精确匹配的 Inspection。
- 父行条件完成和子 Result 插入属于同一事务；注入子表 CHECK 失败后 Inspection 保持 PENDING、结果表保持空。
- 不同 Result 并发均可保存，`completed_at` 只写入一次。
- V2 不会静默挑选互相冲突的历史图片身份。

## 限制与验收状态

- 未实现取消、重开、权威 Result、Kafka/Outbox、权限或自动数据库重试。
- 技术验收：`passed`
- Code Walkthrough：`passed（项目所有者确认）`
- Owner 修改：`accepted with variance（功能与测试由 Review 会话代写，项目所有者完成语义和 diff review）`
- Failure exercise：`accepted with variance（完成注入与 SQL 复位；Docker 阻断，未观察数据库时间覆盖）`
- 最终 Diff Review：`passed（项目所有者明确接受）`
- Learning Gate：`passed by explicit owner acceptance with documented variance`
- Change 最终状态：`archived（2026-08-13）`
