"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""
import os
import re

import aiofiles
from pyrogram import filters
from pyrogram.types import Message

from wbb import app, eor
from wbb.core.decorators.errors import capture_err
from wbb.core.keyboard import ikb
from wbb.utils.pastebin import paste

__MODULE__ = "Paste"
__HELP__ = "/paste - To Paste Replied Text Or Document To A Pastebin"

# allow common text-y mimetypes
pattern = re.compile(r"(?:^text/|json$|yaml$|xml$|toml$|x-sh$|x-shellscript$)", re.I)


@app.on_message(filters.command("paste") & ~filters.forwarded & ~filters.via_bot)
@capture_err
async def paste_func(_, message: Message):
    if not message.reply_to_message:
        return await eor(message, text="Reply to a message with /paste")

    r = message.reply_to_message

    if not r.text and not r.document:
        return await eor(message, text="Only text messages and text files are supported.")

    m = await eor(message, text="Pasting...")

    # Collect content
    if r.text:
        content = r.text
    else:
        # r.document path
        if not getattr(r.document, "mime_type", None) or not pattern.search(r.document.mime_type):
            return await m.edit("Only text files can be pasted.")

        if r.document.file_size and r.document.file_size > 40_000:
            return await m.edit("You can only paste files smaller than 40KB.")

        doc_path = await r.download()
        try:
            async with aiofiles.open(doc_path, mode="r", encoding="utf-8", errors="ignore") as f:
                content = await f.read()
        finally:
            try:
                os.remove(doc_path)
            except Exception:
                pass

    # Do the paste
    link = await paste(content)
    kb = ikb({"Paste Link": link})

    # Try showing a preview image if the paste service returns one; fall back to a captioned link.
    try:
        # When replying as the bot, .from_user is the bot itself — keep both branches but prefer caption.
        await message.reply_photo(
            photo=link,
            quote=False,
            caption=f"**Paste Link:** [Here]({link})",
            reply_markup=kb,
        )
        await m.delete()
    except Exception:
        await m.edit("Here's your paste", reply_markup=kb)
