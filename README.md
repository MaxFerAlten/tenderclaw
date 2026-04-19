# TenderClaw

TenderClaw is a local-first, multi-agent, multi-model AI coding assistant.
It combines a FastAPI backend, a React/Vite web UI, WebSocket streaming, an
OpenAI-compatible gateway, provider routing, tool execution, session history,
and workspace-backed chat archives.

The project is in active development. Treat the codebase as an orchestration
workbench: useful, powerful, and intentionally evolving.

## What It Does

- Runs a browser UI at `/tenderclaw` for chat, settings, agents, history, and coordinator views.
- Streams conversations over `/api/ws/{session_id}`.
- Exposes REST APIs under `/api/*`, including sessions, config, tools, skills, history, diagnostics, archive, and notifications.
- Provides an OpenAI-compatible API surface under `/api/v1`.
- Routes model calls across cloud and local providers.
- Persists conversations and generated chat artifacts under `~/workspace_tenderclaw/chat`.
- Supports local provider workflows through LM Studio, Ollama, llama.cpp, and gpt4free.
- Supports cloud/provider workflows through Anthropic, OpenAI, Google, xAI, DeepSeek/OpenRouter, OpenCode, and OpenRouter.
- Adapts reasoning power levels across providers: `low`, `medium`, `high`, `extra_high`, and `max`.

## Architecture

```text
frontend React UI
        |
        | HTTP + WebSocket
        v
backend FastAPI app
        |
        +-- API routers             backend/api/
        +-- conversation loop       backend/core/
        +-- model routing           backend/services/model_router.py
        +-- provider adapters       backend/services/providers/
        +-- tool registry/runtime   backend/tools/
        +-- hooks and skills        backend/hooks/ + backend/plugins/
        +-- session persistence     backend/services/session_store.py
        +-- chat workspace          ~/workspace_tenderclaw/chat/
```

The frontend is mounted by the backend from `frontend/dist` when a production
build exists. Development can also run Vite separately on port `5173`.

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- npm
- `uv` recommended for Python dependency management

Optional, depending on provider:

- LM Studio at `http://localhost:1234/v1`
- Ollama at `http://localhost:11434/v1`
- llama.cpp server at `http://localhost:3080/v1`
- Playwright for browser e2e tests
- OpenTelemetry collector if exporting traces/metrics

## Quick Start

Install backend dependencies:

```bash
uv sync --extra dev
```

Install frontend dependencies:

```bash
cd frontend
npm install
cd ..
```

Create local configuration:

```bash
cp .env.example .env
```

Then edit `.env` with whichever provider keys or local model URLs you use.

Build the UI and start the backend:

```bash
./start.sh
```

Open:

```text
http://localhost:7000/tenderclaw
```

Stop the server:

```bash
./start.sh stop
```

## Development

Run the backend directly:

```bash
uv run python -m uvicorn backend.main:app --host localhost --port 7000 --reload
```

Run the frontend dev server:

```bash
cd frontend
npm run dev
```

The Vite app is served from:

```text
http://localhost:5173/tenderclaw
```

For CORS during frontend development, keep `TENDERCLAW_DEV=1` in `.env`.

## Configuration

TenderClaw reads `.env` through `backend/config.py`. Most TenderClaw-specific
variables use the `TENDERCLAW_` prefix; provider API keys use their standard
environment variable names.

Common settings:

```bash
TENDERCLAW_HOST=localhost
TENDERCLAW_PORT=7000
TENDERCLAW_DEV=1
TENDERCLAW_DEFAULT_MODEL=claude-sonnet-4-20250514
TENDERCLAW_LOG_LEVEL=INFO

ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=
XAI_API_KEY=
DEEPSEEK_API_KEY=
OPENROUTER_API_KEY=
OPENCODE_API_KEY=

TENDERCLAW_LMSTUDIO_BASE_URL=http://localhost:1234/v1
TENDERCLAW_OLLAMA_BASE_URL=http://localhost:11434/v1
TENDERCLAW_LLAMACPP_BASE_URL=http://localhost:3080/v1
TENDERCLAW_GPT4FREE_BASE_URL=http://localhost:1337/v1
```

