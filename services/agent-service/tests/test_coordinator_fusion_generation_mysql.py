from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from factoryops_agent_service.coordinator_fusion import (
    FusionPersistenceRejected,
    FusionSaveOutcome,
)
from factoryops_agent_service.coordinator_fusion_generation import (
    CoordinatorFusionDraft,
    CoordinatorFusionGenerationCommand,
    CoordinatorFusionGenerationService,
    CoordinatorFusionProviderProvenance,
    FusionCandidateDraft,
    FusionGenerationContext,
    FusionGenerationFailed,
    FusionGenerationRejected,
    RecordedCoordinatorFusionProvider,
)
from factoryops_agent_service.event_ingress.migration import migrate
from sqlalchemy import Engine, create_engine, text
from test_coordinator_fusion_mysql import _parents
from testcontainers.community.mysql import MySqlContainer

GENERATED_AT = "2026-08-20T12:00:00Z"
PROVENANCE = CoordinatorFusionProviderProvenance(
    runtime_version="runtime:v1",
    prompt_version="coordinator/v1",
    model_policy_version="model:v1",
    tool_policy_version="tools:v1",
    context_policy_version="context:v1",
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


def _draft(sources: list[dict[str, object]]) -> CoordinatorFusionDraft:
    roles_by_action: dict[str, list[str]] = {}
    evidence: list[str] = []
    for source in sources:
        common = source["recommendation"]
        identity = source["identity"]
        roles_by_action.setdefault(str(common["action"]), []).append(
            str(identity["agent_role"])
        )
        evidence.extend(str(ref) for ref in common["evidence_refs"])
    all_roles = {role for roles in roles_by_action.values() for role in roles}
    candidates = tuple(
        FusionCandidateDraft(
            action=action,
            rank=index,
            score=max(0.1, 1.0 - (index - 1) * 0.3),
            supporting_roles=list(roles),
            opposing_roles=sorted(all_roles - set(roles)),
        )
        for index, (action, roles) in enumerate(roles_by_action.items(), 1)
    )
    conflict = len(candidates) > 1
    return CoordinatorFusionDraft(
        proposed_action=candidates[0].action,
        candidates=candidates,
        has_conflict=conflict,
        conflict_codes=("SPECIALIST_ACTION_DISAGREEMENT",) if conflict else (),
        evidence_refs=tuple(dict.fromkeys(evidence)),
        reason_codes=("SPECIALIST_RECOMMENDATIONS_FUSED",),
    )


class CapturingProvider:
    provenance = PROVENANCE

    def __init__(self, draft: CoordinatorFusionDraft) -> None:
        self.draft = draft
        self.contexts: list[FusionGenerationContext] = []

    def generate(self, context: FusionGenerationContext) -> CoordinatorFusionDraft:
        self.contexts.append(context)
        return self.draft


def _command(coordinator_id: str, sources: list[dict[str, object]], round: int = 1):
    return CoordinatorFusionGenerationCommand(
        coordinator_execution_id=coordinator_id,
        round=round,
        recommendation_keys=tuple(
            str(source["identity"]["recommendation_key"]) for source in sources
        ),
        generated_at=GENERATED_AT,
    )


def test_recorded_provider_returns_isolated_round_draft():
    source = [
        {
            "identity": {"agent_role": "quality"},
            "recommendation": {"action": "PASS", "evidence_refs": ["inspection:1"]},
        }
    ]
    draft = _draft(source)
    provider = RecordedCoordinatorFusionProvider({1: draft}, PROVENANCE)
    context = FusionGenerationContext(
        coordinator_execution_id="EXE-" + "1" * 32,
        run_id="RUN-" + "1" * 32,
        round=1,
        recommendations=(),
        provenance=PROVENANCE,
    )

    first = provider.generate(context)
    first.candidates[0].supporting_roles.append("sla")
    second = provider.generate(context)

    assert second.candidates[0].supporting_roles == ["quality"]


def test_generate_builds_identity_inputs_and_persists(mysql_engine: Engine):
    run_id, coordinator_id, sources = _parents(mysql_engine, "1")
    provider = CapturingProvider(_draft(sources))
    result = CoordinatorFusionGenerationService(mysql_engine).generate(
        _command(coordinator_id, sources), provider
    )

    assert result.outcome is FusionSaveOutcome.APPLIED
    assert result.fusion["identity"]["run_id"] == run_id
    assert result.fusion["identity"]["coordinator_execution_id"] == coordinator_id
    assert result.fusion["fusion"]["authorization_state"] == "NOT_EVALUATED"
    assert {
        r["recommendation_key"] for r in result.fusion["inputs"]["recommendations"]
    } == {source["identity"]["recommendation_key"] for source in sources}
    assert len(provider.contexts) == 1


def test_generate_canonicalizes_source_order_before_provider(mysql_engine: Engine):
    _, coordinator_id, sources = _parents(mysql_engine, "8")
    reversed_sources = list(reversed(sources))
    provider = CapturingProvider(_draft(sources))

    result = CoordinatorFusionGenerationService(mysql_engine).generate(
        _command(coordinator_id, reversed_sources), provider
    )

    assert result.outcome is FusionSaveOutcome.APPLIED
    assert [source.agent_role for source in provider.contexts[0].recommendations] == [
        "production",
        "quality",
        "sla",
    ]


def test_malformed_provider_draft_is_stably_rejected(mysql_engine: Engine):
    malformed_drafts = (
        CoordinatorFusionDraft(
            proposed_action="PASS",
            candidates=({"action": "PASS"},),  # type: ignore[arg-type]
            has_conflict=False,
            conflict_codes=(),
            evidence_refs=(),
            reason_codes=(),
        ),
        CoordinatorFusionDraft(
            proposed_action="PASS",
            candidates=(),
            has_conflict=False,
            conflict_codes=(),
            evidence_refs=(["inspection:1"],),  # type: ignore[arg-type]
            reason_codes=(),
        ),
    )
    _, coordinator_id, sources = _parents(mysql_engine, "9")

    for malformed in malformed_drafts:
        with pytest.raises(FusionGenerationRejected, match="unsupported draft"):
            CoordinatorFusionGenerationService(mysql_engine).generate(
                _command(coordinator_id, sources), CapturingProvider(malformed)
            )


def test_replay_shortcut_and_conflicting_request(mysql_engine: Engine):
    _, coordinator_id, sources = _parents(mysql_engine, "2")
    service = CoordinatorFusionGenerationService(mysql_engine)
    command = _command(coordinator_id, sources)
    assert (
        service.generate(command, CapturingProvider(_draft(sources))).outcome
        is FusionSaveOutcome.APPLIED
    )

    class MustNotRun:
        provenance = PROVENANCE

        def generate(self, context: FusionGenerationContext):
            raise AssertionError("provider called during replay")

    assert (
        service.generate(command, MustNotRun()).outcome
        is FusionSaveOutcome.DUPLICATE_IDENTICAL
    )
    conflicting = CoordinatorFusionGenerationCommand(
        coordinator_id,
        1,
        command.recommendation_keys[:2],
        GENERATED_AT,
    )
    assert (
        service.generate(conflicting, MustNotRun()).outcome
        is FusionSaveOutcome.DUPLICATE_CONFLICTING
    )


def test_provider_provenance_and_evidence_are_rejected(mysql_engine: Engine):
    _, coordinator_id, sources = _parents(mysql_engine, "3")
    command = _command(coordinator_id, sources)
    wrong_provenance = CoordinatorFusionProviderProvenance(
        **{**PROVENANCE.__dict__, "prompt_version": "coordinator/v2"}
    )

    class WrongProvider(CapturingProvider):
        provenance = wrong_provenance

    service = CoordinatorFusionGenerationService(mysql_engine)
    with pytest.raises(FusionGenerationRejected, match="provenance"):
        service.generate(command, WrongProvider(_draft(sources)))

    draft = _draft(sources)
    draft = CoordinatorFusionDraft(
        **{**draft.__dict__, "evidence_refs": ("ground_truth:hidden",)}
    )
    with pytest.raises(FusionGenerationRejected, match="authorized evidence"):
        service.generate(command, CapturingProvider(draft))


def test_concurrent_identical_calls_both_cross_provider_boundary(mysql_engine: Engine):
    _, coordinator_id, sources = _parents(mysql_engine, "4")
    barrier = threading.Barrier(2)

    class RacingProvider(CapturingProvider):
        def generate(self, context: FusionGenerationContext):
            self.contexts.append(context)
            barrier.wait(timeout=5)
            return self.draft

    providers = [RacingProvider(_draft(sources)) for _ in range(2)]
    service = CoordinatorFusionGenerationService(mysql_engine)
    command = _command(coordinator_id, sources)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            pool.map(lambda provider: service.generate(command, provider), providers)
        )

    assert {result.outcome for result in results} == {
        FusionSaveOutcome.APPLIED,
        FusionSaveOutcome.DUPLICATE_IDENTICAL,
    }
    assert [len(provider.contexts) for provider in providers] == [1, 1]


