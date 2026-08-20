# 技术选型

- 使用 SQLAlchemy `Engine` 与现有 Agent MySQL schema，避免引入新的 Web 框架和第二套数据访问层。
- 首版公开 Python service API；HTTP adapter/dashboard 留给后续 Change。
- 以 Run 为查询边界，关联事实必须满足相同 `run_id`，从而防止展示跨 Run 污染。
