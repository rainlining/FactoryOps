# Start Agent Run from Inbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让可信 `quality.incident.opened` record 在 Kafka offset 提交前可靠拥有唯一 `PENDING` original Workflow Run。

**Architecture:** 保留现有同步 Consumer 所有权。`EventIngressProcessor` 先提交或确认 Inbox，再调用独立 `IncidentRunStarter`；Starter 使用启动时冻结的 `AgentRuntimeConfig` 调用现有 `AgentRunLifecycleService`。Inbox 与 Run 使用顺序事务，Kafka 未提交 offset 负责触发恢复。

**Tech Stack:** Python 3.10+、SQLAlchemy Core 2.x、PyMySQL、confluent-kafka、pytest、Testcontainers MySQL 8.4 与 Apache Kafka 4.1.0、JSON Schema Contract。

## Global Constraints

- Change ID 固定为 `2026-08-15-start-agent-run-from-inbox`，学习等级为 `deep`。
- 不新增数据库 migration、Inbox processing status、Poller、Lease 或 Redis Lock。
- 本 Change 只创建 `PENDING` Run，不启动 Coordinator、LLM、Tool 或 `RUNNING` 迁移。
- `dataset/` 不得修改或纳入提交。
- Java 17 回归必须保持通过。
- 代码使用 Ruff 格式化，禁止把实现压成单行。
- 每个任务从失败测试开始，独立提交，并在最终 handoff 前进行完整验证。

## 文件结构

- Create `services/agent-service/src/factoryops_agent_service/event_ingress/runtime_config.py`：加载和校验不可变 Agent 版本配置。
- Create `services/agent-service/src/factoryops_agent_service/event_ingress/run_starter.py`：event → original Run 的 ensure 语义与完整性异常。
- Modify `services/agent-service/src/factoryops_agent_service/event_ingress/model.py`：显式 Incident、Run start outcome 和处理结果。
- Modify `services/agent-service/src/factoryops_agent_service/event_ingress/decoder.py`：一次解析后传递 Incident ID。
- Modify `services/agent-service/src/factoryops_agent_service/event_ingress/processor.py`：Inbox outcome 到 Starter 的应用编排。
- Modify `services/agent-service/src/factoryops_agent_service/event_ingress/worker.py`：记录 Run 结果并保持 offset/seek 顺序。
- Modify `services/agent-service/src/factoryops_agent_service/event_ingress/main.py`：启动配置与 fatal/retryable 进程边界。
- Modify `services/agent-service/tests/conftest.py`：提供统一版本配置 fixture（如确有跨测试复用）。
- Create `services/agent-service/tests/test_runtime_config.py`：配置边界测试。
- Create `services/agent-service/tests/test_run_starter.py`：Starter 单元测试。
- Modify `services/agent-service/tests/test_decoder.py`、`test_worker.py`、`test_inbox_mysql.py`、`test_kafka_mysql_e2e.py`：调用链和恢复测试。
- Modify OpenSpec `tasks.md`、`verification.md`、`review-handoff.md` 与 Agent Service README：记录真实实现和证据。

---

### Task 1: 冻结配置与 DecodedEvent Incident 语义

**Files:**
- Create: `services/agent-service/src/factoryops_agent_service/event_ingress/runtime_config.py`
- Modify: `services/agent-service/src/factoryops_agent_service/event_ingress/model.py`
- Modify: `services/agent-service/src/factoryops_agent_service/event_ingress/decoder.py`
- Create: `services/agent-service/tests/test_runtime_config.py`
- Modify: `services/agent-service/tests/test_decoder.py`

**Interfaces:**
- Produces: `AgentRuntimeConfig.from_environment(environment: Mapping[str, str]) -> AgentRuntimeConfig`
- Produces: `AgentRuntimeConfig.to_provenance(incident_id: str) -> RunProvenance`
- Produces: `AgentRuntimeConfigurationError(ValueError)`
- Changes: `DecodedEvent.incident_id: str`

- [ ] **Step 1: 写配置缺失、非法版本、非法 code revision 和成功加载的失败测试**

