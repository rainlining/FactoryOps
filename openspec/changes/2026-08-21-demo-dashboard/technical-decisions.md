# 技术选型

- 采用 Python 标准库 `html` 转义和字符串模板，不引入前端构建链。
- 选择静态生成而不是新建 HTTP server，保持 Change 只解决展示边界；后续若需要 live dashboard，可在此输出之上增加 adapter。
- 状态颜色只作为辅助信息，所有状态同时以文本呈现。
