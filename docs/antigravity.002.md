# Antigravity Report 002: Risoluzione Definitiva Bug OpenCode/Big-Pickle

## Obiettivo 
Stabilizzare l'integrazione del modello `big-pickle` (via provider OpenCode) nel framework TenderClaw. Prima di questi fix, l'abilitazione del modello mandava il backend in freeze, non compilava a schermo nessun testo per l'utente, e faceva loopare l'agente a causa dell'incapacità di processare richieste lunghe e gestire lo storico dei tool.

## Problemi Identificati e Risolti

L'operazione ha richiesto il fix di 5 bug critici incatenati su diverse componenti core del sistema.

### 1. Intent Gate Routing Fallace (Limitante solo per Anthropic)
**Problema:** Nel file `backend/core/conversation.py`, il sistema provava a "classificare" l'intento dell'utente e per i prompt > 100 caratteri deviava l'agente alla `team_pipeline` (creata esclusivamente per i modelli Anthropic). In assenza della chiave Anthropic e utilizzando OpenCode associato a un failback verso "implement", entrava in un blocco di retry in background.
**Soluzione:** Aggiunto un controllo (`_anthropic_native = _provider == "anthropic"`) affinché la deviazione verso la pipeline avvenga *esclusivamente* sui provider che la supportano.

### 2. Timeout di Permission Troppo Breve
**Problema:** L'interazione con l'utente sui permission popup andava in timeout in 30 secondi. Per i tool più pesanti o per un utente che non approva immediatamente il modal pop-up, uno scaduto si rifletteva in "Deny" automatico mandando il LLM in retry-loop confuso e invisibile.
**Soluzione:** Aumentato `PERMISSION_TIMEOUT_SECS` da 30 a 300 secondi nel file `backend/core/tool_runner.py`.

### 3. Parser del Provider Incompatibile (Streaming Chunking)
**Problema:** In `backend/services/providers/opencode_provider.py` lo stream parser accumulava gli ID dei JSON di argomenti supponendo l'arrivo sequenziale. Questo "rompeva" la cattura se il parser generava Parallel Tool Calls portando a json illegibili che non scatenavano l'esecuzione.
**Soluzione:** Rielaborato il parser implementando l'accumulazione basata su indici (`tc.index`), rendendolo pienamente conforme con le reti OpenAI formattando lo spec per multiple tool calls simultanee.

### 4. Blocco Bloccante dell'Event Loop (ASGI ASGI Block)
**Problema:** In `backend/services/model_router.py`, l'avvio della sessione e dei vari turni invocava la funzione `detect_provider()` che, per capire ad esempio se dovesse attivare LMStudio, faceva una chiamata HTTP `urllib` in formato "sync". In server ASGI, bloccava letteralmente l'esecuzione globale.
**Soluzione:** Convertita la funzione via `async def` incapsulando il blocco I/O con un `asyncio.to_thread()`, rendendo tutta l'esecuzione sicura pur restando fully-compatible coi moduli sync python. Modificati di conseguenza i file dipendenti aggregati a lui (`ws.py` e `conversation.py`).

### 5. Loop Infinito (Amnesia del System Prompt sui Tool)  🔥 _La Causa Principale_
**Problema:** Se dopo tutte le correzioni l'agente eseguiva un "Glob", si perdeva ancora. `opencode_provider.py` aveva una funzione di traduzione di messaggi (`_to_api_messages`) che filtrava solo messaggi "text" e "image". Qualsiasi blocco generato per `tool_use` o `tool_result` era filtrato dal payload formattato. Dunque, l'Agente richiedeva "Fammi fare Glob", veniva validato, mandato fuori via WebSocket, ma al turno di ricezione successiva perdeva memoria dello storico di quel result. Rifletteva in ri-chiedere di fare di nuovo lo stesso Tool ad infinitum arrivando a produrre testate log da oltre +95 turni.
**Soluzione:** Rifattorizzato tutto il block scope di traduzione messaggi custom per conformarsi ad OpenAI API. Costruita l'iniezione per i "tool_calls" negli `assistant message` e la traduzione nei role `tool` nei block object `tool_result`.

## Collaudo (E2E Test) 
Alla fine dei bug fixes, ho scatenato l'agente "Browser Subagent" di Antigravity simulando le mosse reali dell'utente sul porto 7000. Il sistema:
- Schedula ed esegue parallel tool calls `Glob` & `Read`
- Genera i modal ed attesa per il tempo esteso.
- Mantiene l'indice esatto su `big-pickle`.
- Genera a video per l'utente, non test in console, stampando una mappatura intera della codebase richiesta (prompt testato: `analizza d:\MY_AI\claude-code\TenderClaw\`).
