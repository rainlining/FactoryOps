from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from factoryops_agent_service.run_lifecycle.model import RunProvenance

VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
CODE_REVISION_PATTERN = re.compile(r"^[0-9a-f]{7,64}$")


class AgentRuntimeConfigurationError(ValueError):
    """Raised when immutable Agent provenance cannot be loaded at startup."""


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
    ) -> AgentRuntimeConfig:
        values: dict[str, str] = {}
        version_variables = {
            "runtime_version": "FACTORYOPS_AGENT_RUNTIME_VERSION",
            "workflow_version": "FACTORYOPS_AGENT_WORKFLOW_VERSION",
            "prompt_set_version": "FACTORYOPS_AGENT_PROMPT_SET_VERSION",
            "model_policy_version": "FACTORYOPS_AGENT_MODEL_POLICY_VERSION",
            "tool_policy_version": "FACTORYOPS_AGENT_TOOL_POLICY_VERSION",
            "context_policy_version": "FACTORYOPS_AGENT_CONTEXT_POLICY_VERSION",
        }
        for field_name, variable_name in version_variables.items():
            values[field_name] = cls._required_value(
                environment,
                variable_name,
                VERSION_PATTERN,
                max_length=128,
            )
        values["code_revision"] = cls._required_value(
            environment,
            "FACTORYOPS_AGENT_CODE_REVISION",
            CODE_REVISION_PATTERN,
        )
        return cls(**values)

    @staticmethod
    def _required_value(
        environment: Mapping[str, str],
        variable_name: str,
        pattern: re.Pattern[str],
        *,
        max_length: int | None = None,
    ) -> str:
        value = environment.get(variable_name)
        if value is None:
            raise AgentRuntimeConfigurationError(
                f"missing required environment variable {variable_name}"
            )
        if pattern.fullmatch(value) is None or (
            max_length is not None and len(value) > max_length
        ):
            raise AgentRuntimeConfigurationError(
                f"invalid value for environment variable {variable_name}"
            )
        return value

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
