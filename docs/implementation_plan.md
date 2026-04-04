# [Phase 2 & 3 Fulfillment]

Verify the current state of Phase 1 and Phase 2, identify gaps (HUD component, AST-search), and proceed with implementation.

## User Review Required

> [!IMPORTANT]
> Some items for Phase 3 (like HashlineEdit and LSP) are already in the backend tools, but some Phase 2/3 foundation items like AST-grep and the HUD (Head-Up Display) in the frontend are missing or weren't finalized. I will focus on these gaps.

## Proposed Changes

### [Backend Tools]

#### [MODIFY] [registry.py](file:///d:/MY_AI/claude-code/TenderClaw/backend/tools/registry.py) e [startup.py](file:///d:/MY_AI/claude-code/TenderClaw/backend/tools/startup.py)
Update to include new tools once they are ready.

#### [NEW] [ast_grep_tool.py](file:///d:/MY_AI/claude-code/TenderClaw/backend/tools/ast_grep_tool.py)
Provide structural search capabilities for code understanding across 25+ languages.

### [Frontend UI]

#### [NEW] [HUD.tsx](file:///d:/MY_AI/claude-code/TenderClaw/frontend/src/components/layout/HUD.tsx)
Create a Head-Up Display overlay to track agent activities and health status.

#### [MODIFY] [AppShell.tsx](file:///d:/MY_AI/claude-code/TenderClaw/frontend/src/components/layout/AppShell.tsx)
Integrate the HUD into the main UI container.

## Verification Plan

### Automated Tests
- Run the backend `python -m backend.main` and verify the `/api/health` endpoint.
- Verify `ast-grep` tool initialization.

### Manual Verification
- Visual check of the HUD in the browser.
- Verify that multi-model routing is available through the API.
