from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.specialist_generation import (
    RecordedSpecialistProvider,
    SpecialistGenerationContext,
    SpecialistGenerationFailed,
    SpecialistGenerationRejected,
    SpecialistProviderProvenance,
    SpecialistRecommendationDraft,
    SpecialistRecommendationGenerationCommand,
    SpecialistRecommendationGenerationService,
)
from factoryops_agent_service.specialist_recommendation import (
    RecommendationPersistenceRejected,
    RecommendationSaveOutcome,
    SpecialistRecommendationService,
)
from factoryops_agent_service.worker_task_execution import WorkerTaskExecutionService
from sqlalchemy import Engine, create_engine, text
from test_worker_task_completion_mysql import _running, _success
from testcontainers.community.mysql import MySqlContainer

from contracts.specialist_recommendation.validator import (
    SpecialistRecommendationValidationError,
    compute_recommendation_key,
)

GENERATED_AT = "2026-08-20T09:00:00Z"
PROVENANCE = SpecialistProviderProvenance(
    runtime_version="runtime-v1",
    prompt_version="prompt-v1",
    model_policy_version="model-v1",
    tool_policy_version="tool-v1",
    context_policy_version="context-v1",
    code_revision="a" * 40,
)


@pytest.fixture(scope="module")
def mysql_engine() -> Engine:
    with MySqlContainer("mysql:8.4") as mysql:
        engine = create_engine(
            mysql.get_connection_url().replace("mysql://", "mysql+pymysql://", 1)
        )
        migrate(engine)
        yield engine
        engine.dispose()


def _context(role: str = "quality") -> SpecialistGenerationContext:
    return SpecialistGenerationContext(
        execution_id="EXE-" + "1" * 32,
        run_id="RUN-" + "1" * 32,
        task_id="TSK-" + "1" * 32,
        agent_role=role,
        task_type="QUALITY_ANALYSIS",
        context_snapshot_id="CTX-" + "1" * 32,
        evidence_refs=("context:one",),
        provenance=PROVENANCE,
    )


def _quality_draft(marker: str = "8") -> SpecialistRecommendationDraft:
    return SpecialistRecommendationDraft(
        action="HOLD_BATCH",
        severity="HIGH",
        confidence=0.91,
        evidence_refs=("inspection:" + marker,),
        reason_codes=("CONSECUTIVE_DEFECTS",),
        output_artifact_refs=(),
        details={"consecutive_defect_suspected": True},
    )


def test_recorded_provider_returns_isolated_role_draft():
    draft = _quality_draft()
    provider = RecordedSpecialistProvider({"quality": draft}, PROVENANCE)

    first = provider.generate(_context())
    first.details["consecutive_defect_suspected"] = False
    second = provider.generate(_context())

    assert second.details == {"consecutive_defect_suspected": True}


def test_recorded_provider_rejects_unconfigured_role():
    provider = RecordedSpecialistProvider({"quality": _quality_draft()}, PROVENANCE)

    with pytest.raises(SpecialistGenerationRejected, match="not configured"):
        provider.generate(_context("production"))


class CapturingProvider:
    provenance = PROVENANCE

    def __init__(self, draft: SpecialistRecommendationDraft) -> None:
        self.draft = draft
        self.contexts: list[SpecialistGenerationContext] = []

    def generate(
        self, context: SpecialistGenerationContext
    ) -> SpecialistRecommendationDraft:
        self.contexts.append(context)
        return self.draft


def test_generate_builds_identity_and_persists_current_execution(mysql_engine: Engine):
    task_id, _, execution_id = _running(mysql_engine, "8")
    provider = CapturingProvider(_quality_draft("8"))
    command = SpecialistRecommendationGenerationCommand(execution_id, GENERATED_AT)
    service = SpecialistRecommendationGenerationService(mysql_engine)

    result = service.generate(command, provider)

    key = compute_recommendation_key(execution_id)
    assert result.outcome is RecommendationSaveOutcome.APPLIED
    assert result.recommendation["identity"] == {
        "recommendation_id": "REC-" + key[4:36],
        "recommendation_key": key,
        "execution_id": execution_id,
        "run_id": result.recommendation["identity"]["run_id"],
        "task_id": task_id,
        "agent_role": "quality",
    }
    assert provider.contexts[0].context_snapshot_id.startswith("CTX-")
    assert "ground_truth" not in provider.contexts[0].__dict__
    assert SpecialistRecommendationService(mysql_engine).get_by_key(key) == (
        result.recommendation
    )


