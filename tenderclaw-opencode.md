# TenderClaw OpenCode Plan

## Phase 3 Completion Tasks

### 1. Wire MCP Bridge → Tool Registry
- Edit `backend/tools/startup.py` to add `_register_mcp_tools()` function
- Import `create_mcp_tool_proxies` from `backend.mcp.bridge`
- Register MCP tools after built-in tools

### 2. Skills Path Locale
- Edit `backend/core/skills.py` to add local skills path
- Add `Path(__file__).parent.parent / "skills"` to SKILLS_PATHS

### 3. Intent Gate → Pipeline Integration
- Edit `backend/core/conversation.py` to call `team_pipeline.run_implement_pipeline()` for implement intents

### 4. Test End-to-End
- Run backend and verify all components
