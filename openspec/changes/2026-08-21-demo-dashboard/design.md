# Design

`render_workflow_dashboard(snapshot)` 生成完整 HTML 文档。输入先做最小结构校验，文本全部 HTML escape，状态用固定 CSS class 映射，禁止把 snapshot 当作 HTML/JavaScript 解释。页面按 Run summary、Task table、Execution/Fusion/Risk/Approval sections 展示；缺失可选关联显示 `Not available`，不伪造业务收据。

输出是纯字符串，调用方可写入文件或嵌入已有静态站点。渲染器无数据库依赖、无网络访问、无副作用。
