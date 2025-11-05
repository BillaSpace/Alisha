"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""

import asyncio
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait

from wbb import BOT_ID, BOT_NAME, SUDOERS, USERBOT_NAME, app, app2, HAS_USERBOT
from wbb.core.decorators.errors import capture_err
from wbb.modules import ALL_MODULES
from wbb.utils.dbfunctions import (
    get_blacklist_filters_count,
    get_filters_count,
    get_gbans_count,
    get_karmas_count,
    get_notes_count,
    get_rss_feeds_count,
    get_served_chats,
    get_served_users,
    get_warns_count,
    remove_served_chat,
)
from wbb.utils.http import get
from wbb.utils.inlinefuncs import keywords_list


@app.on_message(filters.command("clean_db") & SUDOERS)
@capture_err
async def clean_db(_, message):
    # fixed: use group_id instead of chat_id
    served_chats = [int(i["group_id"]) for i in (await get_served_chats()) if "group_id" in i]
    m = await message.reply(
        f"__**Cleaning database, might take around {len(served_chats) * 2} seconds.**__",
    )

    for served_chat in served_chats.copy():
        try:
            # check bot presence
            await app.get_chat_member(served_chat, BOT_ID)
            await asyncio.sleep(2)
        except FloodWait as e:
            await asyncio.sleep(int(e.value if hasattr(e, 'value') else e.x))
        except Exception:
            await remove_served_chat(served_chat)
            served_chats.remove(served_chat)

    await m.edit("**✅ Database Cleaned Successfully.**")


# fixed: properly handle group_id from chatsdb
async def get_total_users_count():
    schats = await get_served_chats()
    chats = []

    for chat in schats:
        cid = chat.get("group_id")  # correct field name
        if cid:
            try:
                chats.append(int(cid))
            except ValueError:
                continue

    total_count = 0
    for chat_id in chats:
        try:
            count = await app.get_chat_members_count(chat_id)
            total_count += count
        except Exception as e:
            print(f"Error fetching members count for chat {chat_id}: {e}")

    return total_count


@app.on_message(filters.command("gstats") & SUDOERS)
@capture_err
async def global_stats(_, message):
    m = await app.send_message(
        message.chat.id,
        text="__**Analysing global stats...**__",
        disable_web_page_preview=True,
    )

    # ✅ fixed: counts now match your db schema (group_id / _id)
    served_chats = len(await get_served_chats())
    served_users = len(await get_served_users())
    total_users = await get_total_users_count()
    gbans = await get_gbans_count()

    # the rest of the stats remain unchanged
    _notes = await get_notes_count()
    notes_count = _notes["notes_count"]
    notes_chats_count = _notes["chats_count"]

    _filters = await get_filters_count()
    filters_count = _filters["filters_count"]
    filters_chats_count = _filters["chats_count"]

    _filters = await get_blacklist_filters_count()
    blacklist_filters_count = _filters["filters_count"]
    blacklist_filters_chats_count = _filters["chats_count"]

    _warns = await get_warns_count()
    warns_count = _warns["warns_count"]
    warns_chats_count = _warns["chats_count"]

    _karmas = await get_karmas_count()
    karmas_count = _karmas["karmas_count"]
    karmas_chats_count = _karmas["chats_count"]

    url = "https://api.github.com/repos/thehamkercat/williambutcherbot/contributors"
    rurl = "https://github.com/thehamkercat/williambutcherbot"
    developers = await get(url)
    commits = sum([d["contributions"] for d in developers])
    developers = len(developers)

    rss_count = await get_rss_feeds_count()
    modules_count = len(ALL_MODULES)

    # userbot info (optional)
    groups_ub = channels_ub = bots_ub = privates_ub = total_ub = 0
    if app2 is not None and HAS_USERBOT:
        async for i in app2.get_dialogs():
            t = i.chat.type
            total_ub += 1
            if t in [ChatType.SUPERGROUP, ChatType.GROUP]:
                groups_ub += 1
            elif t == ChatType.CHANNEL:
                channels_ub += 1
            elif t == ChatType.BOT:
                bots_ub += 1
            elif t == ChatType.PRIVATE:
                privates_ub += 1

    msg = f"""
**📊 Global Stats of {BOT_NAME}:**

**Modules:** {modules_count}
**Inline Modules:** {len(keywords_list)}
**RSS Feeds:** {rss_count}
**Global Bans:** {gbans}
**Filters:** {filters_count} across {filters_chats_count} chats
**Blacklist Filters:** {blacklist_filters_count} across {blacklist_filters_chats_count} chats
**Notes:** {notes_count} across {notes_chats_count} chats
**Warns:** {warns_count} across {warns_chats_count} chats
**Karma:** {karmas_count} across {karmas_chats_count} chats
**Users:** {served_users} across {served_chats} chats
**Total Members in Chats:** {total_users}
**Developers:** {developers} | **Commits:** {commits} [GitHub]({rurl})

**🤖 Userbot Stats ({USERBOT_NAME if HAS_USERBOT else 'disabled'}):**
**Total Dialogs:** {total_ub}
**Groups Joined:** {groups_ub}
**Channels Joined:** {channels_ub}
**Bots:** {bots_ub}
**Private Chats:** {privates_ub}
"""
    await m.edit(msg, disable_web_page_preview=True)
