# Design

前端是 `frontend/dashboard.html`、`frontend/dashboard.css`、`frontend/dashboard.js` 三个静态文件。启动时使用内置脱敏演示 Snapshot；用户可通过文件选择器加载 Change 9 的 JSON Snapshot。数据经过前端 schema guard 后才渲染，所有外部文本使用 `textContent`，不拼接用户 HTML。

布局采用运营台风格：深色侧栏承载产品身份与 Run 导航，主区提供状态摘要、进度、Task 表格、决策链和 Approval panel。移动端侧栏折叠为顶部导航，卡片保持紧凑、无装饰性营销区块。