```python
def test_runtime_config_requires_every_version():
    with pytest.raises(AgentRuntimeConfigurationError, match="PROMPT_SET"):
        AgentRuntimeConfig.from_environment(valid_environment_without_prompt())

def test_runtime_config_builds_provenance():
    config = AgentRuntimeConfig.from_environment(valid_environment())
    assert config.to_provenance("QI-" + "A" * 64).prompt_set_version == "prompts:1.0.0"
```

- [ ] **Step 2: 写 Decoder Incident 失败测试**

```python
def test_decoded_event_exposes_incident_id(valid_record):
    decoded = KafkaRecordDecoder().decode(valid_record)
    assert decoded.incident_id == "QI-" + "A" * 64
    assert decoded.message_key == decoded.incident_id
```

- [ ] **Step 3: 运行测试确认 RED**

Run: `python -m pytest -q tests/test_runtime_config.py tests/test_decoder.py`

Expected: import/attribute failures because config and `incident_id` do not exist.

- [ ] **Step 4: 实现不可变配置与精确字段校验**

```python
@dataclass(frozen=True)
class AgentRuntimeConfig:
    runtime_version: str
    workflow_version: str
    prompt_set_version: str
    model_policy_version: str
    tool_policy_version: str
    context_policy_version: str
    code_revision: str

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str],
    ) -> "AgentRuntimeConfig":
        """Read every required value once, validate it, and return frozen config."""
        raise NotImplementedError

    def to_provenance(self, incident_id: str) -> RunProvenance:
        return RunProvenance(
            incident_id=incident_id,
            runtime_version=self.runtime_version,
            workflow_version=self.workflow_version,
            prompt_set_version=self.prompt_set_version,
            model_policy_version=self.model_policy_version,
            tool_policy_version=self.tool_policy_version,
            context_policy_version=self.context_policy_version,
            code_revision=self.code_revision,
        )
```

版本值使用 Agent Run Contract 的 `^[A-Za-z0-9][A-Za-z0-9._:-]*$`；code revision 使用 `^[0-9a-f]{7,64}$`。错误必须指出具体环境变量。环境映射只读取一次，不在每条 record 上读取 `os.environ`。

- [ ] **Step 5: 给 `DecodedEvent` 增加 `incident_id` 并由 Decoder 填充**

保留 `message_key`，不得让 Starter 重新解析 `raw_payload`。

- [ ] **Step 6: 运行局部测试与 Ruff**

Run: `python -m pytest -q tests/test_runtime_config.py tests/test_decoder.py`

Run: `python -m ruff check src tests && python -m ruff format --check src tests`

Expected: all pass.

- [ ] **Step 7: 提交**

```bash
git add services/agent-service/src/factoryops_agent_service/event_ingress services/agent-service/tests/test_runtime_config.py services/agent-service/tests/test_decoder.py
git commit -m "feat(agent): freeze run startup provenance"
```

### Task 2: 实现 IncidentRunStarter Ensure 语义

**Files:**
- Create: `services/agent-service/src/factoryops_agent_service/event_ingress/run_starter.py`
- Create: `services/agent-service/tests/test_run_starter.py`

**Interfaces:**
- Consumes: `AgentRuntimeConfig.to_provenance(incident_id)`
- Consumes: `AgentRunLifecycleService.create_original_run(OriginalRunCommand) -> RunOperationResult`
- Produces: `RunStartOutcome.CREATED | ALREADY_STARTED`
- Produces: `RunStartResult(outcome: RunStartOutcome, run_id: str)`
- Produces: `RunStartIntegrityError(RuntimeError)`
- Produces: `IncidentRunStarter.ensure_original_run(event: DecodedEvent) -> RunStartResult`

- [ ] **Step 1: 写 created、identical、配置变化 conflicting 和 Incident 冲突测试**

使用 fake lifecycle port 返回真实形状的 Contract mapping：

