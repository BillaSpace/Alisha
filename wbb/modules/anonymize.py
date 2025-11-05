from asyncio import gather
from io import BytesIO
from json import loads
from os import remove
from secrets import choice, token_hex
from traceback import format_exc

from pyrogram import filters
from pyrogram.types import Chat, Message

from wbb import LOG_GROUP_ID, SUDOERS, USERBOT_ID, USERBOT_PREFIX
from wbb import aiohttpsession as session
from wbb import app, app2
from wbb.modules.userbot import eor
from wbb.utils.functions import extract_user


# ---- Helpers ---------------------------------------------------------------

def _safe_err_link(msg):
    # Some chats don’t provide .link; return a short text fallback
    try:
        return msg.link
    except Exception:
        return f"message_id={msg.id}"

JSON_NAMES_URL = (
    "https://raw.githubusercontent.com/dominictarr/random-name/master/first-names.json"
)

# ---- /anonymize ------------------------------------------------------------

@app2.on_message(
    filters.command("anonymize", prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & filters.user(SUDOERS)
)
async def change_profile(_, message: Message):
    m = await eor(message, text="Anonymizing...")
    try:
        # Add UA + cache-buster; this endpoint often 403s otherwise
        headers = {"User-Agent": "Mozilla/5.0 (compatible; WBB/1.0)"}
        bust = token_hex(8)
        img_task = session.get(
            f"https://thispersondoesnotexist.com/image?cb={bust}", headers=headers, timeout=20
        )
        names_task = session.get(JSON_NAMES_URL, headers=headers, timeout=20)

        image_resp, name_resp = await gather(img_task, names_task)

        if image_resp.status != 200:
            raise RuntimeError(f"image resp status {image_resp.status}")
        if name_resp.status != 200:
            raise RuntimeError(f"names resp status {name_resp.status}")

        image = BytesIO(await image_resp.read())
        image.name = "a.png"

        names = loads(await name_resp.text())
        if not isinstance(names, list) or not names:
            raise RuntimeError("failed to load names list")
        name = choice(names)[:64]  # Telegram’s first_name limit safeguard

        await gather(
            app2.set_profile_photo(photo=image),
            app2.update_profile(first_name=name),
        )
        await m.edit(f"[Anonymized.](tg://user?id={USERBOT_ID})")
    except Exception:
        e = format_exc()
        err_msg = await app.send_message(LOG_GROUP_ID, text=f"`{e}`")
        return await m.edit(f"**Error**: {_safe_err_link(err_msg)}")
    finally:
        try:
            image.close()
        except Exception:
            pass


# ---- /impersonate ----------------------------------------------------------

@app2.on_message(
    filters.command("impersonate", prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & filters.user(SUDOERS)
)
async def impersonate(_, message: Message):
    user_id = await extract_user(message)

    if not user_id:
        return await eor(message, text="Can't impersonate an anonymous user.")
    if user_id == USERBOT_ID:
        return await eor(message, text="Can't impersonate myself.")

    m = await eor(message, text="Impersonating...")

    try:
        user: Chat = await app2.get_chat(user_id)

        fname = (user.first_name or "")[:64]
        lname = (user.last_name or "")[:64]
        bio = (getattr(user, "bio", "") or "")[:70]  # Telegram bio limit ~70 chars on API

        # Update name/bio first
        await app2.update_profile(first_name=fname, last_name=lname, bio=bio)

        # Then try to copy avatar if present
        if user.photo and getattr(user.photo, "big_file_id", None):
            pfp = await app2.download_media(user.photo.big_file_id)
            try:
                await app2.set_profile_photo(photo=pfp)
            finally:
                try:
                    remove(pfp)
                except Exception:
                    pass
        else:
            # No photo to copy; still consider success for name/bio
            pass

        await m.edit(f"[Done.](tg://user?id={USERBOT_ID})")

    except Exception:
        e = format_exc()
        err_msg = await app.send_message(LOG_GROUP_ID, text=f"`{e}`")
        return await m.edit(f"**Error**: {_safe_err_link(err_msg)}")
