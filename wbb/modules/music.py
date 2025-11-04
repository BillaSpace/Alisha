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

app.song_cache = {}  # cache for callback data


# Clean titles (remove HTML entities)
def clean_text(text: str) -> str:
    return re.sub(r"&(?:quot|amp|#39|lt|gt);", "", text)


# ---------------- /song or /music command ----------------

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
        sid = secrets.token_hex(3)
        title = clean_text(song.get("song", "Unknown"))
        artist = clean_text(song.get("singers", "Unknown Artist"))
        app.song_cache[sid] = {
            "title": title,
            "artist": artist,
            "media_url": song["media_url"],
            "image": song["image"],
            "duration": song.get("duration", "0")
        }
        buttons.append([InlineKeyboardButton(f"{title} - {artist}", callback_data=f"song_{sid}")])

    await m.edit(
        "**🎵 Select a song below:**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ---------------- Song selection handler ----------------

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
        f"🎵 **{title}** - {artist}\n\nChoose quality:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# ---------------- Download and Send ----------------

@app.on_callback_query(filters.regex(r"^quality_[0-9a-f]+_"))
async def download_and_send(_, query: CallbackQuery):
    _, sid, quality = query.data.split("_")
    data = app.song_cache.get(sid)
    if not data:
        return await query.answer("Request expired.", show_alert=True)

    title = data["title"]
    artist = data["artist"]
    performer = "Alisha Ai"
    duration = int(data.get("duration", 0))
    media_url = data["media_url"]
    thumb_url = data["image"]

    await query.message.edit_text(f"⬇️ Downloading **{title}** ...")

    # Download audio file
    file_path = os.path.join(TEMP_DIR, f"{sid}.m4a")
    async with aiohttp.ClientSession() as session:
        async with session.get(media_url) as resp:
            if resp.status != 200:
                return await query.message.edit_text("Failed to download audio.")
            with open(file_path, "wb") as f:
                f.write(await resp.read())

        # Download thumbnail safely
        thumb_path = None
        if thumb_url:
            try:
                thumb_path = os.path.join(TEMP_DIR, f"{sid}.jpg")
                async with session.get(thumb_url) as resp2:
                    if resp2.status == 200:
                        with open(thumb_path, "wb") as t:
                            t.write(await resp2.read())
            except Exception:
                thumb_path = None

    # Convert to ALAC if needed
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
        thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
        caption=f"🎶 **{title}**\n👩‍💻 Performer: {performer}\n💽 Quality: {quality.upper()}",
    )

    await query.message.edit_text("✅ Sent successfully!")

    # Cleanup cache and files
    async def cleanup():
        await asyncio.sleep(300)
        for f in [file_path, thumb_path]:
            if f and os.path.exists(f):
                os.remove(f)
        app.song_cache.pop(sid, None)

    asyncio.create_task(cleanup())
