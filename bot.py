# ---------------- FULL FIXED FLOOD-SAFE BOT CODE ----------------
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import ChatWriteForbiddenError, FloodWaitError
import os, asyncio, json, threading, time
from fastapi import FastAPI
import uvicorn
import logging

logging.basicConfig(level=logging.INFO, filename="error.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")

# ---------------- FastAPI for Koyeb health check ----------------
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "Bot is alive!"}

# Run FastAPI in a separate thread
threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8080), daemon=True).start()

# ---------------- Bot Credentials ----------------
API_ID1 = 23684504
API_HASH1 = "07cbc3f3a8801f5a490174376d11c947"
SESSION1 = "1AZWarzgBuyawIlr49DwtLDlFuOI7Q2ySNiYMlgE0Oi9HNBgz-D_dPQEUJiOmjgVSicaiHs5JiBhTW4dF-U9JX16g51BxbBsVYrmY4cQnmm5h-mu0tc3PYjXQzOop0FOADP_ZVhNSg_jIIUg5UrrDZpUFwbw8hNiDTX_R2ZBJ-jkynAK0wsKXU6KF7cfjZTEgErjvydkbMOCZn3P1vGu97mjSkheDnQHqx9mVGJCFHgROgvuqB2WQEo9tbcr4kKyFMPHZKY8aH_XF8tigf1RacGZpJVXZ1qv_zki6fnIFFh3ftlQaaQq4YkuY8-NUbrrn19dPb5aSNS2NKRtT35uW3PtX1tHUYs4="
ADMIN1 = 8203758037

API_ID2 = 20649966
API_HASH2 = "070f71d4729e407515b2d1bfd372293f"
SESSION2 = "1AZWarzgBu3N7KM3aRae0mrGHKlznWllvqqosgFxz-ShoHyLV752OI7Rw3kY4r1zczttZV_WZO9sa6tVd1b9vkECLxgk4o-ty31jVZ_p84UOasWlAqpyDMVRffd_B0lN8uYqKs1ZV8uF2KQ78T5Okr_Vbiawu1vFdFc2b0nXdc7jkefmdS52KzMHY_fyUUiN1qfxQAcUEi__sbJm8auVKcuyLRxIWj6whLZ4xCH5RQMS_R9OFlqmOF697JjA84spbPdcK4cHf9HWXktP9NExfh1Tmv7B4fG3C5CGDh-gs_5aQ9tcleVTdDkL5-IShz9rFAtFw3-fHqaHRcRpWEWGdaOvtTKmmWKM="
ADMIN2 = 7890932840

GROUPS_FILE1 = "groups1.json"
SETTINGS_FILE1 = "settings1.json"
GROUPS_FILE2 = "groups2.json"
SETTINGS_FILE2 = "settings2.json"

# ---------------- Utility Functions ----------------
def load_data(groups_file, settings_file, default_msg):
    try: groups = set(json.load(open(groups_file)))
    except: groups = set()
    try:
        d = json.load(open(settings_file))
        return (
            groups,
            d.get("reply_msg", default_msg),
            d.get("delete_delay", 15),
            d.get("reply_gap", 30),
            d.get("pm_msg", None)
        )
    except:
        return groups, default_msg, 15, 30, None

def save_groups(path, groups):
    json.dump(list(groups), open(path, "w"))

def save_settings(path, msg, d, g, pm_msg):
    json.dump({"reply_msg": msg, "delete_delay": d, "reply_gap": g, "pm_msg": pm_msg}, open(path, "w"))

# ---------------- Load Settings ----------------
groups1, msg1, delay1, gap1, pm_msg1 = load_data(GROUPS_FILE1, SETTINGS_FILE1, "🤖 Bot1 here!")
groups2, msg2, delay2, gap2, pm_msg2 = load_data(GROUPS_FILE2, SETTINGS_FILE2, "👥 Bot2 here!")

last_reply1, last_reply2 = {}, {}  # per-user last reply timestamp
flood_active1 = False
flood_active2 = False

client1 = TelegramClient(StringSession(SESSION1), API_ID1, API_HASH1)
client2 = TelegramClient(StringSession(SESSION2), API_ID2, API_HASH2)

