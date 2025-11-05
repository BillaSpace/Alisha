from asyncio import sleep

from pyrogram import filters
from pyrogram.types import Message

from wbb import SUDOERS, USERBOT_PREFIX, app2, eor, HAS_USERBOT
from wbb.core.sections import section

# no-op decorator when userbot is disabled/absent
if app2 is not None and HAS_USERBOT:
    ubot_on_message = app2.on_message
else:
    def ubot_on_message(*args, **kwargs):
        def _wrap(func):
            return func
        return _wrap


@ubot_on_message(
    filters.command("parse_preview", prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & SUDOERS
)
async def parse(_, message: Message):
    if app2 is None:
        return

    r = message.reply_to_message
    has_wpp = False
    if not r:
        return await eor(message, text="Reply to a message with a webpage")

    m_ = await eor(message, text="Parsing...")

    if not getattr(r, "web_page", None):
        text = r.text or r.caption
        if text:
            m = await app2.send_message("me", text)
            await sleep(1)
            await m.delete()
            if getattr(m, "web_page", None):
                r = m
                has_wpp = True
    else:
        has_wpp = True

    if not has_wpp:
        return await m_.edit("Replied message has no webpage preview.")

    wpp = r.web_page

    body = {
        "Title": [wpp.title or "Null"],
        "Description": [(wpp.description[:50] + "...") if wpp.description else "Null"],
        "URL": [wpp.display_url or "Null"],
        "Author": [wpp.author or "Null"],
        "Site Name": [wpp.site_name or "Null"],
        "Type": wpp.type or "Null",
    }

    text = section("Preview", body)

    t = wpp.type

    if t == "photo":
        media = wpp.photo
        func = app2.send_photo
    elif t == "audio":
        media = wpp.audio
        func = app2.send_audio
    elif t == "video":
        media = wpp.video
        func = app2.send_video
    elif t == "document":
        media = wpp.document
        func = app2.send_document
    else:
        media = None
        func = None

    if media and func:
        await m_.delete()
        return await func(
            m_.chat.id,
            media.file_id,
            caption=text,
        )

    await m_.edit(text, disable_web_page_preview=True)
