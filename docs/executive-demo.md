# FactoryOps 中文老板演示版

## Start

在项目演示 worktree 中打开 PowerShell：

```powershell
.\scripts\start_factoryops_demo.ps1
```

然后打开 `http://127.0.0.1:4173/dashboard.html`。

页面为中文只读录制场景，展示钣金检测图、表面纹理异常、受影响批次 `BATCH-2026-0817-A`、暂停批次建议、Agent 决策链和审批状态。

## Demo flow

1. 先查看“运行总览”和“已完成”状态。
2. 查看检测图片和“高风险”缺陷。
3. 依次查看专家任务、协调器、融合决策、风险评估和人工审批。
4. 说明当前是只读演示，不会执行真实审批或业务动作。

底层图片保留在 `dataset/`，仅通过固定的只读演示接口提供。
