# Change 设计：扫描 FactoryOps 批次队列

## 1. 边界

本 Change 在现有演示工作台中增加一个本地批次入口和持久化调度层。浏览器负责由操作者授权读取目录与展示队列；Python Demo Server 负责保存批次清单、原子领取待运行项、创建独立 Run 和确定性路由。既有 Agent 调用链仍负责单个批次分析。

浏览器安全模型不允许服务端未经授权任意读取 `C:\...\dataset\factoryops`。因此用户仍需点击“选择 FactoryOps 根目录”，但一次选择即可导入其中所有直接子批次；不会要求逐批选择。

## 2. 组件

- `Batch root scanner`：按 `webkitdirectory` 返回的相对路径分组，验证扩展名并计算 SHA-256。
- `Queue repository`：SQLite 保存队列批次、冻结清单、当前 Run、状态和路由事实。
- `Queue dispatcher`：默认单并发，原子领取一个 `QUEUED` 项并调用现有异步 Run 入口。
- `Outcome router`：只读取结构化 Coordinator/Risk 事实，以确定性规则映射到 `QA_ACCEPTED`、`RECHECK_REQUIRED`、`WAITING_FOR_APPROVAL` 或 `FAILED`。
- `Queue UI`：显示根目录摘要、全局进度、逐批状态、当前批次和操作入口。

## 3. 数据流

```text
用户选择 factoryops 根目录
  → 浏览器按直接子目录分组并计算清单摘要
  → POST /api/batch-queues/scan
  → 服务端幂等保存队列项
  → dispatcher 原子领取 QUEUED 批次
  → 为该批次创建独立现有 Run
  → 轮询/保存真实 Run 事件
  → outcome router 形成队列终态
  → 继续领取下一批次
```

## 4. 状态与不变量

队列项状态：

```text
DISCOVERED → QUEUED → RUNNING
RUNNING → QA_ACCEPTED | RECHECK_REQUIRED | WAITING_FOR_APPROVAL | FAILED | CANCELLED
FAILED | CANCELLED → QUEUED（显式重试，创建派生 Run）
```

关键不变量：

- 一个队列项在任一时刻最多关联一个活动 Run。
- 输入清单一旦启动 Run 就不可改变；变化后的同名批次需要新 revision。
- `QA_ACCEPTED` 只是质检结论，不调用 `RELEASED` 迁移。
- `WAITING_FOR_APPROVAL` 只保存审批候选，不执行副作用。
- LLM 文本不能直接决定状态；缺少结构化字段时失败关闭。
- 查看历史、暂停队列或重复扫描不能触发模型调用。

## 5. 并发与恢复

首版默认并发度为 1，数据库仍使用条件更新领取队列项，防止重复 dispatcher 创建两个 Run。服务重启时：`QUEUED` 继续派发；已有 `RUNNING` 项先查询关联 Run，终态则补做路由，仍运行则继续观察，不存在或损坏则标记可诊断失败，禁止静默重启模型。

暂停只控制 dispatcher，不向已经运行的 Run 发送取消。批次取消分为取消待运行项和调用既有 Run cancel；两者均保存状态事实。

## 6. 失败路径

- 目录不可读或没有有效批次：拒绝扫描并显示原因。
- 同名批次清单变化：保留旧 revision，要求明确重新检测。
- 图片读取失败：该批次失败，不阻塞其他批次。
- Agent API 失败：保存已有证据和失败阶段，允许显式重试。
- Coordinator/Risk 输出不符合结构化约束：失败关闭，绝不自动通过。
- SQLite 或 dispatcher 故障：事务回滚；重启后从持久化状态恢复。

## 7. API 草案

- `POST /api/batch-queues/scan`：提交根目录显示名和批次清单。
- `GET /api/batch-queues/current`：查询当前队列及汇总。
- `POST /api/batch-queues/current/start`：开始或继续派发。
- `POST /api/batch-queues/current/pause`：暂停新派发。
- `POST /api/batch-queue-items/{id}/cancel`：取消待运行或活动批次。
- `POST /api/batch-queue-items/{id}/retry`：创建派生 Run 重试。

接口接受图片内容的方式延续现有本地 Demo 边界；不新增服务器任意路径读取能力。

## 8. 测试策略

- 前端 Contract：多目录分组、忽略规则、清单摘要、按钮与状态文案。
- Repository 单元/SQLite 测试：幂等扫描、同名变化、领取互斥、重启恢复。
- Runtime 测试：连续三批、待审批不阻塞、单批失败不阻塞、暂停/继续/取消/重试。
- 路由负向测试：缺失字段、冲突结论、未知动作均不得 `QA_ACCEPTED`。
- 浏览器真实验证：选择 `dataset/factoryops` 后显示全部批次，并连续完成录制或测试 Agent 流程。
- 回归：现有单批运行、历史只读、取消、Ruff、Java/Contract 验证和 dataset diff 检查。

## 9. 取舍

选择“显式目录选择 + 持久化队列”，而不是服务端监控硬编码绝对路径。前者可在浏览器权限模型下工作，也不会把开发机路径写进产品。

选择默认单并发，避免多批次同时调用模型造成速率限制和成本突增；数据模型保留未来提高并发度的能力。

选择把审批交互留给后续 Change。队列可以可靠地产生待审批事项，但审批权限、Java 副作用和幂等回执属于另一条需要独立 review 的核心能力。
