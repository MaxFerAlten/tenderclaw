"""Register all built-in tools at startup."""

import logging
from backend.tools.registry import ToolRegistry

logger = logging.getLogger("tenderclaw.tools")


def register_builtin_tools(registry: ToolRegistry) -> None:
    """Register all built-in tools into the registry."""
    from backend.tools.bash_tool import BashTool
    from backend.tools.file_read_tool import FileReadTool
    from backend.tools.file_write_tool import FileWriteTool
    from backend.tools.file_edit_tool import FileEditTool
    from backend.tools.glob_tool import GlobTool
    from backend.tools.grep_tool import GrepTool
    from backend.tools.hashline_read_tool import HashlineReadTool
    from backend.tools.hashline_edit_tool import HashlineEditTool
    from backend.tools.web_search_tool import WebSearchTool
    from backend.tools.agent_tool import AgentDelegateTool
    from backend.tools.ast_grep_tool import AstGrepTool
    from backend.tools.lsp_tools import (
        LspGotoDefinitionTool,
        LspFindReferencesTool,
        LspDiagnosticsTool,
    )

    tools = [
        BashTool(),
        FileReadTool(),
        FileWriteTool(),
        FileEditTool(),
        HashlineReadTool(),
        HashlineEditTool(),
        GlobTool(),
        GrepTool(),
        WebSearchTool(),
        AgentDelegateTool(),
        AstGrepTool(),
        LspGotoDefinitionTool(),
        LspFindReferencesTool(),
        LspDiagnosticsTool(),
    ]

    for tool in tools:
        registry.register(tool)
    
    logger.info("Registered %d built-in tools", len(tools))
