from __future__ import annotations

import pytest

from factoryops_agent_service.event_ingress.runtime_config import (
    AgentRuntimeConfig,
    AgentRuntimeConfigurationError,
)

VALID_ENVIRONMENT = {
    "FACTORYOPS_AGENT_RUNTIME_VERSION": "agent-runtime:0.1.0",
    "FACTORYOPS_AGENT_WORKFLOW_VERSION": "incident-workflow:0.1.0",
    "FACTORYOPS_AGENT_PROMPT_SET_VERSION": "prompt-set:0.1.0",
    "FACTORYOPS_AGENT_MODEL_POLICY_VERSION": "model-policy:0.1.0",
    "FACTORYOPS_AGENT_TOOL_POLICY_VERSION": "tool-policy:0.1.0",
    "FACTORYOPS_AGENT_CONTEXT_POLICY_VERSION": "context-policy:0.1.0",
    "FACTORYOPS_AGENT_CODE_REVISION": "651228b9d71ee81e80e6a5030e4c49a50ec60f88",
}


def test_loads_frozen_runtime_configuration_and_builds_provenance() -> None:
    config = AgentRuntimeConfig.from_environment(VALID_ENVIRONMENT)

    provenance = config.to_provenance("QI-" + "A" * 64)

    assert provenance.incident_id == "QI-" + "A" * 64
    assert provenance.runtime_version == "agent-runtime:0.1.0"
    assert (
        provenance.code_revision == VALID_ENVIRONMENT["FACTORYOPS_AGENT_CODE_REVISION"]
    )


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("FACTORYOPS_AGENT_RUNTIME_VERSION", ""),
        ("FACTORYOPS_AGENT_WORKFLOW_VERSION", "invalid version"),
        ("FACTORYOPS_AGENT_CODE_REVISION", "not-a-revision"),
    ],
)
def test_rejects_missing_or_invalid_value_with_variable_name(
    name: str,
    value: str,
) -> None:
    environment = dict(VALID_ENVIRONMENT)
    environment[name] = value

    with pytest.raises(AgentRuntimeConfigurationError, match=name):
        AgentRuntimeConfig.from_environment(environment)


def test_rejects_absent_required_variable() -> None:
    environment = dict(VALID_ENVIRONMENT)
    del environment["FACTORYOPS_AGENT_MODEL_POLICY_VERSION"]

    with pytest.raises(
        AgentRuntimeConfigurationError,
        match="FACTORYOPS_AGENT_MODEL_POLICY_VERSION",
    ):
        AgentRuntimeConfig.from_environment(environment)
