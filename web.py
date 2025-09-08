import os
from flask import Flask

# Start the Telegram bot (polling) in-process
from bot import run_polling

app = Flask(__name__)

@app.route("/")
def health():
    return "OK", 200

if __name__ == "__main__":
    # On Render.com, this web service must bind to PORT
    port = int(os.environ.get("PORT", "10000"))
    # Start bot in a separate thread so Flask can serve healthchecks
    import threading
    t = threading.Thread(target=run_polling, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=port)