# ---------------- Safe Reply Function ----------------
async def safe_reply(client, chat_id, user_id, msg, last_reply, gap, flood_flag_name):
    global flood_active1, flood_active2
    now = time.time()
    if now - last_reply.get(user_id, 0) < gap:  # per-user cooldown
        return
    try:
        m = await client.send_message(chat_id, msg)
        last_reply[user_id] = time.time()
        if m and hasattr(m, 'delete') and ((client==client1 and delay1>0) or (client==client2 and delay2>0)):
            await asyncio.sleep(delay1 if client==client1 else delay2)
            await m.delete()
    except FloodWaitError as e:
        if flood_flag_name == "flood_active1":
            flood_active1 = True
        else:
            flood_active2 = True
        await asyncio.sleep(e.seconds)
        if flood_flag_name == "flood_active1":
            flood_active1 = False
        else:
            flood_active2 = False
    except ChatWriteForbiddenError:
        pass
    except Exception as e:
        logging.error(f"[Safe Reply] {e}")

# ---------------- Bot Handlers ----------------
@client1.on(events.NewMessage)
async def bot1_handler(event):
    global flood_active1
    if event.is_private and pm_msg1:
        m = await event.reply(pm_msg1)
        await asyncio.sleep(60)
        await m.delete()
    elif event.chat_id in groups1 and not event.sender.bot:
        if flood_active1:
            return
        await safe_reply(client1, event.chat_id, event.sender_id, msg1, last_reply1, gap1, "flood_active1")

@client2.on(events.NewMessage)
async def bot2_handler(event):
    global flood_active2
    if event.is_private and pm_msg2:
        m = await event.reply(pm_msg2)
        await asyncio.sleep(60)
        await m.delete()
    elif event.chat_id in groups2 and not event.sender.bot:
        if flood_active2:
            return
        await safe_reply(client2, event.chat_id, event.sender_id, msg2, last_reply2, gap2, "flood_active2")

# ---------------- Admin Handlers ----------------
def admin_handler(client, event, admin_id, groups, settings_file):
    global msg1, msg2, delay1, delay2, gap1, gap2, pm_msg1, pm_msg2
    txt = event.raw_text.strip()
    if event.sender_id != admin_id:
        return
    if event.is_private:
        if txt.startswith("/addgroup"):
            try: gid = int(txt.split(" ",1)[1])
            except: return asyncio.create_task(event.reply("❌ Usage: /addgroup -100xxxx"))
            groups.add(gid)
            save_groups(settings_file.replace("settings","groups"), groups)
            return asyncio.create_task(event.reply(f"✅ Added {gid}"))
        elif txt.startswith("/removegroup"):
            try: gid = int(txt.split(" ",1)[1])
            except: return asyncio.create_task(event.reply("❌ Usage: /removegroup -100xxxx"))
            groups.discard(gid)
            save_groups(settings_file.replace("settings","groups"), groups)
            return asyncio.create_task(event.reply(f"❌ Removed {gid}"))
        elif txt.startswith("/setmsgpm "):
            if client==client1: pm_msg1 = txt.split(" ",1)[1]
            else: pm_msg2 = txt.split(" ",1)[1]
            save_settings(settings_file, msg1 if client==client1 else msg2,
                          delay1 if client==client1 else delay2,
                          gap1 if client==client1 else gap2,
                          pm_msg1 if client==client1 else pm_msg2)
            return asyncio.create_task(event.reply("✅ PM auto-reply set."))
        elif txt=="/setmsgpmoff":
            if client==client1: pm_msg1=None
            else: pm_msg2=None
            save_settings(settings_file, msg1 if client==client1 else msg2,
                          delay1 if client==client1 else delay2,
                          gap1 if client==client1 else gap2,
                          pm_msg1 if client==client1 else pm_msg2)
            return asyncio.create_task(event.reply("❌ PM auto-reply turned off."))

# ---------------- Start Clients ----------------
async def start_clients():
    await client1.start()
    await client2.start()
    print("✅ Bots are running...")
    await asyncio.gather(client1.run_until_disconnected(), client2.run_until_disconnected())

asyncio.get_event_loop().run_until_complete(start_clients())
