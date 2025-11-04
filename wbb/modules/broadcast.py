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
    """Safely extract numeric ID from MongoDB documents."""
    val = entry.get(key1)
    if not val and key2:
        val = entry.get(key2)
    if not val:
        return None
    try:
        # If it's already an int-like string, cast it
        return int(val)
    except (TypeError, ValueError):
        # Try decoding if it's an ObjectId
        try:
            if isinstance(val, ObjectId):
                # You can decode timestamp if you want, but it’s not a Telegram ID
                return None
            # Sometimes val is string form of ObjectId
            ObjectId(val)  # validate
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

    # ✅ Proper ID extraction
    user_ids = [uid for u in users if (uid := safe_get_id(u, "user_id", "_id"))]
    chat_ids = [cid for c in chats if (cid := safe_get_id(c, "group_id"))]

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

    m = await message.reply_text(
        f"📢 Starting broadcast to {len(targets)} targets...\n"
        f"Mode: `{mode}` | Type: `{'Copy' if to_copy else 'Forward'}`"
    )

    sent = failed = 0
    invalid = []

    async def send_to_target(target_id):
        nonlocal sent, failed
        try:
            if to_copy:
                await reply_message.copy(target_id)
            else:
                await reply_message.forward(target_id)
            sent += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await send_to_target(target_id)
        except Forbidden:
            failed += 1
            invalid.append(target_id)
        except Exception:
            failed += 1

    sem = asyncio.Semaphore(20)

    async def sem_task(tid):
        async with sem:
            await send_to_target(tid)
            await asyncio.sleep(0.1)

    await asyncio.gather(*(sem_task(tid) for tid in targets))

    result_msg = (
        f"✅ Broadcast Completed\n"
        f"📤 Sent: `{sent}`\n"
        f"⚠️ Failed/Invalid: `{failed}`\n"
        f"🧩 Total Targets: `{len(targets)}`"
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

    user_ids = [uid for u in users if (uid := safe_get_id(u, "user_id", "_id"))]
    if not user_ids:
        return await message.reply_text("No valid users found in database.")

    m = await message.reply_text(f"📢 Broadcasting to {len(user_ids)} users...")

    sent = failed = 0
    invalid = []

    async def send_user(uid):
        nonlocal sent, failed
        try:
            if to_copy:
                await reply_message.copy(uid)
            else:
                await reply_message.forward(uid)
            sent += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await send_user(uid)
        except Forbidden:
            failed += 1
            invalid.append(uid)
        except Exception:
            failed += 1

    sem = asyncio.Semaphore(20)

    async def sem_task(uid):
        async with sem:
            await send_user(uid)
            await asyncio.sleep(0.1)

    await asyncio.gather(*(sem_task(uid) for uid in user_ids))

    await m.edit(
        f"✅ User Broadcast Completed\n"
        f"📤 Sent: `{sent}`\n"
        f"⚠️ Failed/Invalid: `{failed}`\n"
        f"🧩 Total Users: `{len(user_ids)}`"
    )
