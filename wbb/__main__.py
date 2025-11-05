"""
MIT License

Copyright (c) 2024 TheHamkerCat
"""

import asyncio
import importlib
import re

from pyrogram import filters, idle
from pyrogram.enums import ChatType, ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from uvloop import install

from wbb import (
    BOT_NAME,
    BOT_USERNAME,
    LOG_GROUP_ID,
    USERBOT_NAME,
    aiohttpsession,
    app,
    log,
    # app2 may be None when no SESSION_STRING
    app2 as userbot_app,
)
from wbb.core.keyboard import ikb
from wbb.modules import ALL_MODULES
from wbb.modules.sudoers import bot_sys_stats
from wbb.utils import paginate_modules
from wbb.utils.constants import MARKDOWN
from wbb.utils.dbfunctions import (
    add_served_user,
    add_served_chat,
    clean_restart_stage,
    get_rules,
)
from wbb.utils.functions import extract_text_and_keyb

# schedule greetings cache warm-up AFTER app is connected
try:
    from wbb.modules.greetings import schedule_captcha_cache  # type: ignore
except Exception:
    schedule_captcha_cache = None  # type: ignore

HELPABLE = {}

START_PIC = "https://files.catbox.moe/pe8llc.jpg"

START_TEXT = f"""
<blockquote><b>Hello! I'm {BOT_NAME} — Your All-in-One Telegram Assistant.</b></blockquote>

<blockquote>• Advanced VC Music & Smart Group Management Bot</blockquote>
<blockquote>• Real Humanoid AI Chatbot • Anti-Spam • Auto Moderation</blockquote>
<blockquote>• Anti-Nude • Powerful Feds & More</blockquote>

<blockquote><b>Use the buttons below or try /help to explore all available commands!</b></blockquote>
"""


async def start_bot():
    global HELPABLE

    # --- START/ATTACH CLIENTS (idempotent) ---
    try:
        if not getattr(app, "is_connected", False):
            await app.start()
            log.info("Bot client started.")
        else:
            log.info("Bot client already connected — skipping start().")
    except Exception as e:
        # If already connected or any benign race, just log and continue
        log.info(f"Bot start skipped ({e}).")

    # Optional userbot
    try:
        if userbot_app is not None:
            if not getattr(userbot_app, "is_connected", False):
                maybe = userbot_app.start()
                if asyncio.iscoroutine(maybe):
                    await maybe
                (getattr(log, "warn", log.info))(f"USERBOT STARTED AS {USERBOT_NAME or 'userbot'}!")
            else:
                (getattr(log, "warn", log.info))("Userbot already connected — skipping start().")
        else:
            (getattr(log, "warn", log.info))("Userbot client not available — running bot-only.")
    except Exception as e:
        (getattr(log, "warn", log.info))(f"Userbot failed to start: {e}")

    # Schedule greetings cache warm-up AFTER app is connected (same loop)
    if schedule_captcha_cache:
        try:
            schedule_captcha_cache(app)
            (getattr(log, "warn", log.info))("Scheduled greetings captcha cache warm-up.")
        except Exception as e:
            (getattr(log, "warn", log.info))(f"Failed scheduling captcha cache: {e}")

    # --- LOAD MODULES / HELPABLE MAP ---
    for module in ALL_MODULES:
        imported_module = importlib.import_module("wbb.modules." + module)
        if getattr(imported_module, "__MODULE__", None) and getattr(imported_module, "__HELP__", None):
            HELPABLE[imported_module.__MODULE__.replace(" ", "_").lower()] = imported_module

    # Pretty print module list
    bot_modules = ""
    j = 1
    for i in ALL_MODULES:
        if j == 4:
            bot_modules += "|{:<15}|\n".format(i)
            j = 0
        else:
            bot_modules += "|{:<15}".format(i)
        j += 1
    print("+===============================================================+")
    print("|                              WBB                              |")
    print("+===============+===============+===============+===============+")
    print(bot_modules)
    print("+===============+===============+===============+===============+")
    log.info(f"BOT STARTED AS {BOT_NAME}!")
    if USERBOT_NAME and str(USERBOT_NAME).strip():
        log.info(f"USERBOT STARTED AS {USERBOT_NAME}!")
    else:
        (getattr(log, "warn", log.info))("String session missing — skipping userbot startup.")

    # Online status / restart message
    restart_data = await clean_restart_stage()
    try:
        log.info("Sending online status")
        if restart_data:
            await app.edit_message_text(
                restart_data["chat_id"],
                restart_data["message_id"],
                "**Restarted Successfully**",
            )
        else:
            await app.send_message(LOG_GROUP_ID, "Alisha Ai Bot has been started successfully!")
    except Exception:
        pass

    # --- MAIN IDLE LOOP ---
    try:
        await idle()
    finally:
        # --- GRACEFUL SHUTDOWN ---
        log.info("Stopping clients")
        try:
            if getattr(app, "is_connected", False):
                await app.stop()
        except Exception:
            pass

        try:
            if userbot_app is not None and getattr(userbot_app, "is_connected", False):
                maybe = userbot_app.stop()
                if asyncio.iscoroutine(maybe):
                    await maybe
        except Exception:
            pass

        try:
            if not aiohttpsession.closed:
                await aiohttpsession.close()
        except Exception:
            pass

        log.info("Bot 🛑 stopped Successfully!")


