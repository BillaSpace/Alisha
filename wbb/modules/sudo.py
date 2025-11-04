"""
MIT License

Copyright (c) 2024 TheHamkerCat

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
from pyrogram import filters
from pyrogram.types import Message

from wbb import BOT_ID, SUDOERS, USERBOT_PREFIX, app2, eor
from wbb.core.decorators.errors import capture_err
from wbb.utils.dbfunctions import add_sudo, get_sudoers, remove_sudo

__MODULE__ = "Devs"
__HELP__ = """
**THIS MODULE IS ONLY FOR DEVS**

.addsudo - Add a user to sudoers.
.delsudo - Remove a user from sudoers.
.sudoers - List all sudo users.

**NOTE:**
Never add anyone to sudoers unless you trust them.
Sudo users can run any Shell commands with your bot / UB account or may delete them.
"""


# Add a user to sudoers
@app2.on_message(
    filters.command("addsudo", prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & SUDOERS
)
@capture_err
async def useradd(_, message: Message):
    if not message.reply_to_message:
        return await eor(message, text="Reply to a user's message to add them to sudoers.")

    user = message.reply_to_message.from_user
    user_id = user.id
    mention = user.mention or user.first_name

    if user_id == BOT_ID:
        return await eor(message, text="You can't add the assistant bot to sudoers.")

    sudoers = await get_sudoers()
    if user_id in sudoers:
        return await eor(message, text=f"{mention} is already a sudo user.")

    try:
        await add_sudo(user_id)
        SUDOERS.add(user_id)
        await eor(message, text=f"✅ Successfully added {mention} to sudoers.")
    except Exception as e:
        await eor(message, text=f"⚠️ Failed to add sudo user.\nError: `{e}`")


# Remove a user from sudoers
@app2.on_message(
    filters.command("delsudo", prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & SUDOERS
)
@capture_err
async def userdel(_, message: Message):
    if not message.reply_to_message:
        return await eor(message, text="Reply to a user's message to remove them from sudoers.")

    user = message.reply_to_message.from_user
    user_id = user.id
    mention = user.mention or user.first_name

    sudoers = await get_sudoers()
    if user_id not in sudoers:
        return await eor(message, text=f"{mention} is not in sudoers.")

    try:
        await remove_sudo(user_id)
        if user_id in SUDOERS:
            SUDOERS.remove(user_id)
        await eor(message, text=f"✅ Successfully removed {mention} from sudoers.")
    except Exception as e:
        await eor(message, text=f"⚠️ Failed to remove sudo user.\nError: `{e}`")


#  List sudo users
@app2.on_message(
    filters.command("sudoers", prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & SUDOERS
)
@capture_err
async def sudoers_list(_, message: Message):
    sudoers = await get_sudoers()
    if not sudoers:
        return await eor(message, text="No sudo users found.")

    text = "**🛠️ Sudo Users:**\n\n"
    i = 1

    for user_id in sudoers:
        try:
            user = await app2.get_users(user_id)
            text += f"{i}. {user.mention if user.mention else user.first_name}\n"
            i += 1
        except Exception:
            text += f"{i}. [User ID: `{user_id}`]\n"
            i += 1
            continue

    await eor(message, text=text)
