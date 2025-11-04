import asyncio
import os
import subprocess
import time

import psutil
from pyrogram import filters, types
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup

from wbb import (
    BOT_ID,
    GBAN_LOG_GROUP_ID,
    SUDOERS,
    USERBOT_USERNAME,
    app,
    bot_start_time,
)
from wbb.core.decorators.errors import capture_err
from wbb.utils import formatter
from wbb.utils.dbfunctions import (
    add_gban_user,
    is_gbanned_user,
    remove_gban_user,
    get_gbans_count,
)
from wbb.utils.functions import extract_user, extract_user_and_reason, restart

__MODULE__ = "Sudoers"
__HELP__ = """
/stats - To Check System Status.

/gstats - To Check Bot's Global Stats.

/gban - To Ban A User Globally.

/ungban - to Unban a Globally banned user

/gbanlist - lists all gbanned users if have

/clean_db - Clean database.( sudoers dont try )

/broadcast - To Broadcast A Message To All Groups.

/ubroadcast - To Broadcast A Message To All Users.

/update - To Update And Restart The Bot

/restart - To Restart the bot

/eval - Execute Python Code

/sh - Execute Shell Code
"""


# Stats Module


async def bot_sys_stats():
    bot_uptime = int(time.time() - bot_start_time)
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    process = psutil.Process(os.getpid())
    stats = f"""
{USERBOT_USERNAME}@Alisha 
------------------
UPTIME: {formatter.get_readable_time(bot_uptime)}
BOT: {round(process.memory_info()[0] / 1024 ** 2)} MB
CPU: {cpu}%
RAM: {mem}%
DISK: {disk}%
"""
    return stats

@app.on_message(filters.command("gban") & SUDOERS)
@capture_err
async def ban_globally(_, message):
    user_id, reason = await extract_user_and_reason(message)

    if not user_id:
        return await message.reply_text("I can't find that user.")
    if not reason:
        return await message.reply("No reason provided.")

    try:
        user = await app.get_users(int(user_id))
    except Exception:
        return await message.reply_text("Invalid user, unable to fetch details.")

    from_user = message.from_user

    if user.id in [from_user.id, BOT_ID] or user.id in SUDOERS:
        return await message.reply_text("I can't ban that user.")

    served_chats = await get_served_chats()
    m = await message.reply_text(
        f"**Banning {user.mention} Globally!**\n"
        f"**This Action Should Take About {len(served_chats)} Seconds.**"
    )

    await add_gban_user(user.id)
    number_of_chats = 0

    for served_chat in served_chats:
        try:
            chat_id = int(served_chat.get("group_id") or served_chat.get("chat_id"))
            chat_member = await app.get_chat_member(chat_id, user.id)
            if chat_member.status == ChatMemberStatus.MEMBER:
                await app.ban_chat_member(chat_id, user.id)
                number_of_chats += 1
            await asyncio.sleep(1)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            pass

    try:
        await app.send_message(
            user.id,
            f"Hello, You have been globally banned by {from_user.mention}.\n"
            "You can appeal for this ban by contacting them.",
        )
    except Exception:
        pass

    await m.edit(f"Banned {user.mention} Globally!")

    ban_text = f"""
__**New Global Ban**__
**Origin:** {message.chat.title} [`{message.chat.id}`]
**Admin:** {from_user.mention}
**Banned User:** {user.mention}
**Banned User ID:** `{user.id}`
**Reason:** __{reason}__
**Chats Affected:** `{number_of_chats}`
"""

    try:
        m2 = await app.send_message(
            GBAN_LOG_GROUP_ID,
            text=ban_text,
            disable_web_page_preview=True,
        )
        await m.edit(
            f"Banned {user.mention} Globally!\nAction Log: {m2.link}",
            disable_web_page_preview=True,
        )
    except Exception:
        await message.reply_text(
            "User Gbanned, But This Gban Action Wasn't Logged — Add Me In GBAN_LOG_GROUP"
        )


@app.on_message(filters.command("ungban") & SUDOERS)
@capture_err
async def unban_globally(_, message):
    user_id = await extract_user(message)
    if not user_id:
        return await message.reply_text("I can't find that user.")

    try:
        user = await app.get_users(int(user_id))
    except Exception:
        return await message.reply_text("Invalid user.")

    is_gbanned = await is_gbanned_user(user.id)
    if not is_gbanned:
        return await message.reply_text("I don't remember Gbanning them.")

    await remove_gban_user(user.id)
    await message.reply_text(f"✅ Lifted {user.mention}'s Global Ban.")


@app.on_message(filters.command("gbanlist") & SUDOERS)
@capture_err
async def gban_list(_, message):
    count = await get_gbans_count()
    if count == 0:
        return await message.reply_text("There are no globally banned users.")

    msg = "**Globally Banned Users:**\n"
    async for user in gbansdb.find({}):
        user_id = user["_id"]
        msg += f"• `{user_id}`\n"

    if len(msg) > 4096:
        with open("gbanlist.txt", "w") as f:
            f.write(msg)
        await message.reply_document("gbanlist.txt")
        os.remove("gbanlist.txt")
    else:
        await message.reply_text(msg)

@app.on_message(filters.command("gupdate") & SUDOERS)
async def update_restart(_, message):
    try:
        out = subprocess.check_output(["git", "pull"]).decode("UTF-8")
        if "Already up to date." in str(out):
            return await message.reply_text("Its already up-to date!")
        await message.reply_text(f"```{out}```")
    except Exception as e:
        return await message.reply_text(str(e))
    m = await message.reply_text(
        "**Updated with default branch, restarting now.**"
    )
    await restart(m)


@app.on_message(filters.command("grestart") & SUDOERS)
async def update_restart(_, message):
    m = await message.reply_text(
        "**Bot is restarting now.**"
    )
    await restart(m)
