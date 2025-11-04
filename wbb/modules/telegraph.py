from pyrogram import filters
from pyrogram.types import Message
import aiohttp
import os

from wbb import app, telegraph
from wbb.core.decorators.errors import capture_err

__MODULE__ = "Telegraph"
__HELP__ = """
/telegraph [Page name]: Replying to a Message to Paste styled text on Telegraph.
/tgm: Upload photo/video/document to Catbox.
"""


@app.on_message(filters.command("telegraph"))
@capture_err
async def paste(_, message: Message):
    reply = message.reply_to_message

    if not reply or not reply.text:
        return await message.reply_text("Reply to a text message.")

    if len(message.command) < 2:
        return await message.reply_text("**Usage:**\n/telegraph [Page name]")

    page_name = message.text.split(None, 1)[1]

    try:
        page = telegraph.create_page(
            page_name, html_content=reply.text.html.replace("\n", "<br>")
        )
        await message.reply_text(
            f"**Posted:** {page['url']}",
            disable_web_page_preview=True,
        )
    except Exception as e:
        await message.reply_text(f"Error: {e}")

async def auto_delete(file_path: str, message: Message, delay: int = 300):
    """Deletes the file and message after a delay (default: 5 minutes)."""
    await asyncio.sleep(delay)
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"[AutoDelete] File {file_path} removed after {delay}s")
        except Exception as e:
            print(f"[AutoDelete] Failed to remove {file_path}: {e}")

    try:
        await message.delete()
        print(f"[AutoDelete] Message deleted after {delay}s")
    except Exception as e:
        print(f"[AutoDelete] Failed to delete message: {e}")


@app.on_message(filters.command("tgm"))
@capture_err
async def tgm(_, message: Message):
    reply = message.reply_to_message

    if not reply or not (reply.photo or reply.video or reply.document):
        return await message.reply_text(
            "Reply to a photo, video, or document to upload it to Catbox."
        )

    m = await message.reply_text("📤 Uploading to Catbox...")

    file_path = None
    try:
        # Download the media file
        file_path = await reply.download()
        file_name = os.path.basename(file_path)

        # Prepare upload form for Catbox
        form = aiohttp.FormData()
        form.add_field("reqtype", "fileupload")
        form.add_field("fileToUpload", open(file_path, "rb"), filename=file_name)

        # Upload to Catbox
        async with aiohttp.ClientSession() as session:
            async with session.post("https://catbox.moe/user/api.php", data=form) as resp:
                result = await resp.text()

        if result.startswith("https://"):
            await m.edit_text(
                f"Uploaded to Catbox:\n{result}\n\n"
                f"Save this link now — it will be auto-deleted from chat in 5 minutes.",
                link_preview_options={"is_disabled": False},
            )
            # Auto-delete message and file after 5 minutes
            asyncio.create_task(auto_delete(file_path, m, delay=300))
        else:
            await m.edit_text(f"Upload failed:\n{result}")

    except Exception as e:
        await m.edit_text(f"Upload failed: {e}")

    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
