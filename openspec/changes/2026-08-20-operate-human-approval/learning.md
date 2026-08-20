# Learning

- `learning_level`: `deep`
- Walkthrough：HTTP → schema/semantic validator → server-side authorizer → application transaction → row lock → current/history。
- Owner 小修改：为决定 API 增加一个不改变权限的可选审计 reference，并补 replay 测试。
- Failure exercise：并发提交 APPROVED/REJECTED，观察一个成功、一个 409，数据库只有两条 revision。
- Learning Gate：延后至 demo milestone；此前不得归档或合并 main。
