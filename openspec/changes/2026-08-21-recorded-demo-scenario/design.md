# Design

`frontend/demo_scenario.json` 保存场景元数据和脱敏结论；`demo_server.py` 增加 `/api/scenario` 与白名单 `/api/inspection-image`。图片端点只允许固定文件名 `000_regular.png`，不接受用户路径。Dashboard 在 Run summary 下显示原图、Inspection finding、Affected batch 和 recommended action，明确标注 `recorded demo`。
