"""E2E tests for Telegram and Discord channel integrations.

Tests the full message flow: incoming platform message → normalization →
session lookup → conversation routing → outbound response delivery.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.api.channels import (
    ChannelManager,
    DiscordManager,
    IncomingMessage,
    TelegramManager,
    _handle_channel_message,
    _send_channel_response,
)


# ── IncomingMessage Schema ──────────────────────────────────────────


class TestIncomingMessage:
    def test_create_message(self):
        msg = IncomingMessage(
            channel_id="123",
            user_id="456",
            content="hello",
            platform="telegram",
        )
        assert msg.channel_id == "123"
        assert msg.user_id == "456"
        assert msg.content == "hello"
        assert msg.platform == "telegram"

    def test_default_platform(self):
        msg = IncomingMessage(channel_id="1", user_id="2", content="hi")
        assert msg.platform == "custom"

    def test_empty_content(self):
        msg = IncomingMessage(channel_id="1", user_id="2", content="")
        assert msg.content == ""


# ── TelegramManager ─────────────────────────────────────────────────


class TestTelegramManager:
    def test_init_no_token(self):
        tm = TelegramManager()
        assert tm._token is None
        assert tm._running is False

    def test_init_with_token(self):
        tm = TelegramManager(bot_token="test_token_123")
        assert tm._token == "test_token_123"

    def test_set_handler(self):
        tm = TelegramManager()
        handler = AsyncMock()
        tm.set_handler(handler)
        assert tm._message_handler is handler

    @pytest.mark.asyncio
    async def test_start_no_token_logs_warning(self):
        tm = TelegramManager()
        await tm.start()
        assert tm._running is False
        assert tm._poll_task is None

    @pytest.mark.asyncio
    async def test_start_with_token(self):
        tm = TelegramManager(bot_token="test_token")
        # Mock the poll loop to prevent actual HTTP calls
        with patch.object(tm, "_poll_loop", new_callable=AsyncMock):
            await tm.start()
            assert tm._running is True
            assert tm._poll_task is not None
            # Cleanup
            await tm.stop()

    @pytest.mark.asyncio
    async def test_stop(self):
        tm = TelegramManager(bot_token="test_token")
        tm._running = True
        tm._poll_task = asyncio.create_task(asyncio.sleep(100))
        await tm.stop()
        assert tm._running is False

    @pytest.mark.asyncio
    async def test_send_message_no_token(self):
        tm = TelegramManager()
        # Should silently return without error
        await tm.send_message("123", "hello")

    @pytest.mark.asyncio
    async def test_send_message(self):
        tm = TelegramManager(bot_token="bot_abc")
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            await tm.send_message("12345", "Hello from TenderClaw")

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "bot_abc/sendMessage" in call_args[0][0]
            assert call_args[1]["json"]["chat_id"] == "12345"
            assert call_args[1]["json"]["text"] == "Hello from TenderClaw"
            assert call_args[1]["json"]["parse_mode"] == "Markdown"

    @pytest.mark.asyncio
    async def test_process_update_text_message(self):
        tm = TelegramManager(bot_token="test")
        handler = AsyncMock()
        tm.set_handler(handler)

        update = {
            "update_id": 100,
            "message": {
                "message_id": 1,
                "chat": {"id": 999},
                "from": {"id": 42, "first_name": "Test"},
                "text": "Hello bot",
            },
        }

        await tm._process_update(update)

        handler.assert_called_once()
        msg = handler.call_args[0][0]
        assert isinstance(msg, IncomingMessage)
        assert msg.channel_id == "999"
        assert msg.user_id == "42"
        assert msg.content == "Hello bot"
        assert msg.platform == "telegram"

    @pytest.mark.asyncio
    async def test_process_update_no_message(self):
        tm = TelegramManager(bot_token="test")
        handler = AsyncMock()
        tm.set_handler(handler)

        # Update without "message" key (e.g., edited_message, callback_query)
        await tm._process_update({"update_id": 101})
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_update_no_handler(self):
        tm = TelegramManager(bot_token="test")
        # No handler set — should not crash
        update = {
            "update_id": 100,
            "message": {
                "message_id": 1,
                "chat": {"id": 999},
                "from": {"id": 42},
                "text": "Hello",
            },
        }
        await tm._process_update(update)  # should not raise

    @pytest.mark.asyncio
    async def test_process_update_empty_text(self):
        tm = TelegramManager(bot_token="test")
        handler = AsyncMock()
        tm.set_handler(handler)

        update = {
            "update_id": 102,
            "message": {
                "message_id": 2,
                "chat": {"id": 999},
                "from": {"id": 42},
                # no "text" key — e.g., photo-only message
            },
        }
        await tm._process_update(update)
        handler.assert_called_once()
        msg = handler.call_args[0][0]
        assert msg.content == ""

    @pytest.mark.asyncio
    async def test_poll_updates_offset(self):
        """Verify offset advances after processing updates."""
        tm = TelegramManager(bot_token="bot_test")
        handler = AsyncMock()
        tm.set_handler(handler)
        assert tm._offset == 0

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "result": [
                {
                    "update_id": 500,
                    "message": {
                        "message_id": 1,
                        "chat": {"id": 100},
                        "from": {"id": 1},
                        "text": "msg1",
                    },
                },
                {
                    "update_id": 501,
                    "message": {
                        "message_id": 2,
                        "chat": {"id": 100},
                        "from": {"id": 1},
                        "text": "msg2",
                    },
                },
            ],
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            await tm._poll()

        assert tm._offset == 502  # last update_id + 1
        assert handler.call_count == 2

    @pytest.mark.asyncio
    async def test_poll_timeout_handled(self):
        """Timeout during long-poll should not crash."""
        tm = TelegramManager(bot_token="bot_test")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            mock_client_cls.return_value = mock_client

            await tm._poll()  # should not raise


# ── DiscordManager ───────────────────────────────────────────────────


class TestDiscordManager:
    def test_init_no_token(self):
        dm = DiscordManager()
        assert dm._token is None
        assert dm._running is False

    def test_init_with_token(self):
        dm = DiscordManager(token="discord_token_xyz")
        assert dm._token == "discord_token_xyz"

    def test_set_handler(self):
        dm = DiscordManager()
        handler = AsyncMock()
        dm.set_handler(handler)
        assert dm._message_handler is handler

    @pytest.mark.asyncio
    async def test_start_no_token_logs_warning(self):
        dm = DiscordManager()
        await dm.start()
        assert dm._running is False

    @pytest.mark.asyncio
    async def test_stop(self):
        dm = DiscordManager()
        dm._running = True
        dm._heartbeat_task = asyncio.create_task(asyncio.sleep(100))
        await dm.stop()
        assert dm._running is False

    @pytest.mark.asyncio
    async def test_send_message_no_token(self):
        dm = DiscordManager()
        await dm.send_message("chan_id", "hello")  # should not raise

    @pytest.mark.asyncio
    async def test_send_message(self):
        dm = DiscordManager(token="bot_token_abc")
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            await dm.send_message("channel_789", "Hello Discord")

            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "channels/channel_789/messages" in call_args[0][0]
            assert call_args[1]["json"]["content"] == "Hello Discord"
            assert "Bot bot_token_abc" in call_args[1]["headers"]["Authorization"]

    @pytest.mark.asyncio
    async def test_handle_dispatch_message_create(self):
        dm = DiscordManager(token="test")
        handler = AsyncMock()
        dm.set_handler(handler)

        event = {
            "t": "MESSAGE_CREATE",
            "d": {
                "channel_id": "ch_001",
                "content": "Hello from Discord",
                "author": {"id": "user_42", "bot": False},
            },
        }

        await dm._handle_dispatch(event)

        handler.assert_called_once()
        msg = handler.call_args[0][0]
        assert isinstance(msg, IncomingMessage)
        assert msg.channel_id == "ch_001"
        assert msg.user_id == "user_42"
        assert msg.content == "Hello from Discord"
        assert msg.platform == "discord"

    @pytest.mark.asyncio
    async def test_handle_dispatch_ignores_bot_messages(self):
        dm = DiscordManager(token="test")
        handler = AsyncMock()
        dm.set_handler(handler)

        event = {
            "t": "MESSAGE_CREATE",
            "d": {
                "channel_id": "ch_001",
                "content": "Bot reply",
                "author": {"id": "bot_99", "bot": True},
            },
        }

        await dm._handle_dispatch(event)
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_dispatch_ignores_empty_content(self):
        dm = DiscordManager(token="test")
        handler = AsyncMock()
        dm.set_handler(handler)

        event = {
            "t": "MESSAGE_CREATE",
            "d": {
                "channel_id": "ch_001",
                "content": "",
                "author": {"id": "user_1", "bot": False},
            },
        }

        await dm._handle_dispatch(event)
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_dispatch_non_message_event(self):
        dm = DiscordManager(token="test")
        handler = AsyncMock()
        dm.set_handler(handler)

        event = {
            "t": "GUILD_MEMBER_ADD",
            "d": {"user": {"id": "123"}},
        }

        await dm._handle_dispatch(event)
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_dispatch_no_handler(self):
        dm = DiscordManager(token="test")
        # No handler set
        event = {
            "t": "MESSAGE_CREATE",
            "d": {
                "channel_id": "ch_001",
                "content": "test",
                "author": {"id": "user_1", "bot": False},
            },
        }
        await dm._handle_dispatch(event)  # should not raise


# ── Channel Message Routing (E2E flow) ──────────────────────────────


class TestChannelMessageRouting:
    """Tests the full message routing: platform → session → conversation → response."""

    @pytest.mark.asyncio
    async def test_handle_channel_message_creates_session(self):
        msg = IncomingMessage(
            channel_id="tg_chat_100",
            user_id="tg_user_42",
            content="Write a hello world",
            platform="telegram",
        )

        with patch("backend.core.conversation.run_conversation_turn", new_callable=AsyncMock) as mock_conv:
            with patch("backend.services.session_store.session_store") as mock_ss:
                mock_session = MagicMock()
                mock_ss.get_or_create.return_value = mock_session

                await _handle_channel_message(msg)

                mock_ss.get_or_create.assert_called_once_with(
                    session_id="telegram_tg_user_42",
                    working_directory=".",
                )
                assert mock_session.model == "claude-sonnet"
                mock_conv.assert_called_once()
                call_kwargs = mock_conv.call_args
                assert call_kwargs[1]["session"] is mock_session
                assert call_kwargs[1]["user_content"] == "Write a hello world"

    @pytest.mark.asyncio
    async def test_handle_channel_message_discord_session_id(self):
        msg = IncomingMessage(
            channel_id="dc_chan",
            user_id="dc_user_7",
            content="test",
            platform="discord",
        )

        with patch("backend.core.conversation.run_conversation_turn", new_callable=AsyncMock):
            with patch("backend.services.session_store.session_store") as mock_ss:
                mock_ss.get_or_create.return_value = MagicMock()

                await _handle_channel_message(msg)

                mock_ss.get_or_create.assert_called_once_with(
                    session_id="discord_dc_user_7",
                    working_directory=".",
                )


class TestSendChannelResponse:
    """Tests outbound response delivery to platforms."""

    @pytest.mark.asyncio
    async def test_send_telegram_text(self):
        with patch("backend.api.channels.telegram_manager") as mock_tm:
            mock_tm.send_message = AsyncMock()

            await _send_channel_response(
                "chat_123",
                "telegram",
                {"type": "assistant_text", "delta": "Hello!"},
            )

            mock_tm.send_message.assert_called_once_with("chat_123", "Hello!")

    @pytest.mark.asyncio
    async def test_send_discord_text(self):
        with patch("backend.api.channels.discord_manager") as mock_dm:
            mock_dm.send_message = AsyncMock()

            await _send_channel_response(
                "chan_456",
                "discord",
                {"type": "assistant_text", "delta": "Hi Discord!"},
            )

            mock_dm.send_message.assert_called_once_with("chan_456", "Hi Discord!")

    @pytest.mark.asyncio
    async def test_ignore_non_text_events(self):
        with patch("backend.api.channels.telegram_manager") as mock_tm:
            mock_tm.send_message = AsyncMock()

            # turn_start event — should be ignored
            await _send_channel_response(
                "chat_123",
                "telegram",
                {"type": "turn_start", "turn_number": 1},
            )

            mock_tm.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignore_empty_delta(self):
        with patch("backend.api.channels.telegram_manager") as mock_tm:
            mock_tm.send_message = AsyncMock()

            await _send_channel_response(
                "chat_123",
                "telegram",
                {"type": "assistant_text", "delta": ""},
            )

            mock_tm.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_platform_no_crash(self):
        # Unknown platform should silently do nothing
        await _send_channel_response(
            "chan",
            "slack",
            {"type": "assistant_text", "delta": "msg"},
        )


# ── Webhook Endpoints ───────────────────────────────────────────────


class TestWebhookEndpoints:
    """Test the FastAPI webhook routes."""

    @pytest.mark.asyncio
    async def test_telegram_webhook_endpoint(self):
        from backend.api.channels import telegram_webhook

        update = {
            "update_id": 200,
            "message": {
                "message_id": 5,
                "chat": {"id": 777},
                "from": {"id": 88},
                "text": "webhook test",
            },
        }

        with patch.object(
            TelegramManager, "_process_update", new_callable=AsyncMock
        ) as mock_process:
            # BackgroundTasks mock
            bg = MagicMock()
            result = await telegram_webhook(bg, update)
            assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_generic_webhook_endpoint(self):
        from backend.api.channels import generic_webhook

        result = await generic_webhook("slack", {"event": "message"})
        assert result["status"] == "received"
        assert result["platform"] == "slack"


# ── Full E2E: Telegram update → outbound message ────────────────────


class TestTelegramE2E:
    """Full end-to-end: Telegram update arrives → processed → response sent back."""

    @pytest.mark.asyncio
    async def test_telegram_update_to_response(self):
        """Simulate a complete Telegram message flow."""
        tm = TelegramManager(bot_token="test_bot_token")
        sent_messages: list[tuple[str, str]] = []

        async def capture_send(channel_id: str, content: str) -> None:
            sent_messages.append((channel_id, content))

        tm.send_message = capture_send  # type: ignore

        # Wire a handler that simulates the conversation engine producing a response
        async def mock_handler(msg: IncomingMessage) -> None:
            # Simulate what _handle_channel_message does, but skip real conversation
            await _send_channel_response(
                msg.channel_id,
                msg.platform,
                {"type": "assistant_text", "delta": f"Echo: {msg.content}"},
            )

        tm.set_handler(mock_handler)

        update = {
            "update_id": 300,
            "message": {
                "message_id": 10,
                "chat": {"id": 12345},
                "from": {"id": 99},
                "text": "ping",
            },
        }

        with patch("backend.api.channels.telegram_manager", tm):
            await tm._process_update(update)

        assert len(sent_messages) == 1
        assert sent_messages[0] == ("12345", "Echo: ping")


class TestDiscordE2E:
    """Full end-to-end: Discord MESSAGE_CREATE → response sent back."""

    @pytest.mark.asyncio
    async def test_discord_message_to_response(self):
        """Simulate a complete Discord message flow."""
        dm = DiscordManager(token="test_discord_token")
        sent_messages: list[tuple[str, str]] = []

        async def capture_send(channel_id: str, content: str) -> None:
            sent_messages.append((channel_id, content))

        dm.send_message = capture_send  # type: ignore

        async def mock_handler(msg: IncomingMessage) -> None:
            await _send_channel_response(
                msg.channel_id,
                msg.platform,
                {"type": "assistant_text", "delta": f"Reply: {msg.content}"},
            )

        dm.set_handler(mock_handler)

        event = {
            "t": "MESSAGE_CREATE",
            "d": {
                "channel_id": "discord_ch_42",
                "content": "hello bot",
                "author": {"id": "user_7", "bot": False},
            },
        }

        with patch("backend.api.channels.discord_manager", dm):
            await dm._handle_dispatch(event)

        assert len(sent_messages) == 1
        assert sent_messages[0] == ("discord_ch_42", "Reply: hello bot")

    @pytest.mark.asyncio
    async def test_discord_bot_message_ignored_e2e(self):
        """Bot messages should never trigger a response."""
        dm = DiscordManager(token="test")
        sent_messages: list[tuple[str, str]] = []

        async def capture_send(channel_id: str, content: str) -> None:
            sent_messages.append((channel_id, content))

        dm.send_message = capture_send  # type: ignore

        async def mock_handler(msg: IncomingMessage) -> None:
            await _send_channel_response(
                msg.channel_id,
                msg.platform,
                {"type": "assistant_text", "delta": "should not appear"},
            )

        dm.set_handler(mock_handler)

        event = {
            "t": "MESSAGE_CREATE",
            "d": {
                "channel_id": "ch",
                "content": "bot noise",
                "author": {"id": "bot_1", "bot": True},
            },
        }

        with patch("backend.api.channels.discord_manager", dm):
            await dm._handle_dispatch(event)

        assert len(sent_messages) == 0


# ── ChannelManager ABC ──────────────────────────────────────────────


class TestChannelManagerABC:
    def test_telegram_is_channel_manager(self):
        assert issubclass(TelegramManager, ChannelManager)
        assert TelegramManager.platform == "telegram"

    def test_discord_is_channel_manager(self):
        assert issubclass(DiscordManager, ChannelManager)
        assert DiscordManager.platform == "discord"
