"""CLI error taxonomy and documented exit codes."""

from __future__ import annotations


class CliError(Exception):
    exit_code = 2
    category = "configuration"

    def __init__(self, message: str, *, request_id: str | None = None):
        super().__init__(message)
        self.request_id = request_id


class UsageError(CliError):
    category = "usage"


class ConfigurationError(CliError):
    category = "configuration"


class AuthenticationError(CliError):
    exit_code = 3
    category = "authentication"


class TransportError(CliError):
    exit_code = 4
    category = "transport"


class CompatibilityError(CliError):
    exit_code = 5
    category = "compatibility"


class ServerError(CliError):
    exit_code = 6
    category = "server"

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        server_code: str | None = None,
        request_id: str | None = None,
    ):
        super().__init__(message, request_id=request_id)
        self.status = status
        self.server_code = server_code
