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
            ObjectId(val)  # Validate ObjectId-like values (not Telegram IDs)
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

    users = await get_served_users()
    chats = await get_served_chats()

    # ✅ Proper ID extraction and deduplication
    user_ids = sorted(set(uid for u in users if (uid := safe_get_id(u, "user_id", "_id"))))
    chat_ids = sorted(set(cid for c in chats if (cid := safe_get_id(c, "group_id"))))

    if mode == "all":
        targets = user_ids + chat_ids
    elif mode == "users":
        targets = user_ids
    elif mode == "chats":
        targets = chat_ids
    else:
        return await message.reply_text(BROADCAST_USAGE)

    if not targets:
        return await message.reply_text("No valid targets found to broadcast.")

    total_users = len(user_ids)
    total_chats = len(chat_ids)
    total_targets = len(targets)

    m = await message.reply_text(
        f"📢 **Starting broadcast...**\n"
        f"👤 Users: `{total_users}` | 👥 Groups: `{total_chats}`\n"
        f"🧩 Total: `{total_targets}`\n"
        f"🪄 Mode: `{'Copy' if to_copy else 'Forward'}`"
    )

    sent = failed = 0
    invalid = set()
    progress_update_interval = 50 # Update every 50 messages

    async def send_to_target(target_id):
        nonlocal sent, failed
        try:
            if to_copy:
                await reply_message.copy(target_id)
            else:
                await reply_message.forward(target_id)
            sent += 1
            # Live progress update every 100 successful sends
            if sent % progress_update_interval == 0:
                try:
                    await m.edit_text(
                        f"📡 Broadcasting in progress...\n"
                        f"📤 Sent: `{sent}` | ⚠️ Failed: `{failed}`\n"
                        f"👤 Users: `{total_users}` | 👥 Groups: `{total_chats}`\n"
                        f"🧩 Total Targets: `{total_targets}`"
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

    await asyncio.gather(*(sem_task(tid) for tid in set(targets)))

    result_msg = (
        f"✅ **Broadcast Completed**\n\n"
        f"📤 Sent: `{sent}`\n"
        f"⚠️ Failed: `{failed}`\n\n"
        f"👤 Users: `{total_users}`\n"
        f"👥 Groups: `{total_chats}`\n"
        f"🧩 Total Targets: `{total_targets}`\n"
        f"🪄 Mode: `{'Copy' if to_copy else 'Forward'}`"
    )

    if invalid:
        result_msg += f"\n\n⛔ Invalid IDs skipped: `{len(invalid)}`"

    await m.edit(result_msg)


@app.on_message(filters.command("ubroadcast") & SUDOERS)
@capture_err
async def user_broadcast(_, message):
    reply_message = message.reply_to_message
    if not reply_message:
        return await message.reply_text("Reply to a message to broadcast it.")

    to_copy = "copy" in message.text.lower()
    users = await get_served_users()

    user_ids = sorted(set(uid for u in users if (uid := safe_get_id(u, "user_id", "_id"))))
    if not user_ids:
        return await message.reply_text("No valid users found in database.")

    m = await message.reply_text(f"📢 Broadcasting to `{len(user_ids)}` users...")

    sent = failed = 0
    invalid = set()
    progress_update_interval = 50

    async def send_user(uid):
        nonlocal sent, failed
        try:
            if to_copy:
                await reply_message.copy(uid)
            else:
                await reply_message.forward(uid)
            sent += 1
            if sent % progress_update_interval == 0:
                try:
                    await m.edit_text(
                        f"📡 Broadcasting in progress...\n"
                        f"📤 Sent: `{sent}` | ⚠️ Failed: `{failed}`\n"
                        f"👤 Total Users: `{len(user_ids)}`"
                    )
                except Exception:
                    pass
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await send_user(uid)
        except Forbidden:
            failed += 1
            invalid.add(uid)
        except Exception:
            failed += 1

    sem = asyncio.Semaphore(10)

    async def sem_task(uid):
        async with sem:
            await send_user(uid)
            await asyncio.sleep(0.2)

    await asyncio.gather(*(sem_task(uid) for uid in set(user_ids)))

    await m.edit(
        f"✅ **User Broadcast Completed**\n\n"
        f"📤 Sent: `{sent}`\n"
        f"⚠️ Failed: `{failed}`\n"
        f"👤 Total Users: `{len(user_ids)}`\n"
        f"🪄 Mode: `{'Copy' if to_copy else 'Forward'}`"
    )