测试文件先定义 `contract_run(incident_id)`，返回包含完整 `identity.run_id` 与
`provenance.incident_id` 的有效 Agent Run Contract mapping；再定义
`conflicting_run(incident_id)`，返回 outcome 为 `DUPLICATE_CONFLICTING`、run 为
`contract_run(incident_id)` 的 `RunOperationResult`。不得用不完整字典掩盖 Contract
解析错误。

```python
def test_existing_run_with_changed_config_is_already_started():
    lifecycle.result = RunOperationResult(
        OperationOutcome.DUPLICATE_CONFLICTING,
        contract_run(incident_id=EVENT.incident_id),
    )
    result = starter.ensure_original_run(EVENT)
    assert result.outcome is RunStartOutcome.ALREADY_STARTED

def test_existing_run_for_other_incident_is_fatal():
    lifecycle.result = conflicting_run("QI-" + "B" * 64)
    with pytest.raises(RunStartIntegrityError, match="Incident"):
        starter.ensure_original_run(EVENT)
```

还必须覆盖 lifecycle 返回 `run=None`、Contract 结构缺字段以及 `PersistenceIntegrityError` 转换为 fatal integrity error。

- [ ] **Step 2: 运行测试确认 RED**

Run: `python -m pytest -q tests/test_run_starter.py`

Expected: module import failure.

- [ ] **Step 3: 实现最小 Starter**

```python
class RunLifecyclePort(Protocol):
    def create_original_run(
        self,
        command: OriginalRunCommand,
    ) -> RunOperationResult:
        raise NotImplementedError

class IncidentRunStarter:
    def ensure_original_run(self, event: DecodedEvent) -> RunStartResult:
        result = self._lifecycle.create_original_run(
            OriginalRunCommand(event.event_id, self._config.to_provenance(event.incident_id))
        )
        # APPLIED => CREATED
        # duplicate with same Incident => ALREADY_STARTED
        # missing/invalid/mismatched persisted Run => RunStartIntegrityError
```

Starter 必须从返回 Contract 的 `identity.run_id` 与 `provenance.incident_id` 取值，不访问 Lifecycle Repository 私有方法，不修改已有 Provenance。

- [ ] **Step 4: 运行测试确认 GREEN 并检查格式**

Run: `python -m pytest -q tests/test_run_starter.py`

Run: `python -m ruff check src tests && python -m ruff format --check src tests`

- [ ] **Step 5: 提交**

```bash
git add services/agent-service/src/factoryops_agent_service/event_ingress/run_starter.py services/agent-service/tests/test_run_starter.py
git commit -m "feat(agent): ensure original run for incident event"
```

### Task 3: 将 Starter 接入 Processor 和处理结果

**Files:**
- Modify: `services/agent-service/src/factoryops_agent_service/event_ingress/model.py`
- Modify: `services/agent-service/src/factoryops_agent_service/event_ingress/processor.py`
- Modify: `services/agent-service/tests/test_worker.py`
- Modify: `services/agent-service/tests/test_inbox_mysql.py`

**Interfaces:**
- Changes: `ProcessingResult(outcome, event_id, run_id, run_start_outcome)`
- Produces: `RunStartOutcome.NOT_APPLICABLE`
- Consumes: `IncidentRunStarter.ensure_original_run(event)`

- [ ] **Step 1: 写 Processor 路由失败测试**

测试矩阵必须精确断言：

```text
ACCEPTED              → starter called → created/already-started
DUPLICATE_IDENTICAL   → starter called → created/already-started
REJECTED_INVALID      → starter not called → not-applicable
REJECTED_CONFLICTING  → starter not called → not-applicable
```

在 Inbox MySQL 测试中证明 Inbox 已存在但 Run 尚未创建时，duplicate-identical 仍调用 Starter。

- [ ] **Step 2: 运行测试确认 RED**

Run: `python -m pytest -q tests/test_worker.py tests/test_inbox_mysql.py`

Expected: constructor/result assertion failures because Processor 尚无 Starter。

- [ ] **Step 3: 实现路由与结果组合**