# ================== CLEAN HOME KEYBOARD =================== #

home_keyboard_pm = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(text="Commands", callback_data="bot_commands"),
            InlineKeyboardButton(text="Bot Stats", callback_data="stats_callback"),
        ],
        [
            InlineKeyboardButton(text="Help Desk", url="https://t.me/billacore"),
        ],
        [
            InlineKeyboardButton(
                text="Add Me To Your Group",
                url=f"http://t.me/{BOT_USERNAME}?startgroup=new",
            )
        ],
    ]
)

home_text_pm = START_TEXT

keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(text="Help", url=f"t.me/{BOT_USERNAME}?start=help"),
            InlineKeyboardButton(text="Bot Stats", callback_data="stats_callback"),
        ],
        [
            InlineKeyboardButton(text="Support", url="https://t.me/billacore"),
        ],
    ]
)

FED_MARKUP = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("Fed Owner Commands", callback_data="fed_owner"),
            InlineKeyboardButton("Fed Admin Commands", callback_data="fed_admin"),
        ],
        [
            InlineKeyboardButton("User Commands", callback_data="fed_user"),
        ],
        [
            InlineKeyboardButton("Back", callback_data="help_back"),
        ],
    ]
)


@app.on_message(filters.command("start"))
async def start(_, message):
    # Save group when invoked in a group/supergroup
    if message.chat.type != ChatType.PRIVATE:
        try:
            await add_served_chat(message.chat.id)
        except Exception:
            pass
        return await message.reply("PM Me For More Details.", reply_markup=keyboard)

    # Save user when invoked in private
    try:
        await add_served_user(message.from_user.id)
    except Exception:
        pass

    if len(message.text.split()) > 1:
        user = await app.get_users(message.from_user.id)
        name = (message.text.split(None, 1)[1]).lower()
        match = re.match(r"rules_(.*)", name)
        if match:
            chat_id = match.group(1)
            user_id = message.from_user.id
            chat = await app.get_chat(int(chat_id))
            text = f"**The rules for `{chat.title}` are:\n\n**"
            rules = await get_rules(int(chat_id))
            if rules:
                text = text + rules
                if "{chat}" in text:
                    text = text.replace("{chat}", chat.title)
                if "{name}" in text:
                    text = text.replace("{name}", user.mention)
                keyb = None
                if re.findall(r"\[.+\,.+\]", text):
                    text, keyb = extract_text_and_keyb(ikb, text)
                await app.send_message(user_id, text=text, reply_markup=keyb)
            else:
                return await app.send_message(
                    user_id,
                    "The group admins haven't set any rules for this chat yet.",
                )
        if name == "mkdwn_help":
            await message.reply(
                MARKDOWN,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        elif "_" in name:
            module = name.split("_", 1)[1]
            text = (
                f"Here is the help for **{HELPABLE[module].__MODULE__}**:\n"
                + HELPABLE[module].__HELP__
            )
            if module == "federation":
                return await message.reply(
                    text=text, reply_markup=FED_MARKUP, disable_web_page_preview=True
                )
            await message.reply(
                text,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Back", callback_data="help_back")]]
                ),
                disable_web_page_preview=True,
            )
        elif name == "help":
            text, keyb = await help_parser(message.from_user.first_name)
            await message.reply(text, reply_markup=keyb)
    else:
        await message.reply_photo(
            START_PIC,
            caption=home_text_pm,
            reply_markup=home_keyboard_pm,
            parse_mode=ParseMode.HTML,
        )
    return


