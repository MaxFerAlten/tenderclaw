"""Channel Gateway — use TenderClaw from messaging platforms.

Provides interfaces and managers to bridge TenderClaw with:
- Telegram (via Bot API)
- Discord (via Bot API)
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import TYPE_CHECKING, Any

import websockets
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger("tenderclaw.api.channels")

router = APIRouter()


class IncomingMessage(BaseModel):
    """Normalized incoming message from any platform."""

    channel_id: str
    user_id: str
    content: str
    platform: str = "custom"


class ChannelManager(ABC):
    """Abstract base for channel managers."""

    platform: str

    @abstractmethod
    async def start(self) -> None:
        """Initialize and start the channel listener."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop the channel."""
        ...

    @abstractmethod
    async def send_message(self, channel_id: str, content: str) -> None:
        """Send a message to a channel."""
        ...


class TelegramManager(ChannelManager):
    """Telegram Bot API integration."""

    platform = "telegram"

    def __init__(self, bot_token: str | None = None) -> None:
        self._token = bot_token
        self._offset = 0
        self._running = False
        self._poll_task: asyncio.Task | None = None
        self._message_handler: Callable[[IncomingMessage], Awaitable[None]] | None = None

    def set_handler(self, handler: Callable[[IncomingMessage], Awaitable[None]]) -> None:
        """Set the callback for incoming messages."""
        self._message_handler = handler

    async def start(self) -> None:
        """Start polling for Telegram updates."""
        if not self._token:
            logger.warning("Telegram bot token not configured")
            return

        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Telegram polling started")

    async def stop(self) -> None:
        """Stop polling."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._poll_task
        logger.info("Telegram polling stopped")

    async def send_message(self, channel_id: str, content: str) -> None:
        """Send a message via Telegram Bot API."""
        if not self._token:
            return

        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{self._token}/sendMessage",
                json={
                    "chat_id": channel_id,
                    "text": content,
                    "parse_mode": "Markdown",
                },
                timeout=10.0,
            )

    async def _poll_loop(self) -> None:
        """Poll for Telegram updates every second."""
        while self._running:
            try:
                await self._poll()
            except Exception as exc:
                logger.error("Telegram poll error: %s", exc)
            await asyncio.sleep(1)

    async def _poll(self) -> None:
        """Fetch and process Telegram updates."""
        import httpx

        if not self._token:
            return

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.telegram.org/bot{self._token}/getUpdates",
                    params={
                        "offset": self._offset,
                        "timeout": 30,
                    },
                    timeout=35.0,
                )
                data = response.json()

                if data.get("ok"):
                    for update in data.get("result", []):
                        self._offset = update["update_id"] + 1
                        await self._process_update(update)
            except httpx.TimeoutException:
                logger.debug("Telegram long-poll timeout (normal, retrying)")

    async def _process_update(self, update: dict[str, Any]) -> None:
        """Process a single Telegram update."""
        if "message" not in update:
            return

        msg = update["message"]
        chat_id = str(msg["chat"]["id"])
        text = msg.get("text", "")
        user_id = str(msg["from"]["id"])

        incoming = IncomingMessage(
            channel_id=chat_id,
            user_id=user_id,
            content=text,
            platform="telegram",
        )

        if self._message_handler:
            await self._message_handler(incoming)


class DiscordManager(ChannelManager):
    """Discord Bot API integration."""

    platform = "discord"

    def __init__(self, token: str | None = None) -> None:
        self._token = token
        self._websocket = None
        self._running = False
        self._message_handler: Callable[[IncomingMessage], Awaitable[None]] | None = None
        self._session_id: int | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._gateway_task: asyncio.Task | None = None

    def set_handler(self, handler: Callable[[IncomingMessage], Awaitable[None]]) -> None:
        """Set the callback for incoming messages."""
        self._message_handler = handler

    async def start(self) -> None:
        """Start Discord bot gateway connection."""
        if not self._token:
            logger.warning("Discord bot token not configured")
            return

        self._running = True
        self._gateway_task = asyncio.create_task(self._gateway_loop())
        logger.info("Discord gateway started")

    async def stop(self) -> None:
        """Stop Discord connection."""
        self._running = False
        if self._gateway_task:
            self._gateway_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._gateway_task
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        logger.info("Discord gateway stopped")

    async def send_message(self, channel_id: str, content: str) -> None:
        """Send a message via Discord API."""
        if not self._token:
            return

        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                json={"content": content},
                headers={
                    "Authorization": f"Bot {self._token}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )

    async def _gateway_loop(self) -> None:
        """Main gateway loop for Discord."""

        import httpx

        gateway_url = "https://discord.com/api/v10/gateway"

        async with httpx.AsyncClient() as client:
            response = await client.get(gateway_url)
            gateway = response.json()["url"]

        import websockets

        while self._running:
            try:
                async with websockets.connect(f"{gateway}?v=10&encoding=json") as ws:
                    await self._handle_websocket(ws)
            except Exception as exc:
                logger.error("Discord websocket error: %s", exc)
                await asyncio.sleep(5)

    async def _handle_websocket(self, ws: Any) -> None:
        """Handle Discord websocket events."""
        import json

        while self._running:
            try:
                data = await ws.recv()
                event = json.loads(data)

                op = event.get("op")

                if op == 10:  # Hello
                    await ws.send(json.dumps({
                        "op": 2,
                        "d": {
                            "token": self._token,
                            "intents": 1 << 0,  # Guilds
                            "properties": {"$os": "linux", "$browser": "tenderclaw", "$device": "tenderclaw"}
                        }
                    }))
                elif op == 11:  # Heartbeat ACK
                    pass
                elif op == 0:  # Dispatch
                    await self._handle_dispatch(event)

            except websockets.exceptions.ConnectionClosed:
                break
            except Exception as exc:
                logger.error("Discord event error: %s", exc)

    async def _handle_dispatch(self, event: dict[str, Any]) -> None:
        """Handle Discord dispatch events."""
        t = event.get("t")
        data = event.get("d", {})

        if t == "MESSAGE_CREATE":
            if data.get("author", {}).get("bot"):
                return

            channel_id = data["channel_id"]
            content = data.get("content", "")
            user_id = data["author"]["id"]

            if not content:
                return

            incoming = IncomingMessage(
                channel_id=channel_id,
                user_id=user_id,
                content=content,
                platform="discord",
            )

            if self._message_handler:
                await self._message_handler(incoming)


# Module-level instances
telegram_manager = TelegramManager()
discord_manager = DiscordManager()


@router.post("/webhook/{platform}")
async def generic_webhook(platform: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Universal webhook for platform integrations."""
    logger.info("Received webhook for %s", platform)
    return {"status": "received", "platform": platform}


