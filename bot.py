# bot.py
import os
import asyncio
import json
import time
from typing import Optional
from fastapi import FastAPI
import uvicorn
from telethon import TelegramClient, events, Button, errors

# ---------------- Config (env or default) ----------------
API_ID = int(os.getenv("API_ID", "0"))           # set in Koyeb or here
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = os.getenv("ADMIN_ID")                 # optional: numeric Telegram user id string
DELAY = float(os.getenv("DELAY", 1.2))          # seconds between forwards
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 5000)) # triggers rest
REST_MINUTES = int(os.getenv("REST_MINUTES", 10))
CONFIG_FILE = os.getenv("CONFIG_FILE", "config.json")
PROGRESS_FILE = os.getenv("PROGRESS_FILE", "forward_progress.json")

# ---------------- Telethon client & FastAPI ----------------
client = TelegramClient("forward_session", API_ID, API_HASH)
app = FastAPI()

# ---------------- Runtime state ----------------
is_running = False
is_paused = False
_stop_signal = False
forwarded_count = 0
start_time = None
last_processed_id = None

# ---------------- Helper: config & progress persistence ----------------
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

# default config structure
config = load_json(CONFIG_FILE)
# expected keys in config: source (int or str), target (int or str), admin (str)
# allow override from env
if "admin" not in config and ADMIN_ID:
    config["admin"] = ADMIN_ID
if "source" not in config:
    config["source"] = os.getenv("SOURCE_CHAT")  # optional initial set
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
        return value  # probably @username

def is_admin(user_id: int) -> bool:
    # If admin set in config, only that admin can run privileged commands
    adm = config.get("admin")
    if not adm:
        return True  # no admin set -> allow everyone (use only for testing)
    try:
        return int(adm) == int(user_id)
    except Exception:
        return False

# ---------------- Utility ----------------
def uptime_str():
    global start_time
    if not start_time:
        return "Not running"
    elapsed = int(time.time() - start_time)
    hrs, rem = divmod(elapsed, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hrs}h {mins}m {secs}s"

# ---------------- Forward loop ----------------
async def forward_loop():
    """
    Core forward loop: iterates messages from source (oldest->newest),
    skips messages already forwarded (using last_processed_id), forwards to target.
    """
    global is_running, is_paused, _stop_signal, forwarded_count, start_time, last_processed_id

    src = safe_parse_chat(config.get("source"))
    tgt = safe_parse_chat(config.get("target"))

    if not src or not tgt:
        print("Source or Target not set. Exiting forward loop.")
        is_running = False
        return

    is_running = True
    is_paused = False
    _stop_signal = False
    start_time = time.time()
    print("🔁 Forward loop started")

    try:
        # iterate oldest to newest so resume is easier; reverse=True gives oldest first
        async for msg in client.iter_messages(src, reverse=True):
            if _stop_signal:
                print("🛑 Stop signal received.")
                break

            # skip messages already forwarded (if resuming)
            if last_processed_id and getattr(msg, "id", None) <= last_processed_id:
                continue

            # pause handling
            while is_paused:
                await asyncio.sleep(1)
                if _stop_signal:
                    break

            try:
                # forward
                await client.forward_messages(tgt, msg)
                forwarded_count += 1
                last_processed_id = getattr(msg, "id", None)

                # save progress periodically
                if forwarded_count % 50 == 0:
                    save_json(PROGRESS_FILE, {"last_id": last_processed_id, "count": forwarded_count})

                if forwarded_count % 100 == 0:
                    print(f"✅ Forwarded {forwarded_count} messages; last_id={last_processed_id}")

                # rest after batch
                if BATCH_SIZE > 0 and forwarded_count % BATCH_SIZE == 0:
                    print(f"💤 Batch reached ({BATCH_SIZE}). Resting {REST_MINUTES} minutes...")
                    save_json(PROGRESS_FILE, {"last_id": last_processed_id, "count": forwarded_count})
                    await asyncio.sleep(REST_MINUTES * 60)

                # small delay between forwards
                await asyncio.sleep(DELAY)

            except errors.FloodWaitError as e:
                wait = int(e.seconds) + 2
                print(f"⚠️ FloodWait: sleeping {wait}s")
                save_json(PROGRESS_FILE, {"last_id": last_processed_id, "count": forwarded_count})
                await asyncio.sleep(wait)
            except Exception as ex:
                print("❌ Error forwarding one message:", ex)
                # continue with next message; short delay to avoid tight error loop
                await asyncio.sleep(2)

    except Exception as e:
        print("❌ Fatal error in forward loop:", e)

    # final save
    save_json(PROGRESS_FILE, {"last_id": last_processed_id, "count": forwarded_count})
    print(f"🎉 Forward loop ended. Total forwarded: {forwarded_count}")
    is_running = False
    start_time = None