@app.on_message(filters.command("help"))
async def help_command(_, message):
    if message.chat.type != ChatType.PRIVATE:
        if len(message.command) >= 2:
            name = (message.text.split(None, 1)[1]).replace(" ", "_").lower()
            if str(name) in HELPABLE:
                key = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                text="Click here",
                                url=f"t.me/{BOT_USERNAME}?start=help_{name}",
                            )
                        ],
                    ]
                )
                await message.reply(
                    f"Click on the below button to get help about {name}",
                    reply_markup=key,
                )
            else:
                await message.reply("PM Me For More Details.", reply_markup=keyboard)
        else:
            await message.reply("PM Me For More Details.", reply_markup=keyboard)
    else:
        if len(message.command) >= 2:
            name = (message.text.split(None, 1)[1]).replace(" ", "_").lower()
            if str(name) in HELPABLE:
                text = (
                    f"Here is the help for **{HELPABLE[name].__MODULE__}**:\n"
                    + HELPABLE[name].__HELP__
                )
                await message.reply(text, disable_web_page_preview=True)
            else:
                text, help_keyboard = await help_parser(message.from_user.first_name)
                await message.reply(
                    text, reply_markup=help_keyboard, disable_web_page_preview=True
                )
        else:
            text, help_keyboard = await help_parser(message.from_user.first_name)
            await message.reply(
                text, reply_markup=help_keyboard, disable_web_page_preview=True
            )
    return


async def help_parser(name, keyboard=None):
    if not keyboard:
        keyboard = InlineKeyboardMarkup(paginate_modules(0, HELPABLE, "help"))
    return (
        """Hello {first_name}, My name is {bot_name}.
You can explore available modules below or ask in our Support Group.
""".format(
            first_name=name,
            bot_name=BOT_NAME,
        ),
        keyboard,
    )


@app.on_callback_query(filters.regex("bot_commands"))
async def commands_callbacc(_, CallbackQuery):
    text, keyboard = await help_parser(CallbackQuery.from_user.mention)
    await app.send_message(
        CallbackQuery.message.chat.id,
        text=text,
        reply_markup=keyboard,
    )
    await CallbackQuery.message.delete()


@app.on_callback_query(filters.regex("stats_callback"))
async def stats_callbacc(_, CallbackQuery):
    text = await bot_sys_stats()
    await app.answer_callback_query(CallbackQuery.id, text, show_alert=True)


@app.on_callback_query(filters.regex(r"help_(.*?)"))
async def help_button(client, query):
    home_match = re.match(r"help_home\((.+?)\)", query.data)
    mod_match = re.match(r"help_module\((.+?)\)", query.data)
    prev_match = re.match(r"help_prev\((.+?)\)", query.data)
    next_match = re.match(r"help_next\((.+?)\)", query.data)
    back_match = re.match(r"help_back", query.data)
    create_match = re.match(r"help_create", query.data)
    top_text = f"""
Hello {query.from_user.first_name}, My name is {BOT_NAME}.
You can choose an option below to see command lists or ask in Support Group.

General commands:
 - /start — Start the Ai bot
 - /help — Show help menu
 """
    if mod_match:
        module = (mod_match.group(1)).replace(" ", "_")
        text = (
            "{} **{}**:\n".format("Here is the help for", HELPABLE[module].__MODULE__)
            + HELPABLE[module].__HELP__
        )
        if module == "federation":
            return await query.message.edit(
                text=text,
                reply_markup=FED_MARKUP,
                disable_web_page_preview=True,
            )
        await query.message.edit(
            text=text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Back", callback_data="help_back")]]
            ),
            disable_web_page_preview=True,
        )
    elif home_match:
        await app.send_message(
            query.from_user.id,
            text=home_text_pm,
            reply_markup=home_keyboard_pm,
        )
        await query.message.delete()
    elif prev_match:
        curr_page = int(prev_match.group(1))
        await query.message.edit(
            text=top_text,
            reply_markup=InlineKeyboardMarkup(
                paginate_modules(curr_page - 1, HELPABLE, "help")
            ),
            disable_web_page_preview=True,
        )
    elif next_match:
        next_page = int(next_match.group(1))
        await query.message.edit(
            text=top_text,
            reply_markup=InlineKeyboardMarkup(
                paginate_modules(next_page + 1, HELPABLE, "help")
            ),
            disable_web_page_preview=True,
        )
    elif back_match:
        await query.message.edit(
            text=top_text,
            reply_markup=InlineKeyboardMarkup(
                paginate_modules(0, HELPABLE, "help")
            ),
            disable_web_page_preview=True,
        )
    elif create_match:
        text, keyboard = await help_parser(query)
        await query.message.edit(
            text=text,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    return await client.answer_callback_query(query.id)


if __name__ == "__main__":
    try:
        install()
    except Exception:
        pass
    asyncio.run(start_bot())
