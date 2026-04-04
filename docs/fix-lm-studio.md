# Fix: LM Studio Integration

Data: 2026-04-04

## Problema iniziale

Impossibile connettersi a LM Studio e ricevere risposte dalla UI di TenderClaw.

---

## Root causes trovati e fix applicati

### 1. Modelli LM Studio hardcoded nella UI (non corrispondevano ai modelli reali)

**File:** `frontend/src/components/screens/SettingsScreen.tsx`

I modelli LM Studio erano hardcoded come `lmstudio-community/*`, `mistral/*`, `phi4/*` — nessuno corrispondeva ai modelli reali (`google/gemma-4-e4b`, `unsloth/qwen3.5-9b`, ecc.).

**Fix:** La UI ora carica i modelli dinamicamente dal backend tramite `GET /api/diagnostics/lmstudio/models` invece di fare fetch diretta a `localhost:1234` (che sarebbe bloccata da CORS).

---

### 2. `POST /api/config` restituiva 404

**File:** `backend/api/router.py`

Il config router era montato con `prefix="/config"` ma i suoi handler avevano già il path `/config` — risultando in `/api/config/config`.

**Fix:**
```python
# Prima
api_router.include_router(config_router, prefix="/config", tags=["config"])
# Dopo
api_router.include_router(config_router, tags=["config"])
```

---

### 3. Il modello selezionato in Settings non veniva propagato alla sessione WS attiva

**File:** `frontend/src/components/screens/SettingsScreen.tsx`, `frontend/src/api/ws.ts`

Dopo il salvataggio delle settings, il modello veniva salvato in localStorage ma la sessione WS già aperta continuava a usare il vecchio modello.

**Fix:** Al salvataggio, viene inviato un `session_config` via WS per aggiornare il modello della sessione attiva in tempo reale. Aggiunto `sendSessionConfig(model)` al WS client.

---

### 4. WebSocket si disconnetteva immediatamente (reconnect loop)

**File:** `frontend/src/components/chat/ChatView.tsx`

Le dipendenze del `useEffect` includevano `handleServerEvent` e `setWsStatus` — funzioni Zustand che cambiano reference ad ogni render. Questo causava un loop infinito: mount → connect → cleanup → disconnect → remount.

**Fix:** Uso di `useRef` per stabilizzare le callback, e dipendenza del `useEffect` solo su `sessionId`:
```tsx
const handleServerEventRef = useRef(handleServerEvent);
handleServerEventRef.current = handleServerEvent;
// useEffect dipende solo da [sessionId]
```

---

### 5. Sessione persa dopo riavvio del backend

**File:** `frontend/src/api/ws.ts`, `frontend/src/stores/sessionStore.ts`

Dopo un riavvio del backend, le sessioni in memoria venivano perse. Il browser tentava di riconnettersi alla sessione inesistente all'infinito (codice `4004`).

**Fix:** Quando il WS riceve `error.code === "session_not_found"`, il frontend resetta lo store (`sessionId = null`) e `ChatView` crea automaticamente una nuova sessione.

---

### 6. Errori del server non visibili nella chat

**File:** `frontend/src/stores/sessionStore.ts`

Gli errori (es. `api_key_missing`) venivano loggati solo in console, non mostrati all'utente.

**Fix:** Gli errori vengono ora inseriti come messaggio assistant visibile nella chat con prefisso `⚠️`.

---

### 7. Intent Gate tentava Anthropic/OpenAI anche con modelli locali

**File:** `backend/orchestration/intent_gate.py`

Il classificatore di intent usava sempre `claude-haiku` per classificare il prompt. Con LM Studio attivo ma senza API key Anthropic, ogni messaggio causava un tentativo fallito verso Anthropic (warning + delay ~2s).

**Fix:** Il classificatore ora sceglie il modello in base alle key disponibili:
- Anthropic key presente → `claude-haiku-4-20250514`
- Solo OpenAI key → `gpt-4o-mini`
- Nessuna key cloud → skip classificazione, default `implement`

---

### 8. WS keepalive mancante

**File:** `frontend/src/api/ws.ts`, `backend/api/ws.py`

Il browser chiudeva la connessione WS dopo ~8-10 secondi di inattività (durante la generazione LM Studio), causando `WebSocketDisconnect code=1006` lato backend.

**Fix:** Aggiunto ping ogni 15 secondi dal client, con handler `pong` sul backend:
```typescript
// Client: ping ogni 15s
setInterval(() => ws.send({ type: "ping" }), 15000);
```
```python
# Backend: risponde al ping
elif msg_type == "ping":
    await send({"type": "pong"})
```

---

### 9. Nuovo endpoint `/api/diagnostics/lmstudio/models`

**File:** `backend/api/diagnostics.py`

Aggiunto endpoint che restituisce la lista dei modelli LM Studio come array JSON, usato dalla UI per il caricamento dinamico. Evita il problema CORS del fetch diretto dal browser.

---

### 10. Script di avvio e certificazione

- `start.bat` / `start.sh`: buildano il frontend e avviano il backend con supporto `stop`
- `_certify.py`: script Playwright che certifica end-to-end che TenderClaw risponde via UI usando `google/gemma-4-e4b`

---

## Test E2E

File: `backend/tests/test_e2e_lmstudio.py`

3 test automatizzati:
1. `test_lmstudio_diagnostics` — verifica che LM Studio sia raggiungibile e `google/gemma-4-e4b` sia caricato
2. `test_lmstudio_ws_roundtrip` — crea sessione, invia messaggio via WS, verifica risposta non vuota
3. `test_settings_ui_lmstudio` — Playwright: seleziona modello in Settings, salva, invia messaggio, verifica risposta

Tutti e 3 passano: `3 passed in ~11s`

---

## Note operative

- La OpenAI key nel `.env` era invalida (401) — causava un delay di ~2s ad ogni messaggio per il tentativo di classificazione fallito. Commentarla o aggiornarla.
- Il backend serve il frontend buildato da `frontend/dist`. Dopo modifiche al frontend eseguire `npm run build` nella cartella `frontend`.
- Per avviare: `python -m uvicorn backend.main:app --host localhost --port 7000` oppure `start.bat`
- UI disponibile su: `http://localhost:7000/tenderclaw`
