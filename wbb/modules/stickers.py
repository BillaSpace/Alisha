"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""
import imghdr
import os
from asyncio import gather
from traceback import format_exc

from pyrogram import filters
from pyrogram.errors import (
    PeerIdInvalid,
    ShortnameOccupyFailed,
    StickerEmojiInvalid,
    StickerPngDimensions,
    StickerPngNopng,
    UserIsBlocked,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from wbb import BOT_USERNAME, app
from wbb.core.decorators.errors import capture_err
from wbb.utils.files import (
    get_document_from_file_id,
    resize_file_to_sticker_size,
    upload_document,
)
from wbb.utils.stickerset import (
    add_sticker_to_set,
    create_sticker,
    create_sticker_set,
    get_sticker_set_by_name,
)

__MODULE__ = "Stickers"
__HELP__ = """
/stickerid
    To get FileID of a Sticker.
/getsticker
    To get sticker as a photo and document.
/kang
    To kang a Sticker or an Image."""

# Telegram's practical pack limit (not directly exposed by API)
MAX_STICKERS = 120
SUPPORTED_TYPES = ["jpeg", "png", "webp"]


@app.on_message(filters.command("stickerid"))
@capture_err
async def sticker_id(_, message: Message):
    reply = message.reply_to_message
    if not reply or not reply.sticker:
        return await message.reply("Reply to a sticker.")
    await message.reply_text(f"`{reply.sticker.file_id}`")


@app.on_message(filters.command("getsticker"))
@capture_err
async def sticker_image(_, message: Message):
    r = message.reply_to_message
    if not r or not r.sticker:
        return await message.reply("Reply to a sticker.")

    m = await message.reply("Sending…")
    fpath = await r.download(f"{r.sticker.file_unique_id}.png")

    await gather(
        message.reply_photo(fpath),
        message.reply_document(fpath),
    )

    try:
        await m.delete()
    finally:
        try:
            os.remove(fpath)
        except Exception:
            pass


@app.on_message(filters.command("kang"))
@capture_err
async def kang(client, message: Message):
    if not message.reply_to_message:
        return await message.reply_text("Reply to a sticker/image to kang it.")
    if not message.from_user:
        return await message.reply_text("You are anon admin, kang stickers in my pm.")

    msg = await message.reply_text("Kanging sticker…")

    # Decide emoji
    args = message.text.split()
    if len(args) > 1:
        sticker_emoji = str(args[1])
    elif message.reply_to_message.sticker and message.reply_to_message.sticker.emoji:
        sticker_emoji = message.reply_to_message.sticker.emoji
    else:
        sticker_emoji = "🤔"

    # Prepare input file
    doc = message.reply_to_message.photo or message.reply_to_message.document
    try:
        if message.reply_to_message.sticker:
            sticker = await create_sticker(
                await get_document_from_file_id(message.reply_to_message.sticker.file_id),
                sticker_emoji,
            )
        elif doc:
            if doc.file_size and doc.file_size > 10_000_000:
                return await msg.edit("File size too large.")

            temp_file_path = await client.download_media(doc)
            image_type = imghdr.what(temp_file_path)
            if image_type not in SUPPORTED_TYPES:
                return await msg.edit(f"Format not supported! ({image_type})")

            try:
                temp_file_path = await resize_file_to_sticker_size(temp_file_path)
            except OSError as e:
                await msg.edit_text("Something wrong happened.")
                raise Exception(
                    f"Error resizing sticker ({temp_file_path}); {e}"
                )

            sticker = await create_sticker(
                await upload_document(client, temp_file_path, message.chat.id),
                sticker_emoji,
            )
            if os.path.isfile(temp_file_path):
                os.remove(temp_file_path)
        else:
            return await msg.edit("Nope, can't kang that.")
    except ShortnameOccupyFailed:
        await message.reply_text("Change your name or username.")
        return
    except Exception as e:
        await message.reply_text(str(e))
        print(format_exc())
        return

    # Find/prepare a pack and add the sticker
    packnum = 0
    packname = f"f{message.from_user.id}_by_{BOT_USERNAME}"
    attempts = 0
    try:
        while True:
            if attempts >= 50:  # hard stop to avoid infinite loops
                return await msg.delete()

            stickerset = await get_sticker_set_by_name(client, packname)
            if not stickerset:
                stickerset = await create_sticker_set(
                    client,
                    message.from_user.id,
                    f"{message.from_user.first_name[:32]}'s kang pack",
                    packname,
                    [sticker],
                )
            elif stickerset.set.count >= MAX_STICKERS:
                packnum += 1
                packname = f"f{packnum}_{message.from_user.id}_by_{BOT_USERNAME}"
                attempts += 1
                continue
            else:
                try:
                    await add_sticker_to_set(client, stickerset, sticker)
                except StickerEmojiInvalid:
                    return await msg.edit("[ERROR]: INVALID_EMOJI_IN_ARGUMENT")

            attempts += 1
            break

        await msg.edit(
            f"Sticker kanged to [Pack](t.me/addstickers/{packname})\nEmoji: {sticker_emoji}"
        )
    except (PeerIdInvalid, UserIsBlocked):
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="Start", url=f"t.me/{BOT_USERNAME}")]]
        )
        await msg.edit(
            "You need to start a private chat with me.",
            reply_markup=keyboard,
        )
    except StickerPngNopng:
        await message.reply_text(
            "Stickers must be PNG files but the provided image was not a PNG."
        )
    except StickerPngDimensions:
        await message.reply_text("The sticker PNG dimensions are invalid.")
