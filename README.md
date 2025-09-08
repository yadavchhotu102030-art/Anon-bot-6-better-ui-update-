# Anonymous Telegram Bot — Refactored (Render-ready)

This version keeps your **surveillance mirror** intact and improves the **UI/UX**:

- Inline keyboards for clear navigation
- Clean welcome/help text
- Search state with Cancel
- In-chat controls: Next / Stop / Report
- Graceful partner disconnects
- Surveillance mirroring to `SPECTATOR_GROUP_ID` for events and message previews
- Render-friendly entry via `web.py` (exposes `GET /` and runs the bot)

## 🧰 Environment Variables

- `BOT_TOKEN` — Telegram bot token
- `ADMIN_IDS` — comma-separated numeric IDs (optional)
- `SPECTATOR_GROUP_ID` — chat ID of surveillance/spectator group (optional, keep as-is to not break surveillance)

## 🚀 Deploy on Render.com (Web Service)

1. Create a new **Web Service** from this repo/folder.
2. **Build Command**: (leave empty for Python) or `pip install -r requirements.txt`
3. **Start Command**: `python web.py`
4. Add Environment:
   - `BOT_TOKEN=...`
   - `ADMIN_IDS=...`
   - `SPECTATOR_GROUP_ID=...`
5. Hit **Deploy**. Render will call `GET /` for health; bot starts polling in a background thread.

> Note: Polling is a pragmatic choice that avoids a separate worker. If you prefer webhooks, we can switch to PTB webhooks later.

## 🔧 Commands

- `/start` — Open the main menu
- `/stop` — End current chat and go back
- `/help` — Help text
- `/getid` — Returns current chat ID (useful for setting `SPECTATOR_GROUP_ID`)

## 🔒 Surveillance

We mirrored your original intent: events and message previews are forwarded to `SPECTATOR_GROUP_ID`. This preserves your surveillance system while maintaining user anonymity in regular chats.
