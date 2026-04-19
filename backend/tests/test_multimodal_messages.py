from __future__ import annotations

from backend.api.ws import _image_message_content
from backend.core.conversation import IMAGE_RESPONSE_INSTRUCTIONS, _latest_user_has_image, _to_api_messages
from backend.core.system_prompt import build_system_prompt
from backend.schemas.messages import ImageBlock, Message, Role, TextBlock
from backend.schemas.ws import WSAttachment, WSUserMessage


def test_ws_user_message_accepts_image_attachment() -> None:
    msg = WSUserMessage.model_validate(
        {
            "type": "user_message",
            "content": "what is this?",
            "attachments": [
                {
                    "type": "image/png",
                    "url": "data:image/png;base64,abc123",
                    "name": "screenshot.png",
                    "size_bytes": 42,
                }
            ],
        }
    )

    assert msg.attachments[0].type == "image/png"
    assert msg.attachments[0].size_bytes == 42


def test_image_blocks_convert_to_provider_image_url() -> None:
    api_messages = _to_api_messages(
        [
            Message(
                role=Role.USER,
                content=[
                    TextBlock(text="describe it"),
                    ImageBlock(
                        source="data:image/png;base64,abc123",
                        mime_type="image/png",
                        name="screenshot.png",
                        size_bytes=42,
                    ),
                ],
            )
        ]
    )

    assert api_messages == [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "describe it"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc123"}},
            ],
        }
    ]


def test_image_message_content_builds_multimodal_blocks() -> None:
    blocks = _image_message_content(
        "what changed?",
        [
            WSAttachment(
                type="image/png",
                url="data:image/png;base64,abc123",
                name="screen.png",
                size_bytes=42,
            )
        ],
    )

    assert blocks == [
        TextBlock(text="what changed?"),
        ImageBlock(
            source="data:image/png;base64,abc123",
            mime_type="image/png",
            name="screen.png",
            size_bytes=42,
        ),
    ]


def test_latest_user_image_messages_enable_image_instructions() -> None:
    messages = [
        Message(role=Role.ASSISTANT, content="ready"),
        Message(
            role=Role.USER,
            content=[
                TextBlock(text="analizza questa schermata"),
                ImageBlock(source="data:image/png;base64,abc123", mime_type="image/png"),
            ],
        ),
    ]

    assert _latest_user_has_image(messages)
    assert "same language as the user's text" in IMAGE_RESPONSE_INSTRUCTIONS


def test_base_prompt_keeps_language_and_hides_private_reasoning() -> None:
    prompt = build_system_prompt()

    assert "Reply in the same language as the user's latest message" in prompt
    assert "Do not reveal private reasoning" in prompt
    assert "Never emit hidden-reasoning tags" in prompt
