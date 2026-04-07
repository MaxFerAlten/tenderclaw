"""SDK Validators — validation functions for SDK types."""

from __future__ import annotations

from typing import Any

from shared.sdk_errors import ValidationError
from shared.sdk_types import AgentConfig, AgentManifest, Message, Session, ToolDefinition


def validate_agent_config(config: AgentConfig | dict[str, Any]) -> AgentConfig:
    """Validate and coerce agent configuration."""
    if isinstance(config, dict):
        try:
            config = AgentConfig.model_validate(config)
        except Exception as e:
            raise ValidationError(str(e), field="agent_config")

    if not config.name or not config.name.strip():
        raise ValidationError("Agent name is required", field="name")

    if config.max_tokens <= 0:
        raise ValidationError("max_tokens must be positive", field="max_tokens")

    if config.timeout <= 0:
        raise ValidationError("timeout must be positive", field="timeout")

    return config


def validate_tool_definition(tool: ToolDefinition | dict[str, Any]) -> ToolDefinition:
    """Validate a tool definition."""
    if isinstance(tool, dict):
        try:
            tool = ToolDefinition.model_validate(tool)
        except Exception as e:
            raise ValidationError(str(e), field="tool_definition")

    if not tool.name or not tool.name.strip():
        raise ValidationError("Tool name is required", field="name")

    if not tool.description:
        raise ValidationError("Tool description is required", field="description")

    valid_risk_levels = {"none", "low", "medium", "high"}
    if tool.risk_level.lower() not in valid_risk_levels:
        raise ValidationError(
            f"Invalid risk_level: {tool.risk_level}. Must be one of {valid_risk_levels}",
            field="risk_level",
        )

    return tool


def validate_message(message: Message | dict[str, Any]) -> Message:
    """Validate a message."""
    if isinstance(message, dict):
        try:
            message = Message.model_validate(message)
        except Exception as e:
            raise ValidationError(str(e), field="message")

    if not message.content:
        raise ValidationError("Message content cannot be empty", field="content")

    return message


def validate_session(session: Session | dict[str, Any]) -> Session:
    """Validate a session."""
    if isinstance(session, dict):
        try:
            session = Session.model_validate(session)
        except Exception as e:
            raise ValidationError(str(e), field="session")

    if not session.session_id:
        raise ValidationError("session_id is required", field="session_id")

    return session


def validate_agent_manifest(manifest: AgentManifest | dict[str, Any]) -> AgentManifest:
    """Validate an agent manifest."""
    if isinstance(manifest, dict):
        try:
            manifest = AgentManifest.model_validate(manifest)
        except Exception as e:
            raise ValidationError(str(e), field="agent_manifest")

    if not manifest.name or not manifest.name.strip():
        raise ValidationError("Agent name is required", field="name")

    return manifest