def test_replay_returns_existing_without_calling_provider(mysql_engine: Engine):
    task_id, lease, execution_id = _running(mysql_engine, "9")
    service = SpecialistRecommendationGenerationService(mysql_engine)
    command = SpecialistRecommendationGenerationCommand(execution_id, GENERATED_AT)
    assert service.generate(
        command, CapturingProvider(_quality_draft("9"))
    ).outcome is (RecommendationSaveOutcome.APPLIED)

    class MustNotRun:
        provenance = CapturingProvider.provenance

        def generate(self, context: SpecialistGenerationContext):
            raise AssertionError("provider was called during replay")

    replay = service.generate(command, MustNotRun())

    assert replay.outcome is RecommendationSaveOutcome.DUPLICATE_IDENTICAL
    assert replay.recommendation["identity"]["task_id"] == task_id

    class WrongReplayProvider(MustNotRun):
        provenance = SpecialistProviderProvenance(
            **{**PROVENANCE.__dict__, "model_policy_version": "model-v2"}
        )

    with pytest.raises(SpecialistGenerationRejected, match="provenance"):
        service.generate(command, WrongReplayProvider())
    with pytest.raises(SpecialistGenerationRejected, match="generated_at"):
        service.generate(
            SpecialistRecommendationGenerationCommand(execution_id, "not-a-time"),
            MustNotRun(),
        )

    WorkerTaskExecutionService(mysql_engine).complete(
        _success(task_id, execution_id, lease.owner_id, lease.lease_token, "9")
    )
    terminal_replay = service.generate(command, MustNotRun())
    assert terminal_replay.outcome is RecommendationSaveOutcome.DUPLICATE_IDENTICAL


def test_provider_failure_or_invalid_draft_leaves_no_fact(mysql_engine: Engine):
    _, _, failed_execution = _running(mysql_engine, "a")

    class FailingProvider:
        provenance = PROVENANCE

        def generate(self, context: SpecialistGenerationContext):
            raise TimeoutError("model timeout")

    service = SpecialistRecommendationGenerationService(mysql_engine)
    with pytest.raises(SpecialistGenerationFailed, match="model timeout"):
        service.generate(
            SpecialistRecommendationGenerationCommand(failed_execution, GENERATED_AT),
            FailingProvider(),
        )
    assert (
        SpecialistRecommendationService(mysql_engine).get_by_key(
            compute_recommendation_key(failed_execution)
        )
        is None
    )

    _, _, invalid_execution = _running(mysql_engine, "b")
    invalid = _quality_draft("b")
    invalid = SpecialistRecommendationDraft(**{**invalid.__dict__, "evidence_refs": ()})
    with pytest.raises(SpecialistRecommendationValidationError):
        service.generate(
            SpecialistRecommendationGenerationCommand(invalid_execution, GENERATED_AT),
            CapturingProvider(invalid),
        )


def test_concurrent_identical_generation_keeps_one_fact(mysql_engine: Engine):
    _, _, execution_id = _running(mysql_engine, "c")
    service = SpecialistRecommendationGenerationService(mysql_engine)
    command = SpecialistRecommendationGenerationCommand(execution_id, GENERATED_AT)

    barrier = threading.Barrier(2)

    class RacingProvider(CapturingProvider):
        def generate(self, context: SpecialistGenerationContext):
            self.contexts.append(context)
            barrier.wait(timeout=5)
            return self.draft

    providers = [RacingProvider(_quality_draft("c")) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            pool.map(
                lambda provider: service.generate(command, provider),
                providers,
            )
        )

    assert {result.outcome for result in results} == {
        RecommendationSaveOutcome.APPLIED,
        RecommendationSaveOutcome.DUPLICATE_IDENTICAL,
    }
    assert [len(provider.contexts) for provider in providers] == [1, 1]
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM specialist_recommendations "
                    "WHERE execution_id=:execution_id"
                ),
                {"execution_id": execution_id},
            )
            == 1
        )


def test_context_snapshot_mismatch_is_rejected_before_provider(mysql_engine: Engine):
    _, _, execution_id = _running(mysql_engine, "e")
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE agent_executions SET context_snapshot_id=:context_id "
                "WHERE execution_id=:execution_id"
            ),
            {"context_id": "CTX-" + "F" * 32, "execution_id": execution_id},
        )
    provider = CapturingProvider(_quality_draft("e"))

    with pytest.raises(SpecialistGenerationRejected, match="current RUNNING"):
        SpecialistRecommendationGenerationService(mysql_engine).generate(
            SpecialistRecommendationGenerationCommand(execution_id, GENERATED_AT),
            provider,
        )

    assert provider.contexts == []


