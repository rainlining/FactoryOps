# Learning

- `learning_level`: `deep`
- Walkthrough：internal execute endpoint → approval/incident fencing → Batch domain → receipt commit/replay。
- Owner 小修改：新增一个 receipt reason code 投影并补 corruption test。
- Failure exercise：在 Batch update 后注入 receipt insert failure，确认事务回滚后 Batch 仍 OPEN。
- Learning Gate 延后至 demo milestone；此前不归档、不合并 main。
