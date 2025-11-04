from pyrogram import filters
from pyrogram.types import Message
import aiohttp
import os

from wbb import app, telegraph
from wbb.core.decorators.errors import capture_err

__MODULE__ = "Telegraph"
__HELP__ = """
/telegraph [Page name]: Paste styled text on Telegraph.
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


@app.on_message(filters.command("tgm"))
@capture_err
async def tgm(_, message: Message):
    reply = message.reply_to_message

    if not reply or not (reply.photo or reply.video or reply.document):
        return await message.reply_text(
            "Reply to a photo, video, or document to upload to Catbox."
        )

    m = await message.reply_text("Uploading to Catbox...")

    try:
        # Download the file
        file_path = await reply.download()
        file_name = os.path.basename(file_path)

        # Upload to Catbox.moe
        async with aiohttp.ClientSession() as session:
            catbox_url = "https://catbox.moe/user/api.php"
            data = {"reqtype": "fileupload"}
            async with session.post(catbox_url, data=data, files={"fileToUpload": open(file_path, "rb")}) as resp:
                result = await resp.text()

        await m.edit_text(f"**Uploaded:** {result}", disable_web_page_preview=False)

    except Exception as e:
        await m.edit_text(f"Upload failed: {e}")

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
