"""SDK Types — shared type definitions for TenderClaw Agent SDK."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentMode(str, Enum):
    """Agent execution mode."""

    PRIMARY = "primary"
    SUBAGENT = "subagent"


class AgentCategory(str, Enum):
    """Agent specialization category."""

    ORCHESTRATION = "orchestration"
    EXPLORATION = "exploration"
    ADVISOR = "advisor"
    SPECIALIST = "specialist"
    UTILITY = "utility"


class AgentCost(str, Enum):
    """Relative cost level."""

    FREE = "free"
    CHEAP = "cheap"
    EXPENSIVE = "expensive"


class AgentConfig(BaseModel):
    """Configuration for agent initialization."""

    name: str
    model: str | None = None
    system_prompt: str | None = None
    tools: list[str] = Field(default_factory=list)
    max_tokens: int = 16384
    timeout: int = 300
    stream: bool = True


class AgentManifest(BaseModel):
    """Complete agent definition returned by the SDK."""

    name: str
    description: str
    mode: AgentMode = AgentMode.SUBAGENT
    default_model: str = "claude-sonnet-4-20250514"
    category: AgentCategory = AgentCategory.UTILITY
    cost: AgentCost = AgentCost.CHEAP
    system_prompt: str = ""
    max_tokens: int = 16384
    tools: list[str] = Field(default_factory=list)
    enabled: bool = True
    is_builtin: bool = False


class ToolParameter(BaseModel):
    """Single tool parameter definition."""

    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None


class ToolDefinition(BaseModel):
    """Tool definition for SDK consumption."""

    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    parameters: list[ToolParameter] = Field(default_factory=list)
    risk_level: str = "medium"
    is_read_only: bool = False


class ToolCall(BaseModel):
    """A single tool invocation request."""

    id: str
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Result from a tool execution."""

    id: str
    name: str
    content: str
    is_error: bool = False
    duration_ms: int = 0


class MessageRole(str, Enum):
    """Message author role."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ContentBlockType(str, Enum):
    """Content block type discriminator."""

    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    IMAGE = "image"


class TextContent(BaseModel):
    """Text content block."""

    type: ContentBlockType = ContentBlockType.TEXT
    text: str


class ToolUseContent(BaseModel):
    """Tool use content block."""

    type: ContentBlockType = ContentBlockType.TOOL_USE
    id: str
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


class ToolResultContent(BaseModel):
    """Tool result content block."""

    type: ContentBlockType = ContentBlockType.TOOL_RESULT
    tool_use_id: str
    content: str
    is_error: bool = False


class Message(BaseModel):
    """A conversation message."""

    role: MessageRole
    content: str | list[TextContent | ToolUseContent | ToolResultContent] = ""
    message_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionStatus(str, Enum):
    """Session lifecycle state."""

    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    CLOSED = "closed"


class Session(BaseModel):
    """SDK session representation."""

    session_id: str
    status: SessionStatus = SessionStatus.IDLE
    model: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    message_count: int = 0
    working_directory: str = ""


class TokenUsage(BaseModel):
    """Token usage statistics."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class AgentResponse(BaseModel):
    """Final response from an agent execution."""

    session_id: str
    message: Message
    stop_reason: str = "end_turn"
    usage: TokenUsage = Field(default_factory=TokenUsage)
    cost_usd: float = 0.0
    agent_name: str = ""


class StreamEventType(str, Enum):
    """Streaming event type discriminator."""

    DELTA = "delta"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_PROGRESS = "tool_progress"
    THINKING = "thinking"
    ERROR = "error"
    ABORT = "abort"
    COMPLETE = "complete"


class StreamEvent(BaseModel):
    """A streaming event from agent execution."""

    type: StreamEventType
    session_id: str
    data: str | dict[str, Any] = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SDKExecuteRequest(BaseModel):
    """Request to execute an SDK command."""

    command: str
    agent_name: str | None = None
    session_id: str | None = None
    message: str | None = None
    config: AgentConfig | None = None


class SDKExecuteResponse(BaseModel):
    """Response from SDK execute endpoint."""

    success: bool
    session_id: str | None = None
    message: str | None = None
    error: str | None = None


class SDKSchema(BaseModel):
    """Complete SDK schema for client generation."""

    version: str = "1.0.0"
    agents: list[AgentManifest] = Field(default_factory=list)
    tools: list[ToolDefinition] = Field(default_factory=list)
    message_types: list[str] = [m.value for m in MessageRole]
    stream_event_types: list[str] = [e.value for e in StreamEventType]
