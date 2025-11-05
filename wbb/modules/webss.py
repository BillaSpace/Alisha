"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""

from asyncio import gather
from base64 import b64decode
from io import BytesIO
from typing import Optional

from pyrogram import filters
from pyrogram.types import Message

from wbb import SUDOERS, USERBOT_PREFIX, app, app2, eor
from wbb.core.decorators.errors import capture_err
from wbb.utils.http import post


# --- helpers -----------------------------------------------------------------

def _normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return raw
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw

def _to_bytesio(img_b64_data_url: str, *, name: str) -> Optional[BytesIO]:
    """
    Convert a data URL like 'data:image/jpeg;base64,...' to a BytesIO.
    Returns None if malformed.
    """
    if not img_b64_data_url:
        return None
    prefix = "base64,"
    try:
        # Strip potential data URL prefix if present
        idx = img_b64_data_url.find(prefix)
        b64_part = img_b64_data_url[idx + len(prefix):] if idx != -1 else img_b64_data_url
        binary = b64decode(b64_part, validate=False)
    except Exception:
        return None
    bio = BytesIO(binary)
    bio.name = name
    return bio

def _clone_bytesio(src: BytesIO, *, name: Optional[str] = None) -> BytesIO:
    """Create a fresh BytesIO from an existing BytesIO's buffer."""
    src.seek(0)
    clone = BytesIO(src.getvalue())
    clone.name = name or getattr(src, "name", "file.jpg")
    return clone


# --- core --------------------------------------------------------------------

async def take_screenshot(url: str, full: bool = False, *, timeout: int = 20) -> Optional[BytesIO]:
    """
    Calls the screenshot API and returns a JPEG as BytesIO or None on failure.
    """
    url = _normalize_url(url)
    if not url:
        return None

    payload = {
        "url": url,
        "width": 1920,
        "height": 1080,
        "scale": 1,
        "format": "jpeg",
        # the vercel function accepts "full": true to capture full-page
        **({"full": True} if full else {}),
    }

    try:
        data = await post(
            "https://webscreenshot.vercel.app/api",
            data=payload,
            timeout=timeout,
        )
    except Exception:
        return None

    if not isinstance(data, dict) or "image" not in data:
        return None

    file = _to_bytesio(
        data["image"],
        name="webss_full.jpg" if full else "webss.jpg",
    )
    return file


@app2.on_message(
    filters.command("webss", USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & SUDOERS
)
@app.on_message(filters.command("webss"))
@capture_err
async def take_ss(_, message: Message):
    # Usage:
    # /webss <url>
    # /webss <url> <full|yes|true|1>
    if len(message.command) < 2:
        return await eor(message, text="Give a URL to fetch a screenshot.\nExample: `/webss example.com` or `/webss example.com full`")

    # Parse args
    parts = message.text.split(None, 2)
    url = parts[1].strip()
    full = False
    if len(parts) == 3:
        flag = parts[2].lower().strip()
        full = flag in {"yes", "y", "1", "true", "full"}

    m = await eor(message, text="Capturing screenshot...")

    try:
        photo = await take_screenshot(url, full)
        if not photo:
            return await m.edit("Failed to take screenshot. Make sure the URL is reachable.")

        # Telegram size limits: photos ~10MB, documents larger allowed.
        photo.seek(0)
        size_bytes = len(photo.getbuffer())

        await m.edit("Uploading...")

        if full:
            # Full-page images can be large; prefer document.
            await message.reply_document(photo)
        else:
            # Avoid reusing the same BytesIO object twice without cloning.
            # Send as photo (for preview) AND as document (for original).
            # If it's too big for photo, fall back to document only.
            if size_bytes <= 9_500_000:  # ~9.5MB margin for photo
                await gather(
                    message.reply_photo(_clone_bytesio(photo, name="webss.jpg")),
                    message.reply_document(_clone_bytesio(photo, name="webss.jpg")),
                )
            else:
                await message.reply_document(photo)

        # Clean up status message
        await m.delete()
    except Exception as e:
        # Show a concise error
        await m.edit(f"Error: {e.__class__.__name__}: {e}")