```python
if outcome in {IngressOutcome.ACCEPTED, IngressOutcome.DUPLICATE_IDENTICAL}:
    started = self._run_starter.ensure_original_run(event)
    return ProcessingResult(outcome, event.event_id, started.run_id, started.outcome)
return ProcessingResult(outcome, event_id, None, RunStartOutcome.NOT_APPLICABLE)
```

不得让 Repository 或 Worker直接调用 Starter。

- [ ] **Step 4: 更新所有 ProcessingResult fixtures，并运行局部测试**

Run: `python -m pytest -q tests/test_worker.py tests/test_inbox_mysql.py`

Expected: all pass.

- [ ] **Step 5: 提交**

```bash
git add services/agent-service/src/factoryops_agent_service/event_ingress/model.py services/agent-service/src/factoryops_agent_service/event_ingress/processor.py services/agent-service/tests/test_worker.py services/agent-service/tests/test_inbox_mysql.py
git commit -m "feat(agent): start runs from trusted inbox outcomes"
```

### Task 4: 冻结 Worker 日志与 fatal/retryable 进程边界

**Files:**
- Modify: `services/agent-service/src/factoryops_agent_service/event_ingress/worker.py`
- Modify: `services/agent-service/src/factoryops_agent_service/event_ingress/main.py`
- Modify: `services/agent-service/tests/test_worker.py`
- Create: `services/agent-service/tests/test_main.py`

**Interfaces:**
- Consumes: `RunStartIntegrityError` and `AgentRuntimeConfigurationError`
- Changes: Worker processed log includes `run_id` and `run_start_outcome`
- Produces: testable `run_forever(worker, retry_delay_seconds, sleep)` or equivalent small process-loop function

- [ ] **Step 1: 写日志、retryable 重试和 fatal 退出测试**

```python
def test_fatal_integrity_failure_is_not_retried():
    worker = FakeWorker([RunStartIntegrityError("mismatch")])
    with pytest.raises(RunStartIntegrityError):
        run_forever(worker, sleep=lambda _: pytest.fail("must not sleep"))

def test_retryable_failure_waits_and_retries():
    retryable_error = OperationalError(
        "INSERT INTO agent_workflow_run",
        {},
        RuntimeError("database unavailable"),
    )
    successful_result = ProcessingResult(
        outcome=IngressOutcome.ACCEPTED,
        event_id=EVENT_ID,
        run_id=RUN_ID,
        run_start_outcome=RunStartOutcome.CREATED,
    )
    worker = FakeWorker([retryable_error, successful_result])
    run_forever(worker, stop_after_success=True, sleep=recording_sleep)
    assert recording_sleep.calls == [1.0]
```

Worker 失败仍必须 seek 当前 record；main 只对非 fatal 异常 sleep/retry。

- [ ] **Step 2: 运行测试确认 RED**

Run: `python -m pytest -q tests/test_worker.py tests/test_main.py`

- [ ] **Step 3: 提取可测试进程循环并接入配置/Starter**

启动顺序必须是：读取数据库/Kafka环境 → `AgentRuntimeConfig.from_environment` → create engine/migrate → create Kafka Consumer。配置错误必须早于 Kafka Consumer ownership。

`main` 构造 `IncidentRunStarter(AgentRunLifecycleService(engine), config)` 并注入 Processor。不得捕获 `RunStartIntegrityError` 后继续循环。

- [ ] **Step 4: 更新结构化日志断言**

日志必须包含 `run_id=<id|none>` 与 `run_start_outcome=<value>`，且现有 topic/partition/offset/redelivery 字段保持。

- [ ] **Step 5: 运行局部测试与 Ruff**

Run: `python -m pytest -q tests/test_worker.py tests/test_main.py`

Run: `python -m ruff check src tests && python -m ruff format --check src tests`

- [ ] **Step 6: 提交**

```bash
git add services/agent-service/src/factoryops_agent_service/event_ingress/main.py services/agent-service/src/factoryops_agent_service/event_ingress/worker.py services/agent-service/tests/test_worker.py services/agent-service/tests/test_main.py
git commit -m "feat(agent): classify run start process failures"
```