@router.post("/telegram/webhook")
async def telegram_webhook(background_tasks: BackgroundTasks, update: dict[str, Any]) -> dict[str, Any]:
    """Telegram webhook endpoint (alternative to polling)."""
    await telegram_manager._process_update(update)
    return {"ok": True}


async def _handle_channel_message(msg: IncomingMessage) -> None:
    """Route incoming channel messages to the conversation engine."""
    from backend.core.conversation import run_conversation_turn
    from backend.services.session_store import session_store

    # Find or create session for this user
    session = session_store.get_or_create(
        session_id=f"{msg.platform}_{msg.user_id}",
        working_directory=".",
    )
    session.model = "claude-sonnet"

    # Run the conversation turn
    await run_conversation_turn(
        session=session,
        user_content=msg.content,
        send=lambda x: _send_channel_response(msg.channel_id, msg.platform, x),
    )


async def _send_channel_response(channel_id: str, platform: str, event: dict[str, Any]) -> None:
    """Send WebSocket events as channel messages."""
    event_type = event.get("type", "")

    if event_type == "assistant_text":
        text = event.get("delta", "")
        if text:
            if platform == "telegram":
                await telegram_manager.send_message(channel_id, text)
            elif platform == "discord":
                await discord_manager.send_message(channel_id, text)


# Set up message handlers
telegram_manager.set_handler(_handle_channel_message)
discord_manager.set_handler(_handle_channel_message)
