# 🦞 TenderClaw User Tutorial

Welcome to **TenderClaw**, the most advanced multi-agent coding orchestrator. This guide will help you master the "Brain" and its "Superpowers".

## 1. Quick Start
If you haven't already, start both components:

**Backend:**
```bash
cd D:\MY_AI\claude-code\TenderClaw
python -m backend.main
```
**Frontend:**
```bash
cd frontend
npm run dev
```
Visit: `http://localhost:5173/tenderclaw`

---

## 2. Interaction Modes

### Standard Chat (Sisyphus)
Just type a message. **Sisyphus** (the orchestrator) will handle it. He uses a broad set of tools (FS, Bash, Grep, AST-grep) to act on your workspace.

### Team Pipeline (`/team`)
For complex features, use the **Team Pipeline**.
```text
/team implement a multi-tenant auth system for the backend
```
This triggers a 3-agent orchestration:
1.  **Metis (Strategy)**: Brainstorms and writes a detailed plan.
2.  **Sisyphus (Task-Bot)**: Executes the plan step-by-step.
3.  **Momus (Reviewer)**: Audits the code and suggests fixes.

---

## 3. High-Level HUD (Head-Up Display)
In the bottom-right corner, you'll see the **Execution Trace**.
- It shows the **Active Agent** (e.g., "ORACLE tracing").
- It logs **Tool Progression** (e.g., "Reading file... 80%").
- It captures **Cost & Tokens** in real-time.

---

## 4. Canvas & A2UI (Artifacts)
When an agent creates a significant document (a design spec, a complex script, or a React component), it appears in the **Canvas** side panel.
- This panel is persistent.
- You can minimize it with the `X` button.
- It allows for "Agent-to-UI" collaboration without cluttering the chat.

---

## 5. Superpowers Skills
TenderClaw has been integrated with the **Superpowers** skill library. These are automatic workflows.
- To see available skills: Ask TenderClaw `"What powers do you have?"`.
- To trigger a skill: Just mention the workflow. For example: `"Let's use TDD to write this utility"` or `"Let's brainstorm this architectural gap"`.
- The agent will read the `SKILL.md` file from `superpowers/` and follow the exact protocol (e.g., the RED-GREEN-REFACTOR cycle).

---

## 7. Internal API & External Access
You can use TenderClaw's brains in other apps! 
Point your OpenAI-compatible client (like Continue in VS Code or Cursor) to:
- **URL**: `http://localhost:7000/api/chat/completions`
- **Model**: `sisyphus`, `metis`, or `oracle`

Now you're ready to build something spectacular.
# 🦞
