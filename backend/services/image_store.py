"""Image Store — persist uploaded images to disk alongside session data."""

from __future__ import annotations

import base64
import logging
import re
from pathlib import Path
from typing import Any

from backend.services.workspace import get_session_dir

logger = logging.getLogger("tenderclaw.services.image_store")


def _extract_image_data(source: str) -> tuple[str | None, bytes | None]:
    """Extract mime type and raw bytes from a data URL or file path.

    Returns (mime_type, raw_bytes) or (None, None) if not extractable.
    """
    # Handle data URLs: data:image/png;base64,...
    if source.startswith("data:"):
        match = re.match(r"data:([\w.+-]+/[\w.+-]+);base64,(.+)", source)
        if match:
            mime_type = match.group(1)
            raw_b64 = match.group(2)
            try:
                return mime_type, base64.b64decode(raw_b64)
            except Exception as exc:
                logger.warning("Failed to decode image data URL: %s", exc)
    # Handle file paths (already saved)
    elif Path(source).is_file():
        try:
            return None, Path(source).read_bytes()
        except Exception as exc:
            logger.warning("Failed to read image file %s: %s", source, exc)
    return None, None


def save_image(session_id: str, index: int, name: str, mime_type: str, raw_data: bytes) -> str | None:
    """Save a single image to disk. Returns the saved path or None on failure."""
    try:
        # Derive extension from mime type
        ext_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/bmp": ".bmp",
            "image/svg+xml": ".svg",
            "image/tiff": ".tiff",
        }
        ext = ext_map.get(mime_type, ".png")

        # Sanitize name
        safe_name = re.sub(r"[^\w\-.]", "_", name or f"image_{index}")
        file_name = f"{safe_name}{ext}" if not name.endswith(ext) else f"{safe_name}"

        session_dir = get_session_dir(session_id, create=True)

        file_path = session_dir / file_name
        # Avoid overwriting — add index suffix if needed
        counter = 1
        while file_path.exists():
            stem = file_path.stem
            file_path = session_dir / f"{stem}_{counter}{ext}"
            counter += 1

        file_path.write_bytes(raw_data)
        logger.info("Saved image %s → %s (%d bytes)", file_name, file_path, len(raw_data))
        return str(file_path)
    except Exception as exc:
        logger.error("Failed to save image for session %s: %s", session_id, exc)
        return None


def extract_and_save_images(session_id: str, content: Any) -> list[dict[str, Any]]:
    """Extract ImageBlocks from message content, save them to disk.

    Returns the modified content with images replaced by file references.
    Preserves original image data for API calls while also persisting files.
    """
    if not isinstance(content, list):
        return content

    saved_refs = []
    new_content = []

    for block in content:
        # Handle dict blocks (from deserialized JSON)
        if isinstance(block, dict):
            if block.get("type") == "image":
                source = block.get("source", "")
                mime_type = block.get("mime_type", "image/png")
                name = block.get("name", f"upload_{len(saved_refs)}")

                mime, raw_data = _extract_image_data(source)
                if raw_data:
                    saved_path = save_image(session_id, len(saved_refs), name, mime or mime_type, raw_data)
                    if saved_path:
                        saved_refs.append({
                            "original_source": source,
                            "saved_path": saved_path,
                            "mime_type": mime or mime_type,
                            "name": name,
                        })

                # Keep original block for API use (base64 stays in memory)
                new_content.append(block)
            else:
                new_content.append(block)
        else:
            # Handle Pydantic model blocks
            if hasattr(block, "type") and str(getattr(block, "type", "")) == "image":
                source = getattr(block, "source", "")
                mime_type = getattr(block, "mime_type", "image/png")
                name = getattr(block, "name", f"upload_{len(saved_refs)}")

                mime, raw_data = _extract_image_data(source)
                if raw_data:
                    saved_path = save_image(session_id, len(saved_refs), name, mime or mime_type, raw_data)
                    if saved_path:
                        saved_refs.append({
                            "original_source": source,
                            "saved_path": saved_path,
                            "mime_type": mime or mime_type,
                            "name": name,
                        })

                new_content.append(block)
            else:
                new_content.append(block)

    return new_content


def get_session_images(session_id: str) -> list[dict]:
    """List all images saved for a session."""
    session_dir = get_session_dir(session_id)
    if not session_dir.exists():
        return []

    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".tiff"}
    results = []
    for f in sorted(session_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in image_extensions:
            results.append({
                "name": f.name,
                "path": str(f),
                "size_bytes": f.stat().st_size,
            })
    return results


def delete_session_images(session_id: str) -> int:
    """Delete all images for a session. Returns count deleted."""
    session_dir = get_session_dir(session_id)
    if not session_dir.exists():
        return 0

    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".tiff"}
    count = 0
    for f in session_dir.iterdir():
        if f.is_file() and f.suffix.lower() in image_extensions:
            f.unlink()
            count += 1

    # Remove dir if empty
    try:
        if not any(session_dir.iterdir()):
            session_dir.rmdir()
    except OSError:
        pass
    return count


# Module-level convenience — called from conversation engine after user message
def persist_images_for_session(session_id: str, content: Any) -> list[dict[str, Any]]:
    """Public entry point: extract and save images from a user message."""
    return extract_and_save_images(session_id, content)
