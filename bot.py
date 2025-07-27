from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import ChatWriteForbiddenError
import os, asyncio, json, threading, time
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import uvicorn
import logging

# ✅ Logging Setup
logging.basicConfig(level=logging.INFO, filename="error.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")

# ✅ FastAPI Health Check for Koyeb & UptimeRobot
app = FastAPI()

@app.get("/", response_class=PlainTextResponse)
async def root():
    return "OK"  # Plain text to prevent Koyeb monitor issue

threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8080), daemon=True).start()

# ✅ Credentials for Both Bots
API_ID1 = 123456
API_HASH1 = "abc123"
SESSION1 = "1Axxxxxxxxxx"
ADMIN1 = 111111111

API_ID2 = 654321
API_HASH2 = "xyz789"
SESSION2 = "1Bxxxxxxxxxx"
ADMIN2 = 222222222

GROUPS_FILE1 = "groups1.json"
SETTINGS_FILE1 = "settings1.json"
GROUPS_FILE2 = "groups2.json"
SETTINGS_FILE2 = "settings2.json"

# ✅ Load/Save Functions
def load_data(groups_file, settings_file, default_msg):
    try:
        with open(groups_file) as f:
            groups = set(json.load(f))
    except:
        groups = set()
    try:
        with open(settings_file) as f:
            d = json.load(f)
            return groups, d.get("reply_msg", default_msg), d.get("delete_delay", 15), d.get("reply_gap", 30)
    except:
        return groups, default_msg, 15, 30

def save_groups(path, groups):
    json.dump(list(groups), open(path, "w"))

def save_settings(path, msg, d, g):
    json.dump({"reply_msg": msg, "delete_delay": d, "reply_gap": g}, open(path, "w"))

# ✅ Load Configs
groups1, msg1, delay1, gap1 = load_data(GROUPS_FILE1, SETTINGS_FILE1, "🤖 Bot1 here!")
groups2, msg2, delay2, gap2 = load_data(GROUPS_FILE2, SETTINGS_FILE2, "👥 Bot2 here!")
last_reply1, last_reply2 = {}, {}

# ✅ Telethon Clients
client1 = TelegramClient(StringSession(SESSION1), API_ID1, API_HASH1)
client2 = TelegramClient(StringSession(SESSION2), API_ID2, API_HASH2)

# ✅ Bot 1 Handler
@client1.on(events.NewMessage)
async def handle1(event):
    global msg1, delay1, gap1
    try:
        sender = await event.get_sender()
        if event.chat_id in groups1 and not sender.bot:
            now = time.time()
            if now - last_reply1.get(event.chat_id, 0) < gap1:
                return
            last_reply1[event.chat_id] = now
            m = await event.reply(msg1)
            if delay1 > 0:
                await asyncio.sleep(delay1)
                await m.delete()
    except ChatWriteForbiddenError:
        pass
    except Exception as e:
        logging.error(f"[Bot1] {e}")

# ✅ Bot 2 Handler
@client2.on(events.NewMessage)
async def handle2(event):
    global msg2, delay2, gap2
    try:
        sender = await event.get_sender()
        if event.chat_id in groups2 and not sender.bot:
            now = time.time()
            if now - last_reply2.get(event.chat_id, 0) < gap2:
                return
            last_reply2[event.chat_id] = now
            m = await event.reply(msg2)
            if delay2 > 0:
                await asyncio.sleep(delay2)
                await m.delete()
    except ChatWriteForbiddenError:
        pass
    except Exception as e:
        logging.error(f"[Bot2] {e}")

# ✅ Admin Commands – Bot 1
@client1.on(events.NewMessage(pattern="/add"))
async def add1(e):
    if e.sender_id == ADMIN1:
        groups1.add(e.chat_id)
        save_groups(GROUPS_FILE1, groups1)
        await e.reply("✅ Added")

