"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""
from asyncio import gather
from base64 import b64decode
from io import BytesIO

from pyrogram import filters
from pyrogram.types import Message

from wbb import SUDOERS, USERBOT_PREFIX, app, app2, eor, HAS_USERBOT
from wbb.core.decorators.errors import capture_err
from wbb.utils.http import post

# ---- userbot decorator shim (no-op if userbot is disabled/absent) ----
if app2 is not None and HAS_USERBOT:
    ubot_on_message = app2.on_message
else:
    def ubot_on_message(*args, **kwargs):
        def _wrap(func):
            return func
        return _wrap


async def take_screenshot(url: str, full: bool = False):
    url = "https://" + url if not url.startswith("http") else url
    payload = {
        "url": url,
        "width": 1920,
        "height": 1080,
        "scale": 1,
        "format": "jpeg",
    }
    if full:
        payload["full"] = True
    data = await post(
        "https://webscreenshot.vercel.app/api",
        data=payload,
    )
    if not isinstance(data, dict) or "image" not in data:
        return None
    b = data["image"].replace("data:image/jpeg;base64,", "")
    file = BytesIO(b64decode(b))
    file.name = "webss.jpg"
    return file


@ubot_on_message(
    filters.command("webss", prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & SUDOERS
)
@app.on_message(filters.command("webss"))
@capture_err
async def take_ss(_, message: Message):
    if len(message.command) < 2:
        return await eor(message, text="Give A Url To Fetch Screenshot.")

    if len(message.command) == 2:
        url = message.text.split(None, 1)[1]
        full = False
    elif len(message.command) == 3:
        url = message.text.split(None, 2)[1]
        full = message.text.split(None, 2)[2].lower().strip() in [
            "yes",
            "y",
            "1",
            "true",
        ]
    else:
        return await eor(message, text="Invalid Command.")

    m = await eor(message, text="Capturing screenshot...")

    try:
        photo = await take_screenshot(url, full)
        if not photo:
            return await m.edit("Failed To Take Screenshot")

        await m.edit("Uploading...")

        if not full:
            # Full-size images can be problematic with reply_photo; send both when not full.
            await gather(
                message.reply_document(photo),
                message.reply_photo(photo),
            )
        else:
            await message.reply_document(photo)
        await m.delete()
    except Exception as e:
        await m.edit(str(e))
