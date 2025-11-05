"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""
from asyncio import gather
from io import BytesIO
from json import loads
from os import remove
from secrets import choice
from traceback import format_exc

from pyrogram import filters
from pyrogram.types import Chat, Message

from wbb import LOG_GROUP_ID, SUDOERS, USERBOT_ID, USERBOT_PREFIX, HAS_USERBOT
from wbb import aiohttpsession as session
from wbb import app, app2
from wbb.modules.userbot import eor
from wbb.utils.functions import extract_user

# No-op decorator when userbot is disabled/absent
if app2 is not None and HAS_USERBOT:
    ubot_on_message = app2.on_message
else:
    def ubot_on_message(*args, **kwargs):
        def _wrap(func):
            return func
        return _wrap


@ubot_on_message(
    filters.command("anonymize", prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & SUDOERS
)
async def change_profile(_, message: Message):
    if app2 is None:
        return
    m = await eor(message, text="Anonymizing...")
    try:
        image_resp, name_resp = await gather(
            session.get("https://thispersondoesnotexist.com/image"),
            session.get(
                "https://raw.githubusercontent.com/dominictarr/random-name/master/first-names.json"
            ),
        )
        image = BytesIO(await image_resp.read())
        image.name = "a.png"
        name = choice(loads(await name_resp.text()))
        await gather(
            app2.set_profile_photo(photo=image),
            app2.update_profile(first_name=name),
        )
    except Exception:
        e = format_exc()
        err = await app.send_message(LOG_GROUP_ID, text=f"`{e}`")
        return await m.edit(f"**Error**: {err.link}")
    await m.edit(f"[Anonymized.](tg://user?id={USERBOT_ID})")
    image.close()


@ubot_on_message(
    filters.command("impersonate", prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & SUDOERS
)
async def impersonate(_, message: Message):
    if app2 is None:
        return
    user_id = await extract_user(message)

    if not user_id:
        return await eor(message, text="Can't impersonate an anonymous user.")
    if user_id == USERBOT_ID:
        return await eor(message, text="Can't impersonate myself.")

    m = await eor(message, text="Processing...")

    try:
        user: Chat = await app2.get_chat(user_id)
        fname = user.first_name
        lname = user.last_name or ""
        bio = user.bio or ""
        pfp, _ = await gather(
            app2.download_media(user.photo.big_file_id),
            app2.update_profile(fname, lname, bio),
        )
        await app2.set_profile_photo(photo=pfp)
        remove(pfp)
    except Exception:
        e = format_exc()
        err = await app.send_message(LOG_GROUP_ID, text=f"`{e}`")
        return await m.edit(f"**Error**: {err.link}")

    await m.edit(f"[Done](tg://user?id={USERBOT_ID})")
