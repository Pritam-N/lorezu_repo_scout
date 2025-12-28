from __future__ import annotations

from enum import IntEnum
from typing import Optional


class ExitCode(IntEnum):
    OK = 0
    FINDINGS = 1
    ERROR = 2


class SecretScoutError(Exception):
    """
    Base exception for all repo-scout errors.
    Attach an exit code and safe message.
    """

    def __init__(
        self,
        message: str,
        *,
        exit_code: ExitCode = ExitCode.ERROR,
        detail: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.detail = detail


class ConfigError(SecretScoutError):
    pass


class RulesError(SecretScoutError):
    pass


class DependencyError(SecretScoutError):
    pass


class ScanExecutionError(SecretScoutError):
    pass


def exit_code_for(exc: BaseException) -> int:
    if isinstance(exc, SecretScoutError):
        return int(exc.exit_code)
    return int(ExitCode.ERROR)