### Task 5: 证明两个事务和 Kafka 重投恢复

**Files:**
- Modify: `services/agent-service/tests/test_inbox_mysql.py`
- Modify: `services/agent-service/tests/test_kafka_mysql_e2e.py`

**Interfaces:**
- Consumes all production interfaces from Tasks 1–4.
- Produces executable evidence for Inbox → Run → offset completion invariant.

- [ ] **Step 1: 写真实 MySQL 顺序事务测试**

覆盖：首次 `created`；Inbox 已存在/Run 缺失时补建；配置变化时 `already-started` 且旧 Provenance 不变；并发确保单 Run/单 initial history；Incident 不一致 fatal。

- [ ] **Step 2: 写 Inbox commit 后故障的 Kafka E2E 失败测试**

使用 `FailFirstRunStarter`：首次调用抛 `OperationalError` 或专用 injected retryable exception，第二次委托真实 Starter。

第一次 `run_once` 后断言：

```text
Inbox count = 1
Run count = 0
committed offset != record.offset + 1
```

第二次处理后断言：

```text
ingress_outcome = duplicate-identical
run_start_outcome = created
Inbox count = 1
Run count = 1
initial history count = 1
committed offset = record.offset + 1
```

- [ ] **Step 3: 运行目标集成测试确认 RED，再完成 fixture 接线**

Run: `python -m pytest -q tests/test_inbox_mysql.py tests/test_kafka_mysql_e2e.py`

- [ ] **Step 4: 运行完整 Agent Service 验证**

Run: `python -m ruff check src tests`

Run: `python -m ruff format --check src tests`

Run: `python -m pytest -q`

Expected: all Agent Service tests pass with Docker running.

- [ ] **Step 5: 提交**

```bash
git add services/agent-service/tests/test_inbox_mysql.py services/agent-service/tests/test_kafka_mysql_e2e.py
git commit -m "test(agent): prove inbox to run crash recovery"
```

### Task 6: 全量验证、技术文档与 Review Handoff

**Files:**
- Modify: `services/agent-service/README.md`
- Modify: `openspec/changes/2026-08-15-start-agent-run-from-inbox/tasks.md`
- Modify: `openspec/changes/2026-08-15-start-agent-run-from-inbox/verification.md`
- Modify: `openspec/changes/2026-08-15-start-agent-run-from-inbox/review-handoff.md`

**Interfaces:**
- Produces a pushed `review-handoff-ready` branch for the independent Review/Learning session.

- [ ] **Step 1: 更新 README**

记录七个环境变量、可信事件到 PENDING Run 的成功链、retryable/fatal 行为及“不启动 Coordinator”的边界。

- [ ] **Step 2: 运行完整验证并保存实际数量**

From `services/agent-service`:

```powershell
python -m ruff check src tests
python -m ruff format --check src tests
python -m pytest -q
```

From repository root:

```powershell
python -m unittest discover -s contracts -p "test_*.py" -q
git diff --check main..HEAD
```

From `backend/business-service`:

```powershell
mvn -q verify
```

必须从 XML 报告核对 Java tests/failures/errors/skipped，不得只凭日志判断。

- [ ] **Step 3: 完成 OpenSpec 证据**

`verification.md` 写入真实命令、数量、Docker/MySQL/Kafka 证据、限制和 `dataset/` 范围检查。`review-handoff.md` 写入 base/head、入口、成功/失败调用链、Owner 修改和故障实验。

- [ ] **Step 4: 独立只读代码审查**

以 `main` base 与最终 implementation head 审查完整 diff；修复所有 Critical/Important 后重新运行受影响及完整测试。

- [ ] **Step 5: 提交并推送**

```bash
git add services/agent-service/README.md openspec/changes/2026-08-15-start-agent-run-from-inbox
git commit -m "docs: prepare inbox run start review handoff"
git push -u origin codex/start-agent-run-from-inbox
```

最终停在 `review-handoff-ready`，不在实现会话归档或合并 `main`。