def test_coordinator_provenance_drift_during_provider_is_fenced(mysql_engine: Engine):
    _, coordinator_id, sources = _parents(mysql_engine, "5")
    entered = threading.Event()
    release = threading.Event()

    class BlockingProvider(CapturingProvider):
        def generate(self, context: FusionGenerationContext):
            entered.set()
            assert release.wait(5)
            return self.draft

    service = CoordinatorFusionGenerationService(mysql_engine)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            service.generate,
            _command(coordinator_id, sources),
            BlockingProvider(_draft(sources)),
        )
        assert entered.wait(5)
        with mysql_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE agent_executions SET prompt_version='coordinator/v2' WHERE execution_id=:id"
                ),
                {"id": coordinator_id},
            )
        release.set()
        with pytest.raises(FusionPersistenceRejected, match="provenance"):
            future.result()

    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM coordinator_fusions WHERE coordinator_execution_id=:id"
                ),
                {"id": coordinator_id},
            )
            == 0
        )


def test_two_sources_record_missing_role(mysql_engine: Engine):
    _, coordinator_id, sources = _parents(mysql_engine, "6")
    selected = sources[:2]
    result = CoordinatorFusionGenerationService(mysql_engine).generate(
        _command(coordinator_id, selected), CapturingProvider(_draft(selected))
    )

    assert result.outcome is FusionSaveOutcome.APPLIED
    assert result.fusion["inputs"]["missing_roles"] == ["sla"]


def test_provider_failure_leaves_no_fusion(mysql_engine: Engine):
    _, coordinator_id, sources = _parents(mysql_engine, "7")

    class FailingProvider:
        provenance = PROVENANCE

        def generate(self, context: FusionGenerationContext):
            raise TimeoutError("model timeout")

    with pytest.raises(FusionGenerationFailed, match="model timeout"):
        CoordinatorFusionGenerationService(mysql_engine).generate(
            _command(coordinator_id, sources), FailingProvider()
        )

    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM coordinator_fusions "
                    "WHERE coordinator_execution_id=:id"
                ),
                {"id": coordinator_id},
            )
            == 0
        )
