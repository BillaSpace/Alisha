"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""

from pyrogram import filters

from wbb import BOT_USERNAME, SUDOERS, USERBOT_PREFIX, app2, HAS_USERBOT
from wbb.modules.userbot import eor

# no-op decorator when userbot is disabled/absent
if app2 is not None and HAS_USERBOT:
    ubot_on_message = app2.on_message
else:
    def ubot_on_message(*args, **kwargs):
        def _wrap(func):
            return func
        return _wrap


@ubot_on_message(
    SUDOERS
    & ~filters.forwarded
    & ~filters.via_bot
    & filters.command("create", prefixes=USERBOT_PREFIX)
)
async def create(_, message):
    if app2 is None:
        return
    if len(message.command) < 3:
        return await eor(message, text="__**.create (b|s|c) Name**__")

    group_type = (message.command[1] or "").lower()
    split = message.command[2:]
    group_name = " ".join(split).strip()
    if not group_name:
        return await eor(message, text="__**.create (b|s|c) Name**__")

    desc = "Welcome To My " + ("Supergroup" if group_type == "s" else "Channel")

    if group_type == "b":  # basicgroup
        chat = await app2.create_group(group_name, BOT_USERNAME)
        link = await app2.get_chat(chat.id)
        return await eor(
            message,
            text=f"**Basicgroup Created: [{group_name}]({link.invite_link})**",
            disable_web_page_preview=True,
        )

    if group_type == "s":  # supergroup
        chat = await app2.create_supergroup(group_name, desc)
        link = await app2.get_chat(chat.id)
        return await eor(
            message,
            text=f"**Supergroup Created: [{group_name}]({link.invite_link})**",
            disable_web_page_preview=True,
        )

    if group_type == "c":  # channel
        chat = await app2.create_channel(group_name, desc)
        link = await app2.get_chat(chat.id)
        return await eor(
            message,
            text=f"**Channel Created: [{group_name}]({link.invite_link})**",
            disable_web_page_preview=True,
        )

    # invalid group type
    return await eor(message, text="__**.create (b|s|c) Name**__")
