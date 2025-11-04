import asyncio
from pyrogram import filters
from pyrogram.errors import FloodWait, Forbidden
from bson import ObjectId

from wbb import app, SUDOERS
from wbb.core.decorators.errors import capture_err
from wbb.utils.dbfunctions import get_served_chats, get_served_users

BROADCAST_USAGE = """⚠️ Usage: /broadcast [all|users|chats] [copy]
• all: Broadcast to all users and groups
• users: Only users
• chats: Only groups/channels
• copy: Send as copy (no forward tag)
"""


def safe_get_id(entry, key1, key2=None):
    """Safely extract numeric Telegram ID from MongoDB documents."""
    val = entry.get(key1)
    if not val and key2:
        val = entry.get(key2)
    if not val:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        try:
            ObjectId(val)
            return None
        except Exception:
            return None


@app.on_message(filters.command("broadcast") & SUDOERS)
@capture_err
async def broadcast_message(_, message):
    args = message.text.split()
    if len(args) < 2:
        return await message.reply_text(BROADCAST_USAGE)

    mode = args[1].lower()
    to_copy = "copy" in args
    reply_message = message.reply_to_message

    if not reply_message:
        return await message.reply_text("Reply to a message to broadcast it.")

    # Fetch data
    users = await get_served_users()
    chats = await get_served_chats()

    # Extract valid IDs
    user_ids = sorted(set(uid for u in users if (uid := safe_get_id(u, "user_id", "_id"))))
    chat_ids = sorted(set(cid for c in chats if (cid := safe_get_id(c, "group_id"))))

    # Determine broadcast targets
    if mode == "users":
        targets = user_ids
    elif mode == "chats":
        targets = chat_ids
    elif mode == "all":
        targets = user_ids + chat_ids
    else:
        return await message.reply_text(BROADCAST_USAGE)

    if not targets:
        return await message.reply_text("No valid targets found to broadcast.")

    total_users = len(user_ids)
    total_chats = len(chat_ids)

    m = await message.reply_text(
        f"📢 **Starting broadcast...**\n"
        f"👤 Users: `{total_users}` | 👥 Groups: `{total_chats}`\n"
        f"🧩 Sending to: `{len(targets)}` targets\n"
        f"🪄 Mode: `{'Copy' if to_copy else 'Forward'}`"
    )

    sent = failed = 0
    invalid = set()
    progress_update_interval = 50

    async def send_to_target(target_id):
        nonlocal sent, failed
        try:
            if to_copy:
                await reply_message.copy(target_id)
            else:
                await reply_message.forward(target_id)
            sent += 1
            if sent % progress_update_interval == 0:
                try:
                    await m.edit_text(
                        f"📡 Broadcasting...\n"
                        f"📤 Sent: `{sent}` | ⚠️ Failed: `{failed}`\n"
                        f"🧩 Total: `{len(targets)}`"
                    )
                except Exception:
                    pass
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await send_to_target(target_id)
        except Forbidden:
            failed += 1
            invalid.add(target_id)
        except Exception:
            failed += 1

    sem = asyncio.Semaphore(10)

    async def sem_task(tid):
        async with sem:
            await send_to_target(tid)
            await asyncio.sleep(0.2)

    # Broadcast only to the intended list
    await asyncio.gather(*(sem_task(tid) for tid in targets))

    result_msg = (
        f"✅ **Broadcast Completed**\n\n"
        f"📤 Sent: `{sent}`\n"
        f"⚠️ Failed: `{failed}`\n\n"
        f"👤 Users: `{total_users}`\n"
        f"👥 Groups: `{total_chats}`\n"
        f"🧩 Targets Used: `{len(targets)}`\n"
        f"🪄 Mode: `{'Copy' if to_copy else 'Forward'}`"
    )

    if invalid:
        result_msg += f"\n\n⛔ Invalid IDs skipped: `{len(invalid)}`"

    await m.edit(result_msg)
