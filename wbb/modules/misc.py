"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""
import re
import secrets
import string
import subprocess
import time
import socket
import platform
import json  # <- needed for /json
from asyncio import Lock
from re import findall

from pyrogram import enums, filters

from wbb import SUDOERS, USERBOT_PREFIX, app, app2, arq, eor, HAS_USERBOT
from wbb.core.decorators.errors import capture_err
from wbb.utils import random_line
from wbb.utils.http import get
from wbb.utils.json_prettify import json_prettify
from wbb.utils.pastebin import paste

__MODULE__ = "Misc"
__HELP__ = """
/asq
    Ask a question

/commit
    Generate Funny Commit Messages

/runs
    Idk Test Yourself

/id
    Get Chat_ID or User_ID

/random [Length]
    Generate Random Complex Passwords

/cheat [Language] [Query]
    Get Programming Related Help

/tr [LANGUAGE_CODE]
    Translate A Message
    Ex: /tr en

/json [URL]
    Get parsed JSON response from a rest API.


/webss | .webss [URL] [FULL_SIZE?, use (y|yes|true) to get full size image. (optional)]
    Take A Screenshot Of A Webpage

/reverse
    Reverse search an image.

/carbon
    Make Carbon from code.

/tts
    Convert Text To Speech.

/autocorrect [Reply to a message]
    Autocorrects the text in replied message.

/pdf [Reply to an image (as document) or a group of images.]
    Convert images to PDF, helpful for online classes.

/markdownhelp
    Sends mark down and formatting help.

/backup
    Backup database

/ping
    Check ping of all 5 DCs.
    
#RTFM - Tell noobs to read the manual
"""

PING_LOCK = Lock()

# ---- userbot decorator shim (no-op if userbot is disabled/absent) ----
if app2 is not None and HAS_USERBOT:
    ubot_on_message = app2.on_message
else:
    def ubot_on_message(*args, **kwargs):
        def _wrap(func):
            return func
        return _wrap


