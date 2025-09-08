import os
from flask import Flask, request
from telegram import Update
from bot import application  # import the global Application

# Flask app
app = Flask(__name__)

# Health check (Render pings this)
@app.route("/")
def home():
    return "🤖 Anonymous Bot is running with webhook!"

# Telegram will send updates here
@app.route(f"/{os.getenv('BOT_TOKEN')}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    url = f"https://{os.getenv('RENDER_EXTERNAL_URL').strip('/')}/{os.getenv('BOT_TOKEN')}"

    # Set webhook on startup
    application.bot.set_webhook(url)
    app.run(host="0.0.0.0", port=port)
