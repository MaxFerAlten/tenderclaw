"""SDK Errors — exception hierarchy for TenderClaw Agent SDK."""


class SDKError(Exception):
    """Base exception for all SDK errors."""

    def __init__(self, message: str, code: str | None = None):
        self.message = message
        self.code = code or "sdk_error"
        super().__init__(self.message)


class AgentNotFoundError(SDKError):
    """Raised when an agent is not found in the registry."""

    def __init__(self, agent_name: str):
        super().__init__(f"Agent not found: {agent_name}", code="agent_not_found")
        self.agent_name = agent_name


class ToolNotFoundError(SDKError):
    """Raised when a tool is not found."""

    def __init__(self, tool_name: str):
        super().__init__(f"Tool not found: {tool_name}", code="tool_not_found")
        self.tool_name = tool_name


class SessionNotFoundError(SDKError):
    """Raised when a session is not found."""

    def __init__(self, session_id: str):
        super().__init__(f"Session not found: {session_id}", code="session_not_found")
        self.session_id = session_id


class ValidationError(SDKError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None):
        code = f"validation_error{': ' + field if field else ''}"
        super().__init__(message, code=code)
        self.field = field


class TimeoutError(SDKError):
    """Raised when an operation times out."""

    def __init__(self, operation: str, timeout_seconds: int):
        super().__init__(
            f"Operation '{operation}' timed out after {timeout_seconds}s",
            code="timeout",
        )
        self.operation = operation
        self.timeout_seconds = timeout_seconds
