"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""

from pyrogram import filters
from pyrogram.types import Message

from wbb import BOT_ID, SUDOERS, USERBOT_PREFIX, app2

# ---- userbot decorator shim (no-op if userbot is disabled/absent) ----
if app2 is not None:
    ubot_on_message = app2.on_message
else:
    def ubot_on_message(*args, **kwargs):
        def _wrap(func):
            return func
        return _wrap


@ubot_on_message(
    filters.command("alive", prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & SUDOERS
)
async def alive_command_func(_, message: Message):
    # Only runs if app2 exists (otherwise not registered)
    await message.delete()
    results = await app2.get_inline_bot_results(BOT_ID, "alive")
    await app2.send_inline_bot_result(
        message.chat.id, results.query_id, results.results[0].id
    )
