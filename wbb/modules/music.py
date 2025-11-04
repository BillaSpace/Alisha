import os
import re
import aiohttp
import asyncio
import ffmpeg
import secrets
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from wbb import app
from wbb.core.decorators.errors import capture_err

SAAVN_API = "http://saavnapi-nine.vercel.app/result?query="
TEMP_DIR = "downloads"
if not os.path.exists(TEMP_DIR):
    os.mkdir(TEMP_DIR)

# Temporary cache for callback lookups
app.song_cache = {}

__MODULE__ = "Music"
__HELP__ = """
/song [link] To Download Music From Various Websites.
/music [query] To Download Music From Saavn.
"""


# ------------------------- /song or /music command -------------------------

@app.on_message(filters.command(["song", "music"]))
@capture_err
async def saavn_search(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("**Usage:** /song <song name>")
    query = message.text.split(None, 1)[1]
    m = await message.reply_text(f"🔎 Searching for **{query}** ...")

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{SAAVN_API}{query}&lyrics=false") as resp:
            if resp.status != 200:
                return await m.edit("⚠️ API Error. Try again later.")
            results = await resp.json()

    if not results:
        return await m.edit("❌ No results found.")

    buttons = []
    for song in results[:5]:
        sid = secrets.token_hex(3)  # 6-character ID
        title = re.sub(r"&(?:quot|amp|#39);", "", song.get("song", "Unknown"))
        artist = re.sub(r"&(?:quot|amp|#39);", "", song.get("singers", "Unknown Artist"))
        app.song_cache[sid] = {
            "title": title,
            "artist": artist,
            "media_url": song["media_url"],
            "image": song["image"],
            "duration": song["duration"]
        }
        buttons.append([InlineKeyboardButton(f"{title} - {artist}", callback_data=f"song_{sid}")])

    await m.edit(
        "**🎵 Select a song below:**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ------------------------- Song selection handler -------------------------

@app.on_callback_query(filters.regex(r"^song_[0-9a-f]+$"))
async def choose_quality(_, query: CallbackQuery):
    sid = query.data.split("_")[1]
    song = app.song_cache.get(sid)
    if not song:
        return await query.answer("Song expired or invalid.", show_alert=True)

    title = song["title"]
    artist = song["artist"]

    buttons = [
        [
            InlineKeyboardButton("🎧 320 kbps", callback_data=f"quality_{sid}_320"),
            InlineKeyboardButton("🍎 ALAC (.m4a)", callback_data=f"quality_{sid}_alac"),
        ]
    ]
    await query.message.edit_text(
        f"🎵 **{title}** - {artist}\n\nChoose your preferred quality:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ------------------------- Quality selection handler -------------------------

@app.on_callback_query(filters.regex(r"^quality_[0-9a-f]+_"))
async def download_and_send(_, query: CallbackQuery):
    parts = query.data.split("_")
    sid, quality = parts[1], parts[2]
    data = app.song_cache.get(sid)

    if not data:
        return await query.answer("Request expired.", show_alert=True)

    title = data["title"]
    artist = data["artist"]
    media_url = data["media_url"]
    thumb = data["image"]
    duration = int(data["duration"])
    performer = "Alisha Ai"

    await query.message.edit_text(f"⬇️ Downloading **{title}** ...")

    file_path = os.path.join(TEMP_DIR, f"{sid}.m4a")

    async with aiohttp.ClientSession() as session:
        async with session.get(media_url) as resp:
            if resp.status != 200:
                return await query.message.edit_text("Failed to fetch media file.")
            with open(file_path, "wb") as f:
                f.write(await resp.read())

    # Convert to ALAC if selected
    if quality == "alac":
        await query.message.edit_text("🎚️ Converting to ALAC (Apple Lossless)...")
        alac_path = os.path.join(TEMP_DIR, f"{sid}_alac.m4a")
        try:
            (
                ffmpeg
                .input(file_path)
                .output(alac_path, acodec="alac", loglevel="quiet")
                .run(overwrite_output=True)
            )
            os.remove(file_path)
            file_path = alac_path
        except Exception as e:
            return await query.message.edit_text(f"Conversion failed: {e}")

    await query.message.reply_audio(
        audio=file_path,
        title=title,
        performer=performer,
        duration=duration,
        thumb=thumb,
        caption=f"🎶 **{title}**\n👩‍💻 Performer: {performer}\n\n⚠️ Auto-deletes in 5 minutes.",
    )

    await query.message.edit_text("✅ Sent successfully!")

    # Schedule cleanup
    async def cleanup():
        await asyncio.sleep(300)
        try:
            os.remove(file_path)
        except:
            pass
        if sid in app.song_cache:
            del app.song_cache[sid]

    asyncio.create_task(cleanup())
