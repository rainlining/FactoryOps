# FactoryOps Executive Demo

## Start

From the repository root:

```powershell
.\scripts\start_factoryops_demo.ps1
```

Open `http://127.0.0.1:4173/dashboard.html`.

The page is a read-only recorded scenario. It shows a sheet-metal inspection image, a recorded surface-texture finding, affected batch `BATCH-2026-0817-A`, the `HOLD_BATCH` recommendation, the Agent decision chain and approval state.

## Demo flow

1. Start on the Run overview and point out the `SUCCEEDED` workflow status.
2. Show the recorded inspection image and the high-severity finding.
3. Walk through Specialist Tasks and the Coordinator/Fusion/Risk/Approval chain.
4. Explain that no approval or business action controls are exposed in demo mode.

The underlying image remains in `dataset/` and is served only through the fixed read-only demo endpoint.
