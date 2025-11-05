"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""
from pykeyboard import InlineKeyboard
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, Message

from wbb import (
    BOT_ID,
    LOG_GROUP_ID,
    LOG_MENTIONS,
    USERBOT_ID,
    USERBOT_NAME,
    USERBOT_USERNAME,
    app,
    app2,
    HAS_USERBOT,  # <- added
)
from wbb.core.decorators.errors import capture_err
from wbb.utils.filter_groups import taglog_group

IS_USERBOT_ONLINE = False

# ---- userbot decorator shims (no-op if userbot is disabled/absent) ----
if app2 is not None and HAS_USERBOT:
    ubot_on_message = app2.on_message
    # some pyrogram builds expose on_user_status; guard in case it doesn't exist
    ubot_on_user_status = getattr(app2, "on_user_status", None) or (lambda *a, **k: (lambda f: f))
else:
    def ubot_on_message(*args, **kwargs):
        def _wrap(func):
            return func
        return _wrap

    def ubot_on_user_status(*args, **kwargs):
        def _wrap(func):
            return func
        return _wrap


@ubot_on_user_status()
async def statusUpdaterFunc(_, update):
    # if userbot disabled, this won't be registered
    if USERBOT_ID is None:
        return
    if getattr(update, "id", None) != USERBOT_ID:
        return
    global IS_USERBOT_ONLINE
    if getattr(update, "status", None) == "online":
        IS_USERBOT_ONLINE = True
        return
    IS_USERBOT_ONLINE = False


async def sendLog(message: Message):
    # build a safe text preview (avoid .markdown attribute which may not exist)
    raw_text = message.text or message.caption or None
    # escape backticks to avoid formatting issues
    if isinstance(raw_text, str):
        safe_text = raw_text.replace("`", "ˋ")
    else:
        safe_text = None

    uid = message.from_user.id if message.from_user else None
    uname = message.from_user.mention if message.from_user else None

    msg = (
        f"**User:** {uname} [`{uid}`]\n"
        f"**Text:** {safe_text}\n"
        f"**Chat:** {getattr(message.chat, 'title', None)} [`{message.chat.id}`]\n"
        f"**Bot:** {getattr(message.from_user, 'is_bot', None)}\n"
    )

    button = InlineKeyboard(row_width=1)
    button.add(InlineKeyboardButton(text="Check Action", url=message.link))
    await app.send_message(
        LOG_GROUP_ID,
        text=msg,
        reply_markup=button,
        disable_web_page_preview=True,
    )


@ubot_on_message(
    ~filters.me
    & ~filters.chat([LOG_GROUP_ID, BOT_ID])
    & ~filters.private
    & ~filters.forwarded
    & ~filters.via_bot,
    group=taglog_group,
)
@capture_err
async def tagLoggerFunc(_, message: Message):
    # if userbot disabled, this won't be registered
    if not LOG_MENTIONS:
        return
    if IS_USERBOT_ONLINE:
        return

    # case 1: replies to userbot
    if message.reply_to_message:
        reply_message = message.reply_to_message
        if reply_message.from_user and USERBOT_ID is not None:
            if reply_message.from_user.id == USERBOT_ID:
                return await sendLog(message)

    # case 2: mentions/text contains our ubot identity (guard Nones)
    text = message.text or message.caption
    if not text:
        return

    hit = False
    if USERBOT_ID is not None and str(USERBOT_ID) in text:
        hit = True
    elif USERBOT_USERNAME and str(USERBOT_USERNAME) in text:
        hit = True
    elif USERBOT_NAME and USERBOT_NAME in text:
        hit = True

    if hit:
        await sendLog(message)
