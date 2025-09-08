import os
import threading
from flask import Flask
from bot import run_polling

app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Anonymous Bot is running!"

def start_bot():
    run_polling()

if __name__ == "__main__":
    threading.Thread(target=start_bot, daemon=True).start()
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
