"""Executable boundary for FactoryOps vision inspection results."""

from .validator import (
    ValidationIssue,
    VisionContractValidationError,
    validate_result,
)

__all__ = [
    "ValidationIssue",
    "VisionContractValidationError",
    "validate_result",
]