OpenTelemetry:

```bash
TENDERCLAW_OTEL_ENABLED=1
TENDERCLAW_OTEL_CONSOLE_EXPORT=0
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

Do not commit real API keys.

## Testing

Backend unit and integration tests:

```bash
uv run pytest backend/tests -m 'not e2e'
```

Targeted backend tests:

```bash
uv run pytest backend/tests/test_power_levels.py
```

Lint backend Python:

```bash
uv run ruff check backend
```

Build frontend:

```bash
cd frontend
npm run build
```

Browser e2e tests are marked `e2e` and require the relevant services plus
Playwright:

```bash
uv run pytest backend/tests -m e2e
```

## API Surface

The backend mounts all API routes under `/api`.

Important route groups:

- `/api/health` - health check
- `/api/sessions` - create, list, and manage sessions
- `/api/ws/{session_id}` - streaming chat WebSocket
- `/api/v1/*` - OpenAI-compatible gateway
- `/api/config` - runtime/provider configuration
- `/api/diagnostics/*` - provider diagnostics
- `/api/tools` - tool metadata and execution support
- `/api/skills` - skill discovery and routing
- `/api/history` - persisted chat history
- `/api/archive` - generated chat archive access
- `/api/notifications` - runtime notifications
- `/api/bridge` and `/api/relay` - remote/relay integration surfaces

Generated chat archive files are served from:

```text
/tenderclaw/chats
/tenderclaw/chats/{path}
```

## Repository Layout

```text
backend/
  api/                 FastAPI routers
  agents/              agent registry and definitions
  core/                conversation loop, streaming, skills, prompts
  hooks/               lifecycle hook system
  migrations/          settings/state migrations
  orchestration/       intent gate, role routing, coordinator logic
  plugins/             plugin integrations
  runtime/             runtime state and accounting
  schemas/             pydantic models and wire contracts
  services/            persistence, provider routing, history, telemetry helpers
  services/providers/  model provider adapters
  telemetry/           tracing, metrics, logging integration
  tests/               backend tests
  tools/               built-in tools and registries

frontend/
  src/api/             API and WebSocket clients
  src/components/      chat, layout, tools, settings, history screens
  src/keybindings/     keyboard shortcut system
  src/sdk/             frontend SDK types/client
  src/stores/          Zustand stores
  src/styles/          global styles
```

## Session Storage

By default, TenderClaw stores chat sessions under:

```text
~/workspace_tenderclaw/chat/{session_id}/conversation.json
~/workspace_tenderclaw/chat/{session_id}/metadata.json
```

Attachments and generated chat archive assets live next to the session files.
The UI history and archive views read from this workspace.

## Worktree Hygiene

Generated or local-only state should stay out of Git:

- `.env`
- `.codex`
- `.tenderclaw/`
- `.tenderclaw.pid`
- `frontend/dist/`
- `frontend/*.tsbuildinfo`
- `tenderclaw*.log`
- `uv.lock` in this local workflow

Before sharing a patch, prefer small, reviewable slices:

1. backend runtime fix
2. frontend UI change
3. provider/model routing change
4. persistence/history change
5. test-only or tooling change

Each slice should include the narrowest practical verification command.

## Troubleshooting

If the backend exits during startup:

```bash
uv run python -c "import backend.main; print('backend.main import ok')"
```

If frontend build fails:

```bash
cd frontend
npm run build
```

If broad non-e2e pytest fails on browser tests, check that browser tests are
marked `e2e` and that optional Playwright imports are guarded with
`pytest.importorskip`.

If a local model provider is not selected as expected, check:

- the selected provider in Settings
- the model name prefix
- the provider diagnostics route
- the local server base URL in `.env`

## License

No license file is currently included. Add one before publishing or accepting
external contributions.
