"""Channel Gateway — use TenderClaw from messaging platforms.

Provides a generic interface and HTTP/Webhook endpoints to bridge
TenderClaw with Telegram, Discord, Slack, etc.
"""

import logging
from typing import Any, Protocol

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger("tenderclaw.api.channels")
router = APIRouter()


@router.post("/webhook/{platform}")
async def generic_webhook(platform: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Universal webhook for platform integrations."""
    logger.info("Received webhook for %s: %s", platform, payload)
    return {"status": "received", "platform": platform}


class IncomingMessage(BaseModel):
    """Normalized incoming message from any platform."""

    channel_id: str
    user_id: str
    content: str
    platform: str = "custom"


class Channel(Protocol):
    """Interface for a Messaging Channel."""

    platform: str
    enabled: bool

    async def send_message(self, channel_id: str, content: str) -> None:
        """Send a message back to the user."""
        ...


class ChannelGateway:
    """Manages all external messaging channels."""

    def __init__(self) -> None:
        self._channels: dict[str, Channel] = {}

    def register(self, channel: Channel) -> None:
        """Add a channel implementation."""
        self._channels[channel.platform] = channel

    async def handle_incoming(self, msg: IncomingMessage) -> None:
        """Process an incoming message and route it to the Conversation Engine."""
        logger.info("Incoming message from %s [%s]: %s", msg.platform, msg.user_id, msg.content[:50])
        # Phase 5+: Logic to spawn/find session for the user and run turn.


class TelegramChannel(Channel):
    """Stub implementation for Telegram."""
    
    platform = "telegram"
    enabled = False

    async def send_message(self, channel_id: str, content: str) -> None:
        logger.info("Telegram: Sending msg to %s: %s", channel_id, content[:50])


# Module-level instance
channel_gateway = ChannelGateway()
channel_gateway.register(TelegramChannel())
