# Design

`scripts/start_factoryops_demo.ps1` 从仓库根目录定位前端，启动 `frontend/demo_server.py` 并在终端输出 URL。`frontend/demo_server.py` 已提供 snapshot、scenario、inspection image 和静态页面；本 Change 只增加启动/说明层，不复制数据或改变运行时语义。

演示验收以“命令启动 → HTTP 200 → 页面显示 recorded inspection → API 只读 405”为主链路。
