"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""
import asyncio

from pyrogram import filters
from pyrogram.types import Message

from wbb import BOT_ID, SUDOERS, USERBOT_ID, app, app2, HAS_USERBOT
from wbb.core.decorators.errors import capture_err

__MODULE__ = "Pipes"
__HELP__ = """
**THIS MODULE IS ONLY FOR DEVS**

Use this module to create a pipe that will forward messages of one chat/channel to another.


/activate_pipe [FROM_CHAT_ID] [TO_CHAT_ID] [BOT|USERBOT]

    Active a pipe.

    choose 'BOT' or 'USERBOT' according to your needs,
    this will decide which client will fetch the
    message from 'FROM_CHAT'.


/deactivate_pipe [FROM_CHAT_ID]
    Deactivete a pipe.


/show_pipes
    Show all the active pipes.

**NOTE:**
    These pipes are only temporary, and will be destroyed
    on restart.
"""
pipes_list_bot = {}
pipes_list_userbot = {}

# ---- userbot decorator shim (no-op if userbot is disabled/absent) ----
if app2 is not None and HAS_USERBOT:
    ubot_on_message = app2.on_message
else:
    def ubot_on_message(*args, **kwargs):
        def _wrap(func):
            return func
        return _wrap


@app.on_message(~filters.me, group=500)
@capture_err
async def pipes_worker_bot(_, message: Message):
    chat_id = message.chat.id
    if chat_id in pipes_list_bot:
        await message.forward(pipes_list_bot[chat_id])


@ubot_on_message(~filters.me, group=500)
@capture_err
async def pipes_worker_userbot(_, message: Message):
    if app2 is None:
        return
    chat_id = message.chat.id

    # fixed: check the correct dict for userbot pipes
    if chat_id in pipes_list_userbot:
        caption = f"\n\nForwarded from `{chat_id}`"
        to_chat_id = pipes_list_userbot[chat_id]

        if not message.text:
            # keep original structure/logic
            m, temp = await asyncio.gather(
                app.listen(USERBOT_ID),  # leave as-is to preserve behavior
                message.copy(BOT_ID),
            )
            caption = f"{temp.caption}{caption}" if getattr(temp, "caption", None) else caption

            await app.copy_message(
                to_chat_id,
                USERBOT_ID,
                m.id,
                caption=caption,
            )
            await asyncio.sleep(2)
            return await temp.delete()

        await app.send_message(to_chat_id, text=message.text + caption)


@app.on_message(filters.command("activate_pipe") & SUDOERS)
@capture_err
async def activate_pipe_func(_, message: Message):
    global pipes_list_bot, pipes_list_userbot

    if len(message.command) != 4:
        return await message.reply(
            "**Usage:**\n/activate_pipe [FROM_CHAT_ID] [TO_CHAT_ID] [BOT|USERBOT]"
        )

    text = message.text.strip().split()

    from_chat = int(text[1])
    to_chat = int(text[2])
    fetcher = text[3].lower()

    if fetcher not in ["bot", "userbot"]:
        return await message.reply("Wrong fetcher, see help menu.")

    if from_chat in pipes_list_bot or from_chat in pipes_list_userbot:
        return await message.reply_text("This pipe is already active.")

    dict_ = pipes_list_bot if fetcher == "bot" else pipes_list_userbot
    dict_[from_chat] = to_chat
    await message.reply_text("Activated pipe.")


@app.on_message(filters.command("deactivate_pipe") & SUDOERS)
@capture_err
async def deactivate_pipe_func(_, message: Message):
    global pipes_list_bot, pipes_list_userbot

    if len(message.command) != 2:
        await message.reply_text("**Usage:**\n/deactivate_pipe [FROM_CHAT_ID]")
        return
    text = message.text.strip().split()
    from_chat = int(text[1])

    if from_chat not in pipes_list_bot and from_chat not in pipes_list_userbot:
        return await message.reply_text("This pipe is already inactive.")

    dict_ = pipes_list_bot if from_chat in pipes_list_bot else pipes_list_userbot
    del dict_[from_chat]
    await message.reply_text("Deactivated pipe.")


@app.on_message(filters.command("pipes") & SUDOERS)
@capture_err
async def show_pipes_func(_, message: Message):
    # Present a merged view without mutating the dicts
    merged = {**pipes_list_bot, **pipes_list_userbot}
    if not merged:
        return await message.reply_text("No pipe is active.")

    text = ""
    for count, (src, dst) in enumerate(merged.items(), 1):
        text += f"**Pipe:** `{count}`\n**From:** `{src}`\n**To:** `{dst}`\n\n"
    await message.reply_text(text)
