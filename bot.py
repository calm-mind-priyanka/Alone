# bot.py
import os
import asyncio
import json
import time
from typing import Optional
from fastapi import FastAPI
import uvicorn
from telethon import TelegramClient, events, Button, errors
from contextlib import asynccontextmanager

# ---------------- Config ----------------
API_ID = int(os.getenv("API_ID", "24222039"))
API_HASH = os.getenv("API_HASH", "6dd2dc70434b2f577f76a2e993135662")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8259426500:AAHclWJUNaMZ9XLhWx7M27jxrKxnPijyyaw")
ADMIN_ID = os.getenv("ADMIN_ID", "6046055058")
DELAY = float(os.getenv("DELAY", 1.2))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 5000))
REST_MINUTES = int(os.getenv("REST_MINUTES", 10))
CONFIG_FILE = os.getenv("CONFIG_FILE", "config.json")
PROGRESS_FILE = os.getenv("PROGRESS_FILE", "forward_progress.json")

# ---------------- Telethon client ----------------
client = TelegramClient("forward_session", API_ID, API_HASH)

# ---------------- Runtime ----------------
is_running = False
is_paused = False
_stop_signal = False
forwarded_count = 0
start_time = None
last_processed_id = None

# ---------------- Helpers ----------------
def load_json(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {path}: {e}")
            return {}
    return {}

def save_json(path: str, data: dict):
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error saving {path}: {e}")

config = load_json(CONFIG_FILE)
if "admin" not in config and ADMIN_ID:
    config["admin"] = ADMIN_ID
if "source" not in config:
    config["source"] = os.getenv("SOURCE_CHAT")
if "target" not in config:
    config["target"] = os.getenv("TARGET_CHAT")

progress = load_json(PROGRESS_FILE)
last_processed_id = progress.get("last_id")
forwarded_count = progress.get("count", 0)

def safe_parse_chat(value: Optional[str]):
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return value

def is_admin(user_id: int) -> bool:
    adm = config.get("admin")
    if not adm:
        return True
    try:
        return int(adm) == int(user_id)
    except Exception:
        return False

def uptime_str():
    global start_time
    if not start_time:
        return "Not running"
    elapsed = int(time.time() - start_time)
    hrs, rem = divmod(elapsed, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hrs}h {mins}m {secs}s"

# ---------------- Forwarding Loop ----------------
async def forward_loop():
    global is_running, is_paused, _stop_signal, forwarded_count, start_time, last_processed_id

    src = safe_parse_chat(config.get("source"))
    tgt = safe_parse_chat(config.get("target"))

    if not src or not tgt:
        print("⚠️ Source or Target not set. Exiting forward loop.")
        is_running = False
        return

    is_running = True
    is_paused = False
    _stop_signal = False
    start_time = time.time()
    print("🔁 Forward loop started")

    try:
        async for msg in client.iter_messages(src, reverse=True):
            if _stop_signal:
                print("🛑 Stop signal received.")
                break

            if last_processed_id and getattr(msg, "id", None) <= last_processed_id:
                continue

            while is_paused:
                await asyncio.sleep(1)
                if _stop_signal:
                    break

            try:
                await client.forward_messages(tgt, msg)
                forwarded_count += 1
                last_processed_id = getattr(msg, "id", None)

                if forwarded_count % 50 == 0:
                    save_json(PROGRESS_FILE, {"last_id": last_processed_id, "count": forwarded_count})
                if forwarded_count % 100 == 0:
                    print(f"✅ Forwarded {forwarded_count} messages; last_id={last_processed_id}")

                if BATCH_SIZE > 0 and forwarded_count % BATCH_SIZE == 0:
                    print(f"💤 Batch reached ({BATCH_SIZE}). Resting {REST_MINUTES} minutes...")
                    save_json(PROGRESS_FILE, {"last_id": last_processed_id, "count": forwarded_count})
                    await asyncio.sleep(REST_MINUTES * 60)

                await asyncio.sleep(DELAY)

            except errors.FloodWaitError as e:
                wait = int(e.seconds) + 2
                print(f"⚠️ FloodWait: sleeping {wait}s")
                save_json(PROGRESS_FILE, {"last_id": last_processed_id, "count": forwarded_count})
                await asyncio.sleep(wait)
            except Exception as ex:
                print("❌ Error forwarding one message:", ex)
                await asyncio.sleep(2)

    except Exception as e:
        print("❌ Fatal error in forward loop:", e)

    save_json(PROGRESS_FILE, {"last_id": last_processed_id, "count": forwarded_count})
    print(f"🎉 Forward loop ended. Total forwarded: {forwarded_count}")
    is_running = False
    start_time = None

# ---------------- Telegram Commands ----------------
@client.on(events.NewMessage(pattern=r"^/start$"))
async def start_cmd(event):
    text = (
        "🤖 **Forward Bot — Control Panel**\n"
        "Use the buttons below to control forwarding."
    )
    buttons = [
        [Button.inline("▶️ Start Forward", b"start")],
        [Button.inline("⏸ Pause", b"pause"), Button.inline("▶️ Resume", b"resume")],
        [Button.inline("📊 Status", b"status"), Button.inline("🛑 Stop", b"stop")],
        [Button.inline("⚙️ Config", b"showcfg")]
    ]
    await event.respond(text, buttons=buttons)

@client.on(events.CallbackQuery)
async def cb_handler(event):
    global is_running, is_paused, _stop_signal
    data = event.data.decode()
    user = event.sender_id
    try:
        if data == "start":
            if not is_admin(user):
                return await event.answer("Unauthorized", alert=True)
            if not is_running:
                asyncio.create_task(forward_loop())
                await event.edit("▶️ Forwarding started.")
            else:
                await event.answer("Already running.", alert=True)

        elif data == "pause":
            if not is_admin(user):
                return await event.answer("Unauthorized", alert=True)
            is_paused = True
            await event.edit("⏸ Paused.")

        elif data == "resume":
            if not is_admin(user):
                return await event.answer("Unauthorized", alert=True)
            is_paused = False
            await event.edit("▶️ Resumed.")

        elif data == "stop":
            if not is_admin(user):
                return await event.answer("Unauthorized", alert=True)
            _stop_signal = True
            is_paused = False
            await event.edit("🛑 Stopping soon...")

        elif data == "status":
            msg = (
                f"📊 Status\nRunning: {is_running}\nPaused: {is_paused}\n"
                f"Forwarded: {forwarded_count}\nUptime: {uptime_str()}\n"
                f"Source: {config.get('source')}\nTarget: {config.get('target')}\nLastID: {last_processed_id}"
            )
            await event.edit(msg, buttons=[[Button.inline("◀ Back", b"back")]])

        elif data == "showcfg":
            cfg = (
                f"⚙️ Config:\nSource: {config.get('source')}\n"
                f"Target: {config.get('target')}\nAdmin: {config.get('admin')}"
            )
            await event.edit(cfg, buttons=[[Button.inline("◀ Back", b"back")]])

        elif data == "back":
            await start_cmd(event)

    except Exception as e:
        print("Callback error:", e)

# ---------------- FastAPI app ----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await client.start(bot_token=BOT_TOKEN)
        print("✅ Telegram client started")
        save_json(CONFIG_FILE, config)
        asyncio.create_task(_keep_alive())
        print("🚀 Bot ready. Use /start in Telegram.")
        yield
    finally:
        await client.disconnect()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def health():
    return {
        "status": "running",
        "forwarded": forwarded_count,
        "uptime": uptime_str(),
        "source": config.get("source"),
        "target": config.get("target")
    }

async def _keep_alive():
    while True:
        try:
            if not await client.is_connected():
                await client.connect()
        except Exception:
            pass
        await asyncio.sleep(30)

# ---------------- Run ----------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