@ubot_on_message(
    SUDOERS
    & filters.command("ping", prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
)
@app.on_message(filters.command("ping"))
async def ping_handler(_, message):
    m = await eor(message, text="Pinging datacenters...")
    async with PING_LOCK:
        ips = {
            "dc1": "149.154.175.53",
            "dc2": "149.154.167.51",
            "dc3": "149.154.175.100",
            "dc4": "149.154.167.91",
            "dc5": "91.108.56.130",
        }
        text = "**Pings:**\n"

        system = platform.system().lower()
        for dc, ip in ips.items():
            # choose ping args per platform
            if system == "windows":
                # -n count, -w timeout (ms)
                cmd = ["ping", "-n", "1", "-w", "2000", ip]
            else:
                # unix-like: -c count, -W timeout (seconds)
                cmd = ["ping", "-c", "1", "-W", "2", ip]

            try:
                proc = subprocess.run(
                    cmd,
                    text=True,
                    capture_output=True,
                )
                out = (proc.stdout or "") + (proc.stderr or "")
                # only treat returncode==0 as success for parsing ping
                if proc.returncode == 0:
                    # try several common time= formats, and time<1ms
                    m1 = re.search(r"time[=<]\s*([\d.]+)\s*ms", out)
                    m2 = re.search(r"time[=<]\s*(<\s*1)\s*ms", out)
                    m3 = re.search(r"time[=<]\s*([\d.]+)\s*m?s", out)  # fallback
                    if m1:
                        resp_time = f"{m1.group(1)} ms"
                    elif m2:
                        resp_time = "<1 ms"
                    elif m3:
                        resp_time = f"{m3.group(1)}"
                    else:
                        # couldn't parse but ping returned 0 -> mark reachable
                        resp_time = "reachable"
                    text += f"    **{dc.upper()}:** {resp_time} ✅\n"
                else:
                    # ping returned non-zero (no reply) — try TCP connect fallback
                    try:
                        start = time.time()
                        sock = socket.create_connection((ip, 443), timeout=2)
                        sock.close()
                        elapsed_ms = int((time.time() - start) * 1000)
                        text += (
                            f"    **{dc.upper()}:** reachable (tcp) ~{elapsed_ms} ms ✅\n"
                        )
                    except Exception:
                        text += f"    **{dc.upper()}:** ❌\n"
            except FileNotFoundError:
                # ping command not available on system — do TCP check only
                try:
                    start = time.time()
                    sock = socket.create_connection((ip, 443), timeout=2)
                    sock.close()
                    elapsed_ms = int((time.time() - start) * 1000)
                    text += (
                        f"    **{dc.upper()}:** reachable (tcp) ~{elapsed_ms} ms ✅\n"
                    )
                except Exception:
                    text += f"    **{dc.upper()}:** ❌\n"
            except Exception:
                # any other unexpected error -> mark fail
                text += f"    **{dc.upper()}:** ❌\n"

        await m.edit(text)


@app.on_message(filters.command("commit"))
async def commit(_, message):
    await message.reply_text(await get("http://whatthecommit.com/index.txt"))


@app.on_message(filters.command("RTFM", "#"))
async def rtfm(_, message):
    await message.delete()
    if not message.reply_to_message:
        return await message.reply_text("Reply To A Message lol")
    await message.reply_to_message.reply_text(
        "Are You Lost? READ THE FUCKING DOCS!"
    )


@app.on_message(filters.command("runs"))
async def runs(_, message):
    await message.reply_text((await random_line("wbb/utils/runs.txt")))


@ubot_on_message(
    filters.command("id", prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & SUDOERS
)
@app.on_message(filters.command("id"))
async def getid(client, message):
    chat = message.chat
    your_id = message.from_user.id
    message_id = message.id
    reply = message.reply_to_message

    text = f"**[Message ID:]({message.link})** `{message_id}`\n"
    text += f"**[Your ID:](tg://user?id={your_id})** `{your_id}`\n"

    if not message.command:
        message.command = message.text.split()

    if len(message.command) == 2:
        try:
            split = message.text.split(None, 1)[1].strip()
            user_id = (await client.get_users(split)).id
            text += f"**[User ID:](tg://user?id={user_id})** `{user_id}`\n"
        except Exception:
            return await eor(message, text="This user doesn't exist.")

    text += f"**[Chat ID:](https://t.me/{chat.username})** `{chat.id}`\n\n"
    if not getattr(reply, "empty", True):
        id_ = reply.from_user.id if reply.from_user else reply.sender_chat.id
        text += f"**[Replied Message ID:]({reply.link})** `{reply.id}`\n"
        text += f"**[Replied User ID:](tg://user?id={id_})** `{id_}`"

    await eor(
        message,
        text=text,
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.MARKDOWN,
    )


# Random
@app.on_message(filters.command("random"))
@capture_err
async def random(_, message):
    if len(message.command) != 2:
        return await message.reply_text(
            '"/random" Needs An Argurment.' " Ex: `/random 5`"
        )
    length = message.text.split(None, 1)[1]
    try:
        if 1 < int(length) < 1000:
            alphabet = string.ascii_letters + string.digits
            password = "".join(
                secrets.choice(alphabet) for i in range(int(length))
            )
            await message.reply_text(f"`{password}`")
        else:
            await message.reply_text("Specify A Length Between 1-1000")
    except ValueError:
        await message.reply_text(
            "Strings Won't Work!, Pass A Positive Integer Less Than 1000"
        )


# Translate
@app.on_message(filters.command("tr"))
@capture_err
async def tr(_, message):
    if len(message.command) != 2:
        return await message.reply_text("/tr [LANGUAGE_CODE]")
    lang = message.text.split(None, 1)[1]
    if not message.reply_to_message or not lang:
        return await message.reply_text(
            "Reply to a message with /tr [language code]"
            + "\nGet supported language list from here -"
            + " https://py-googletrans.readthedocs.io/en"
            + "/latest/#googletrans-languages"
        )
    reply = message.reply_to_message
    text = reply.text or reply.caption
    if not text:
        return await message.reply_text("Reply to a text to translate it")
    result = await arq.translate(text, lang)
    if not result.ok:
        return await message.reply_text(result.result)
    await message.reply_text(result.result.translatedText)


@app.on_message(filters.command("json"))
@capture_err
async def json_fetch(_, message):
    if len(message.command) != 2:
        return await message.reply_text("/json [URL]")
    url = message.text.split(None, 1)[1]
    m = await message.reply_text("Fetching")
    try:
        data = await get(url)
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                pass
        if isinstance(data, dict) or isinstance(data, list):
            data = await json_prettify(data)
        else:
            data = str(data)

        if len(data) < 4090:
            await m.edit(data)
        else:
            link = await paste(data)
            await m.edit(
                f"[OUTPUT_TOO_LONG]({link})",
                disable_web_page_preview=True,
            )
    except Exception as e:
        await m.edit(str(e))


@app.on_message(filters.command(["kickme", "banme"]))
async def kickbanme(_, message):
    await message.reply_text(
        "Haha, it doesn't work that way, You're stuck with everyone here."
    )
