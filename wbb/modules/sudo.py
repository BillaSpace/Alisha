"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""

from pyrogram import filters
from pyrogram.types import Message

from wbb import BOT_ID, SUDOERS, app
from wbb.core.decorators.errors import capture_err
from wbb.utils.dbfunctions import add_sudo, get_sudoers, remove_sudo


__MODULE__ = "Devs"
__HELP__ = """
**THIS MODULE IS ONLY FOR DEVS**

/addsudo [reply|username|id] - Add a user to sudoers.
/rmsudo [reply|username|id] - Remove a user from sudoers.
/sudoers - List all sudo users.

**NOTE:**
Only trusted people should be given sudo access.
Sudo users can run powerful commands.
"""


# Helper: extract user from reply / argument
async def get_target_user(message: Message):
    if message.reply_to_message:
        return message.reply_to_message.from_user

    if len(message.command) < 2:
        return None

    arg = message.text.split(None, 1)[1]
    try:
        user = await app.get_users(arg)
        return user
    except Exception:
        return None


# Add sudo user
@app.on_message(filters.command("addsudo") & SUDOERS)
@capture_err
async def addsudo_handler(_, message: Message):
    user = await get_target_user(message)
    if not user:
        return await message.reply_text("Reply to a user or provide a valid username/ID.")

    user_id = user.id
    mention = user.mention or user.first_name

    if user_id == BOT_ID:
        return await message.reply_text("You can't add the bot itself to sudoers.")

    sudoers = await get_sudoers()
    if user_id in sudoers:
        return await message.reply_text(f"{mention} is already a sudo user.")

    try:
        await add_sudo(user_id)
        SUDOERS.add(user_id)
        await message.reply_text(f"✅ Successfully added {mention} to sudoers.")
    except Exception as e:
        await message.reply_text(f"⚠️ Failed to add sudo user.\nError: `{e}`")


# Remove sudo user
@app.on_message(filters.command("rmsudo") & SUDOERS)
@capture_err
async def delsudo_handler(_, message: Message):
    user = await get_target_user(message)
    if not user:
        return await message.reply_text("Reply to a user or provide a valid username/ID.")

    user_id = user.id
    mention = user.mention or user.first_name

    sudoers = await get_sudoers()
    if user_id not in sudoers:
        return await message.reply_text(f"{mention} is not a sudo user.")

    try:
        await remove_sudo(user_id)
        SUDOERS.discard(user_id)
        await message.reply_text(f"✅ Successfully removed {mention} from sudoers.")
    except Exception as e:
        await message.reply_text(f"⚠️ Failed to remove sudo user.\nError: `{e}`")


# List sudo users
@app.on_message(filters.command("sudoers") & SUDOERS)
@capture_err
async def sudoers_list(_, message: Message):
    sudoers = await get_sudoers()
    if not sudoers:
        return await message.reply_text("No sudo users found.")

    text = "🛠️ Sudo Users:\n\n"
    for i, user_id in enumerate(sudoers, start=1):
        try:
            user = await app.get_users(user_id)
            name = user.mention or user.first_name
        except Exception:
            name = f"[User ID: `{user_id}`]"
        text += f"{i}. {name}\n"

    text += f"\nTotal : {len(sudoers)} sudo users."
    await message.reply_text(text)