# ---------------- Commands & Callbacks ----------------
@client.on(events.NewMessage(pattern=r"^/start$"))
async def cmd_start(event):
    # welcome + inline control panel
    text = "🤖 Forward Bot — Control Panel\nUse the buttons below to control forwarding."
    buttons = [
        [Button.inline("▶️ Start Forward", b"start")],
        [Button.inline("⏸ Pause", b"pause"), Button.inline("▶️ Resume", b"resume")],
        [Button.inline("📊 Status", b"status"), Button.inline("🛑 Stop", b"stop")],
        [Button.inline("⚙️ Show Config", b"showcfg")]
    ]
    await event.respond(text, buttons=buttons)

@client.on(events.CallbackQuery)
async def callback_handler(event):
    global is_running, is_paused, _stop_signal
    data = event.data.decode() if event.data else ""
    user_id = event.sender_id
    try:
        if data == "start":
            if not is_admin(user_id):
                await event.answer("Unauthorized", alert=True); return
            if not is_running:
                await event.answer("Starting forward loop...", alert=False)
                asyncio.create_task(forward_loop())
                await event.edit("▶️ Forwarding started.")
            else:
                await event.answer("Already running.", alert=True)

        elif data == "pause":
            if not is_admin(user_id):
                await event.answer("Unauthorized", alert=True); return
            if is_running and not is_paused:
                is_paused = True
                await event.answer("Paused", alert=True)
                await event.edit("⏸ Forwarding paused. Use Resume to continue.")
            else:
                await event.answer("Cannot pause now.", alert=True)

        elif data == "resume":
            if not is_admin(user_id):
                await event.answer("Unauthorized", alert=True); return
            if is_running and is_paused:
                is_paused = False
                await event.answer("Resumed", alert=True)
                await event.edit("▶️ Forwarding resumed.")
            else:
                await event.answer("Cannot resume now.", alert=True)

        elif data == "stop":
            if not is_admin(user_id):
                await event.answer("Unauthorized", alert=True); return
            if is_running:
                _stop_signal = True
                is_paused = False
                await event.answer("Stopping...", alert=True)
                await event.edit("🛑 Stopping forwarding. It will stop after the current message.")
            else:
                await event.answer("Not running.", alert=True)

        elif data == "status":
            msg = (
                f"📊 Status\nRunning: {is_running}\nPaused: {is_paused}\n"
                f"Forwarded: {forwarded_count}\nUptime: {uptime_str()}\n"
                f"Source: {config.get('source')}\nTarget: {config.get('target')}\nLastID: {last_processed_id}"
            )
            await event.answer("Status", alert=True)
            await event.edit(msg, buttons=[[Button.inline("◀ Back", b"start")]])

        elif data == "showcfg":
            cfg = f"Source: {config.get('source')}\nTarget: {config.get('target')}\nAdmin: {config.get('admin')}"
            await event.answer("Config", alert=True)
            await event.edit(f"⚙️ Current Config:\n\n{cfg}", buttons=[[Button.inline("◀ Back", b"start")]])
        else:
            await event.answer("Unknown action.", alert=True)
    except Exception as e:
        print("Callback error:", e)

# ---------------- Text commands for admin control ----------------
@client.on(events.NewMessage(pattern=r"^/status$"))
async def cmd_status(event):
    await event.reply(
        f"📊 Status\nRunning: {is_running}\nPaused: {is_paused}\n"
        f"Forwarded: {forwarded_count}\nUptime: {uptime_str()}\n"
        f"Source: {config.get('source')}\nTarget: {config.get('target')}\nLastID: {last_processed_id}"
    )

