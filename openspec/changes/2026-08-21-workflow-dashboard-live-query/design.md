# Design

`frontend/demo_server.py` 使用 Python 标准库提供静态文件和 `/api/snapshot`，默认读取同目录 `demo_snapshot.json`。浏览器启动时先请求 API，成功后渲染；失败时显示可理解的错误并保留内置 fallback，用户仍可通过文件选择器替换数据。API 只响应 GET，其他方法返回 405。
