"""Canvas (A2UI) Tool — Create or update an artifact on the frontend UI."""

from __future__ import annotations

import logging
from typing import Any

from backend.schemas.tools import RiskLevel, ToolResult
from backend.tools.base import BaseTool, ToolContext
from backend.schemas.ws import WSUIUpdate

logger = logging.getLogger("tenderclaw.tools.canvas")


class CanvasTool(BaseTool):
    """Publish content (code, markdown, text) directly to the user's Canvas UI."""

    name = "CanvasUpdate"
    description = (
        "Create or update an artifact on the user's screen (the A2UI Canvas). "
        "Use this for large code snippets, configuration files, architectural diagrams, "
        "or any content that the user would benefit from seeing in a standalone viewer. "
        "You can overwrite an existing artifact by using the same artifact_id."
    )
    risk_level = RiskLevel.LOW
    is_read_only = False
    concurrency_safe = True

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "artifact_id": {
                    "type": "string",
                    "description": "Unique identifier for this artifact (use kebab-case, e.g. 'auth-service-diagram'). Keep it the same to update an existing artifact.",
                },
                "title": {
                    "type": "string",
                    "description": "Human-readable title for the artifact.",
                },
                "content": {
                    "type": "string",
                    "description": "The full body content of the artifact to render.",
                },
                "language": {
                    "type": "string",
                    "description": "Optional syntax highlighting language (e.g. 'python', 'typescript', 'markdown').",
                },
            },
            "required": ["artifact_id", "title", "content"],
        }

    async def execute(
        self,
        tool_input: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        artifact_id = tool_input.get("artifact_id", "")
        title = tool_input.get("title", "")
        content = tool_input.get("content", "")
        language = tool_input.get("language")

        if not artifact_id or not title or not content:
            return ToolResult(
                tool_use_id=context.tool_use_id,
                content="Error: artifact_id, title, and content are required.",
                is_error=True,
            )
            
        from backend.services.session_store import session_store
        session = session_store.get(context.session_id)
        if session:
            session.artifacts[artifact_id] = {
                "artifact_id": artifact_id,
                "title": title,
                "content": content,
                "language": language or "",
            }
            session_store._save_state()

        if context.send:
            try:
                msg = WSUIUpdate(
                    artifact_id=artifact_id,
                    title=title,
                    content=content,
                    language=language,
                )
                await context.send(msg.model_dump())
            except Exception as exc:
                logger.error("Failed to send WSUIUpdate: %s", exc)
                return ToolResult(
                    tool_use_id=context.tool_use_id,
                    content=f"Error projecting to canvas: {exc}",
                    is_error=True,
                )

        return ToolResult(
            tool_use_id=context.tool_use_id,
            content=f"Canvas successfully updated with artifact '{artifact_id}'",
        )