def test_parent_becoming_terminal_during_provider_call_is_fenced(
    mysql_engine: Engine,
):
    task_id, lease, execution_id = _running(mysql_engine, "d")
    entered = threading.Event()
    release = threading.Event()

    class BlockingProvider:
        provenance = CapturingProvider.provenance

        def generate(self, context: SpecialistGenerationContext):
            entered.set()
            assert release.wait(5)
            return _quality_draft("d")

    service = SpecialistRecommendationGenerationService(mysql_engine)
    command = SpecialistRecommendationGenerationCommand(execution_id, GENERATED_AT)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(service.generate, command, BlockingProvider())
        assert entered.wait(5)
        WorkerTaskExecutionService(mysql_engine).complete(
            _success(
                task_id,
                execution_id,
                lease.owner_id,
                lease.lease_token,
                "d",
            )
        )
        release.set()
        with pytest.raises(RecommendationPersistenceRejected, match="not current"):
            future.result()

    assert (
        SpecialistRecommendationService(mysql_engine).get_by_key(
            compute_recommendation_key(execution_id)
        )
        is None
    )


def test_provider_provenance_and_references_are_fenced(mysql_engine: Engine):
    _, _, execution_id = _running(mysql_engine, "f")
    service = SpecialistRecommendationGenerationService(mysql_engine)
    command = SpecialistRecommendationGenerationCommand(execution_id, GENERATED_AT)
    wrong = SpecialistProviderProvenance(
        **{**CapturingProvider.provenance.__dict__, "prompt_version": "prompt-v2"}
    )

    class WrongProvider(CapturingProvider):
        provenance = wrong

    with pytest.raises(SpecialistGenerationRejected, match="provenance"):
        service.generate(command, WrongProvider(_quality_draft("f")))

    unauthorized_evidence = SpecialistRecommendationDraft(
        **{**_quality_draft("f").__dict__, "evidence_refs": ("ground_truth:hidden",)}
    )
    with pytest.raises(SpecialistGenerationRejected, match="authorized evidence"):
        service.generate(command, CapturingProvider(unauthorized_evidence))

    unauthorized_artifact = SpecialistRecommendationDraft(
        **{
            **_quality_draft("f").__dict__,
            "output_artifact_refs": ("artifact:untrusted",),
        }
    )
    with pytest.raises(SpecialistGenerationRejected, match="artifact"):
        service.generate(command, CapturingProvider(unauthorized_artifact))


def test_snapshot_changing_during_provider_call_is_fenced(mysql_engine: Engine):
    _, _, execution_id = _running(mysql_engine, "1")
    entered = threading.Event()
    release = threading.Event()

    class BlockingProvider(CapturingProvider):
        def generate(self, context: SpecialistGenerationContext):
            entered.set()
            assert release.wait(5)
            return self.draft

    service = SpecialistRecommendationGenerationService(mysql_engine)
    command = SpecialistRecommendationGenerationCommand(execution_id, GENERATED_AT)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            service.generate, command, BlockingProvider(_quality_draft("1"))
        )
        assert entered.wait(5)
        with mysql_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE agent_executions SET context_snapshot_id=:snapshot "
                    "WHERE execution_id=:execution"
                ),
                {"snapshot": "CTX-" + "F" * 32, "execution": execution_id},
            )
        release.set()
        with pytest.raises(RecommendationPersistenceRejected, match="not current"):
            future.result()

    assert (
        SpecialistRecommendationService(mysql_engine).get_by_key(
            compute_recommendation_key(execution_id)
        )
        is None
    )


def test_provenance_changing_during_provider_call_is_fenced(mysql_engine: Engine):
    _, _, execution_id = _running(mysql_engine, "2")
    entered = threading.Event()
    release = threading.Event()

    class BlockingProvider(CapturingProvider):
        def generate(self, context: SpecialistGenerationContext):
            entered.set()
            assert release.wait(5)
            return self.draft

    service = SpecialistRecommendationGenerationService(mysql_engine)
    command = SpecialistRecommendationGenerationCommand(execution_id, GENERATED_AT)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            service.generate, command, BlockingProvider(_quality_draft("2"))
        )
        assert entered.wait(5)
        with mysql_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE agent_executions SET prompt_version='prompt-v2' "
                    "WHERE execution_id=:execution"
                ),
                {"execution": execution_id},
            )
        release.set()
        with pytest.raises(RecommendationPersistenceRejected, match="provenance"):
            future.result()

    assert (
        SpecialistRecommendationService(mysql_engine).get_by_key(
            compute_recommendation_key(execution_id)
        )
        is None
    )
