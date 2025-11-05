"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""

from pyrogram import filters
from pyrogram.types import Message

from wbb import SUDOERS, USERBOT_ID, USERBOT_PREFIX, app2, eor, log, telegraph, HAS_USERBOT

__MODULE__ = "Userbot"
TEXT = """
<code>alive</code>  →  Send Alive Message.<br>

<code>create (b|s|c) Title</code>  →  create [basic|super]group & channel<br>

<code>chatbot [ENABLE|DISABLE]</code>  →  Enable chatbot in a chat.<br>

<code>autocorrect [ENABLE|DISABLE]</code>  →  This will autocorrect your messages on the go.<br>

<code>purgeme [Number of messages to purge]</code>  →  Purge your own messages.<br>

<code>eval [Lines of code]</code>  →  Execute Python Code.<br>

<code>lsTasks</code>  →  List running tasks (eval)<br>

<code>sh [Some shell code]</code>  →  Execute Shell Code.<br>

<code>approve</code>  →  Approve a user to PM you.<br>

<code>disapprove</code>  →  Disapprove a user to PM you.<br>

<code>block</code>  →  Block a user.<br>

<code>unblock</code>  →  Unblock a user.<br>

<code>anonymize</code>  →  Change Name/PFP Randomly.<br>

<code>impersonate [User_ID|Username|Reply]</code> → Clone profile of a user.<br>

<code>useradd</code>  →  To add a user in sudoers. [UNSAFE]<br>

<code>userdel</code>  → To remove a user from sudoers.<br>

<code>sudoers</code>  →  To list sudo users.<br>

<code>download [URL or reply to a file]</code>  →  Download a file from TG or URL<br>

<code>upload [URL or File Path]</code>  →  Upload a file from local or URL<br>

<code>parse_preview [REPLY TO A MESSAGE]</code>  →  Parse a web_page(link) preview<br>

<code>id</code>  →  Same as /id but for Ubot<br>

<code>paste</code> → Paste shit on batbin.<br>

<code>help</code> → Get link to this page.<br>

<code>kang</code> → Kang stickers.<br>

<code>dice</code> → Roll a dice.<br>
"""
log.info("Pasting userbot commands on telegraph")

__HELP__ = f"""**Commands:** {telegraph.create_page(
    "Userbot Commands",
    html_content=TEXT,
)['url']}"""

log.info("Done pasting userbot commands on telegraph")

# ---- userbot decorator shim (no-op if userbot is disabled/absent) ----
if app2 is not None and HAS_USERBOT:
    ubot_on_message = app2.on_message
else:
    def ubot_on_message(*args, **kwargs):
        def _wrap(func):
            return func
        return _wrap

# safe user filter: if USERBOT_ID isn't an int, make a filter that matches nobody
if isinstance(USERBOT_ID, int):
    UB_USER_FILTER = filters.user(USERBOT_ID)
else:
    UB_USER_FILTER = filters.user([])


@ubot_on_message(
    filters.command("help", prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & UB_USER_FILTER
)
async def get_help(_, message: Message):
    if app2 is None:
        return
    await eor(
        message,
        text=__HELP__,
        disable_web_page_preview=True,
    )


@ubot_on_message(
    filters.command(["purgeme", "purge_me"], prefixes=USERBOT_PREFIX)
    & ~filters.forwarded
    & ~filters.via_bot
    & UB_USER_FILTER
)
async def purge_me_func(_, message: Message):
    if app2 is None:
        return
    if len(message.command) != 2:
        return await message.delete()

    n = message.text.split(None, 1)[1].strip()
    if not n.isnumeric():
        return await eor(message, text="Invalid Args")

    n = int(n)

    if n < 1:
        return await eor(message, text="Need a number >=1")

    chat_id = message.chat.id

    message_ids = [
        m.id
        async for m in app2.search_messages(
            chat_id,
            from_user=int(USERBOT_ID) if isinstance(USERBOT_ID, int) else None,
            limit=n,
        )
    ]

    if not message_ids:
        return await eor(message, text="No messages found.")

    # chunk into <=99 IDs to respect deletion limits
    to_delete = [message_ids[i:i + 99] for i in range(0, len(message_ids), 99)]

    for chunk in to_delete:
        await app2.delete_messages(
            chat_id=chat_id,
            message_ids=chunk,
            revoke=True,
        )