@client1.on(events.NewMessage(pattern="/setmsg"))
async def setmsg1(e):
    global msg1
    if e.sender_id == ADMIN1:
        try:
            msg1 = e.raw_text.split(" ", 1)[1]
            save_settings(SETTINGS_FILE1, msg1, delay1, gap1)
            await e.reply("✅ Msg set")
        except:
            await e.reply("❌ Usage: /setmsg text")

@client1.on(events.NewMessage(pattern="/setdel"))
async def setdel1(e):
    global delay1
    if e.sender_id == ADMIN1:
        try:
            delay1 = int(e.raw_text.split(" ", 1)[1])
            save_settings(SETTINGS_FILE1, msg1, delay1, gap1)
            await e.reply("✅ Delete set")
        except:
            await e.reply("❌ Usage: /setdel seconds")

@client1.on(events.NewMessage(pattern="/setgap"))
async def setgap1(e):
    global gap1
    if e.sender_id == ADMIN1:
        try:
            gap1 = int(e.raw_text.split(" ", 1)[1])
            save_settings(SETTINGS_FILE1, msg1, delay1, gap1)
            await e.reply("✅ Gap set")
        except:
            await e.reply("❌ Usage: /setgap seconds")

@client1.on(events.NewMessage(pattern="/ping"))
async def ping1(e):
    if e.sender_id == ADMIN1:
        await e.reply("🏓 Bot1 alive!")

@client1.on(events.NewMessage(pattern="/status"))
async def status1(e):
    if e.sender_id == ADMIN1:
        await e.reply(f"🔧 Bot1 Status:\nGroups: {len(groups1)}\nMsg: {msg1}\nGap: {gap1}s\nDelete: {delay1}s")

# ✅ Admin Commands – Bot 2
@client2.on(events.NewMessage(pattern="/add"))
async def add2(e):
    if e.sender_id == ADMIN2:
        groups2.add(e.chat_id)
        save_groups(GROUPS_FILE2, groups2)
        await e.reply("✅ Added")

@client2.on(events.NewMessage(pattern="/setmsg"))
async def setmsg2(e):
    global msg2
    if e.sender_id == ADMIN2:
        try:
            msg2 = e.raw_text.split(" ", 1)[1]
            save_settings(SETTINGS_FILE2, msg2, delay2, gap2)
            await e.reply("✅ Msg set")
        except:
            await e.reply("❌ Usage: /setmsg text")

@client2.on(events.NewMessage(pattern="/setdel"))
async def setdel2(e):
    global delay2
    if e.sender_id == ADMIN2:
        try:
            delay2 = int(e.raw_text.split(" ", 1)[1])
            save_settings(SETTINGS_FILE2, msg2, delay2, gap2)
            await e.reply("✅ Delete set")
        except:
            await e.reply("❌ Usage: /setdel seconds")

@client2.on(events.NewMessage(pattern="/setgap"))
async def setgap2(e):
    global gap2
    if e.sender_id == ADMIN2:
        try:
            gap2 = int(e.raw_text.split(" ", 1)[1])
            save_settings(SETTINGS_FILE2, msg2, delay2, gap2)
            await e.reply("✅ Gap set")
        except:
            await e.reply("❌ Usage: /setgap seconds")

@client2.on(events.NewMessage(pattern="/ping"))
async def ping2(e):
    if e.sender_id == ADMIN2:
        await e.reply("🏓 Bot2 alive!")

@client2.on(events.NewMessage(pattern="/status"))
async def status2(e):
    if e.sender_id == ADMIN2:
        await e.reply(f"🔧 Bot2 Status:\nGroups: {len(groups2)}\nMsg: {msg2}\nGap: {gap2}s\nDelete: {delay2}s")

# ✅ Start Both Clients Together
async def start_clients():
    await client1.start()
    await client2.start()
    print("✅ Running bots...")
    await asyncio.gather(client1.run_until_disconnected(), client2.run_until_disconnected())

asyncio.get_event_loop().run_until_complete(start_clients())