@client.on(events.NewMessage(pattern=r"^/pause$"))
async def cmd_pause(event):
    user = event.sender_id
    if not is_admin(user):
        await event.reply("❌ Unauthorized")
        return
    global is_paused
    if is_running and not is_paused:
        is_paused = True
        await event.reply("⏸ Bot paused.")
    else:
        await event.reply("Bot not running or already paused.")

@client.on(events.NewMessage(pattern=r"^/resume$"))
async def cmd_resume(event):
    user = event.sender_id
    if not is_admin(user):
        await event.reply("❌ Unauthorized")
        return
    global is_paused
    if is_running and is_paused:
        is_paused = False
        await event.reply("▶️ Bot resumed.")
    else:
        await event.reply("Bot not paused or not running.")

@client.on(events.NewMessage(pattern=r"^/stop$"))
async def cmd_stop(event):
    user = event.sender_id
    if not is_admin(user):
        await event.reply("❌ Unauthorized")
        return
    global _stop_signal, is_paused
    if is_running:
        _stop_signal = True
        is_paused = False
        await event.reply("🛑 Stopping forwarding (will stop soon).")
    else:
        await event.reply("Bot not running.")

# ---------------- Commands to set/change/remove source & target ----------------
@client.on(events.NewMessage(pattern=r"^/setsource\s+(.+)$"))
async def cmd_setsource(event):
    user = event.sender_id
    if not is_admin(user):
        await event.reply("❌ Unauthorized"); return
    new_src = event.pattern_match.group(1).strip()
    config["source"] = new_src
    save_json(CONFIG_FILE, config)
    await event.reply(f"✅ Source channel set to: {new_src}")

@client.on(events.NewMessage(pattern=r"^/settarget\s+(.+)$"))
async def cmd_settarget(event):
    user = event.sender_id
    if not is_admin(user):
        await event.reply("❌ Unauthorized"); return
    new_tgt = event.pattern_match.group(1).strip()
    config["target"] = new_tgt
    save_json(CONFIG_FILE, config)
    await event.reply(f"✅ Target channel set to: {new_tgt}")

@client.on(events.NewMessage(pattern=r"^/removesource$"))
async def cmd_removesource(event):
    user = event.sender_id
    if not is_admin(user):
        await event.reply("❌ Unauthorized"); return
    config.pop("source", None)
    save_json(CONFIG_FILE, config)
    await event.reply("✅ Source removed.")

@client.on(events.NewMessage(pattern=r"^/removetarget$"))
async def cmd_removetarget(event):
    user = event.sender_id
    if not is_admin(user):
        await event.reply("❌ Unauthorized"); return
    config.pop("target", None)
    save_json(CONFIG_FILE, config)
    await event.reply("✅ Target removed.")

@client.on(events.NewMessage(pattern=r"^/showconfig$"))
async def cmd_showconfig(event):
    user = event.sender_id
    if not is_admin(user):
        await event.reply("❌ Unauthorized"); return
    await event.reply(f"⚙️ Current config:\n\nSource: {config.get('source')}\nTarget: {config.get('target')}\nAdmin: {config.get('admin')}")

# ---------------- FastAPI health route ----------------
@app.get("/")
def health():
    return {"status": "running", "forwarded": forwarded_count, "uptime": uptime_str(), "source": config.get("source"), "target": config.get("target")}

# ---------------- Startup: initialize client ----------------
@app.on_event("startup")
async def startup_event():
    try:
        await client.start(bot_token=BOT_TOKEN)
        print("✅ Telegram client started")
    except Exception as e:
        print("❌ Error starting Telegram client:", e)
        raise

    # ensure config persisted
    save_json(CONFIG_FILE, config)
    # keep the telethon client alive
    asyncio.create_task(_keep_client_alive())
    # Note: forward_loop is NOT auto-started on startup. Use Start button or /start to begin.
    print("🚀 Bot ready. Use /start in Telegram to open control panel.")

async def _keep_client_alive():
    # keep client connected (reconnect-friendly)
    while True:
        try:
            if not await client.is_connected():
                try:
                    await client.connect()
                except Exception:
                    pass
        except Exception:
            pass
        await asyncio.sleep(20)

# ---------------- Run ----------------
if __name__ == "__main__":
    # run fastapi via uvicorn (Koyeb expects a web port)
    uvicorn.run(app, host="0.0.0.0", port=8080)
