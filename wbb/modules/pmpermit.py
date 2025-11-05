"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""

from pyrogram import filters
from pyrogram.raw.functions.messages import DeleteHistory

from wbb import (
    BOT_ID,
    PM_PERMIT,
    SUDOERS,
    USERBOT_ID,
    USERBOT_PREFIX,
    app,
    app2,
    eor,
    HAS_USERBOT,  # <- added
)
from wbb.core.decorators.errors import capture_err
from wbb.utils.dbfunctions import (
    approve_pmpermit,
    disapprove_pmpermit,
    is_pmpermit_approved,
)

flood = {}

# ---- userbot decorator shim (no-op if userbot is disabled/absent) ----
if app2 is not None and HAS_USERBOT:
    ubot_on_message = app2.on_message
else:
    def ubot_on_message(*args, **kwargs):
        def _wrap(func):
            return func
        return _wrap


@ubot_on_message(
    filters.private
    & filters.incoming
    & ~filters.service
    & ~filters.me
    & ~filters.bot
    & ~filters.via_bot
    & ~SUDOERS
)
@capture_err
async def pmpermit_func(_, message):
    if app2 is None:
        return
    user_id = message.from_user.id
    if not PM_PERMIT or await is_pmpermit_approved(user_id):
        return
    async for m in app2.get_chat_history(user_id, limit=6):
        if m.reply_markup:
            try:
                await m.delete()
            except Exception:
                pass
    key = str(user_id)
    flood[key] = flood.get(key, 0) + 1
    if flood[key] > 5:
        await message.reply_text("SPAM DETECTED, BLOCKED USER AUTOMATICALLY!")
        return await app2.block_user(user_id)
    results = await app2.get_inline_bot_results(BOT_ID, f"pmpermit {user_id}")
    await app2.send_inline_bot_result(
        user_id,
        results.query_id,
        results.results[0].id,
    )


@ubot_on_message(
    filters.command("approve", prefixes=USERBOT_PREFIX)
    & SUDOERS
    & ~filters.via_bot
    & ~filters.forwarded
)
@capture_err
async def pm_approve(_, message):
    if app2 is None:
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await eor(message, text="Reply to a user's message to approve.")
    user_id = message.reply_to_message.from_user.id
    if await is_pmpermit_approved(user_id):
        return await eor(message, text="User is already approved to pm")
    await approve_pmpermit(user_id)
    await eor(message, text="User is approved to pm")


@ubot_on_message(
    filters.command("disapprove", prefixes=USERBOT_PREFIX)
    & SUDOERS
    & ~filters.via_bot
    & ~filters.forwarded
)
@capture_err
async def pm_disapprove(_, message):
    if app2 is None:
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await eor(message, text="Reply to a user's message to disapprove.")
    user_id = message.reply_to_message.from_user.id
    if not await is_pmpermit_approved(user_id):
        await eor(message, text="User is already disapproved to pm")
        async for m in app2.get_chat_history(user_id, limit=6):
            if m.reply_markup:
                with capture_err.log_exceptions():
                    await m.delete()
        return
    await disapprove_pmpermit(user_id)
    await eor(message, text="User is disapproved to pm")


@ubot_on_message(
    filters.command("block", prefixes=USERBOT_PREFIX)
    & SUDOERS
    & ~filters.via_bot
    & ~filters.forwarded
)
@capture_err
async def block_user_func(_, message):
    if app2 is None:
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await eor(message, text="Reply to a user's message to block.")
    user_id = message.reply_to_message.from_user.id
    # Edit first so the other side sees it, then block.
    await eor(message, text="Successfully blocked the user")
    await app2.block_user(user_id)


@ubot_on_message(
    filters.command("unblock", prefixes=USERBOT_PREFIX)
    & SUDOERS
    & ~filters.via_bot
    & ~filters.forwarded
)
@capture_err
async def unblock_user_func(_, message):
    if app2 is None:
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await eor(message, text="Reply to a user's message to unblock.")
    user_id = message.reply_to_message.from_user.id
    await app2.unblock_user(user_id)
    await eor(message, text="Successfully Unblocked the user")


# ---------------------- CALLBACK QUERY HANDLER (bot) ----------------------

flood2 = {}


@app.on_callback_query(filters.regex("pmpermit"))
@capture_err
async def pmpermit_cq(_, cq):
    # Short-circuit when userbot is disabled
    if app2 is None or not HAS_USERBOT or USERBOT_ID is None:
        return await cq.answer("Userbot is disabled.", show_alert=True)

    user_id = cq.from_user.id
    try:
        _, data, victim = cq.data.split(None, 2)
    except Exception:
        return await cq.answer("Malformed data.")

    if data == "approve":
        if user_id != USERBOT_ID:
            return await cq.answer("This Button Is Not For You")
        await approve_pmpermit(int(victim))
        return await app.edit_inline_text(
            cq.inline_message_id, "User Has Been Approved To PM."
        )

    if data == "block":
        if user_id != USERBOT_ID:
            return await cq.answer("This Button Is Not For You")
        await cq.answer()
        await app.edit_inline_text(
            cq.inline_message_id, "Successfully blocked the user."
        )
        await app2.block_user(int(victim))
        return await app2.invoke(
            DeleteHistory(
                peer=(await app2.resolve_peer(victim)),
                max_id=0,
                revoke=False,
            )
        )

    # From here on, only non-userbot users should trigger
    if user_id == USERBOT_ID:
        return await cq.answer("It's For The Other Person.")

    if data == "to_scam_you":
        async for m in app2.get_chat_history(user_id, limit=6):
            if m.reply_markup:
                try:
                    await m.delete()
                except Exception:
                    pass
        await app2.send_message(user_id, "Blocked, Go scam someone else.")
        await app2.block_user(user_id)
        return await cq.answer()

    elif data == "approve_me":
        await cq.answer()
        key = str(user_id)
        flood2[key] = flood2.get(key, 0) + 1
        if flood2[key] > 5:
            await app2.send_message(user_id, "SPAM DETECTED, USER BLOCKED.")
            return await app2.block_user(user_id)
        await app2.send_message(
            user_id,
            "I'm busy right now, will approve you shortly, DO NOT SPAM.",
        )
