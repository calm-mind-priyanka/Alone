from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import ChatWriteForbiddenError
import os, asyncio, json, threading, time
from fastapi import FastAPI
import uvicorn
import logging

# Logging
logging.basicConfig(level=logging.INFO, filename="error.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")

# FastAPI health check for Koyeb
app = FastAPI()
@app.get("/")
async def root():
    return {"status": "Bot is alive!"}
threading.Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8080), daemon=True).start()

# Bot 1 credentials
API_ID1 = 22492935
API_HASH1 = "4a4e08f1059532c2116384e08519847c"
SESSION1 = "1BVtsOJwBuynZGBfI9g3k69uqogCymAMdh5yfIkSeEyii_-dYJzYHijzetuIvgQpahD-_6fgWCzfzK4CjgME4KRcUfFoxPg67NPKqIBAB-0PHh2li3cvkhU-9IySltoJnke4ZfF1tpF2dCj9OcQhd9LZTek9fF-aKW4bERNtLg0pWTNp3CC_oCS6rCkibKxubmoPhV-8pzcN9taOjPRMzqZuwf6FTEmNq1r6Y63l2FRi9JxyrqTrznpHgoQ3YsIN6xA4qj8ELBdsFdSOZYWTekL31a0gScS5ZelHCnWbcQPlsu-kJKfD1ayjMxWOU27N7B-okKMI1V4OfYFPm8C5QoAjxCE07OVk="
ADMIN1 = 8194528281

# Bot 2 credentials
API_ID2 = 25801447
API_HASH2 = "1b2905795e78355baf7e289183bccb9a"
SESSION2 = "1BVtsOJwBu11_cQ5HN1VHctDPK7jEPaGWMsDTFGz7gksmVUMNoQxeztgDPhUY2AVDwgE5XzmFz2f70WU9NOaBv9l2X4NrnyXM4Wa1r57CdkjVEmykLueeNZJrE2pYvJ-zM_VJPYIFVDQuPCF4tIX3_qu5u_YAXNlPfVl63us2CgMl85q3pfRcF1SC5FyErD_cc8jd9P4BYir4-fUb8Nmws9XN77JMaFs-Euk17uenf151Nx7sOhG5r7EG3-eiiSDe384NG7AIR4KaHQFg6xVcoV1p62S_moNE8oYocPijp80ACvgm1Bi5sYKZYRmB6sMoMaG8p7B1eYV-qyIyDRc2UFR7r1_u9Ng="
ADMIN2 = 7554623404

# File paths
GROUPS_FILE1 = "groups1.json"
SETTINGS_FILE1 = "settings1.json"
GROUPS_FILE2 = "groups2.json"
SETTINGS_FILE2 = "settings2.json"

# Load/save
def load_data(groups_file, settings_file, default_msg):
    try: groups = set(json.load(open(groups_file)))
    except: groups = set()
    try:
        d = json.load(open(settings_file))
        return groups, d.get("reply_msg", default_msg), d.get("delete_delay", 15), d.get("reply_gap", 30)
    except: return groups, default_msg, 15, 30

def save_groups(path, groups): json.dump(list(groups), open(path, "w"))
def save_settings(path, msg, d, g): json.dump({"reply_msg": msg, "delete_delay": d, "reply_gap": g}, open(path, "w"))

# Configs
groups1, msg1, delay1, gap1 = load_data(GROUPS_FILE1, SETTINGS_FILE1, "🤖 Bot1 here!")
groups2, msg2, delay2, gap2 = load_data(GROUPS_FILE2, SETTINGS_FILE2, "👥 Bot2 here!")
last_reply1, last_reply2 = {}, {}

# Clients
client1 = TelegramClient(StringSession(SESSION1), API_ID1, API_HASH1)
client2 = TelegramClient(StringSession(SESSION2), API_ID2, API_HASH2)

# Message reply logic
@client1.on(events.NewMessage)
async def bot1_handler(event):
    try:
        if event.chat_id in groups1 and not event.sender.bot:
            now = time.time()
            if now - last_reply1.get(event.chat_id, 0) < gap1: return
            last_reply1[event.chat_id] = now
            m = await event.reply(msg1)
            if delay1 > 0: await asyncio.sleep(delay1); await m.delete()
    except ChatWriteForbiddenError: pass
    except Exception as e: logging.error(f"[Bot1] {e}")

@client2.on(events.NewMessage)
async def bot2_handler(event):
    try:
        if event.chat_id in groups2 and not event.sender.bot:
            now = time.time()
            if now - last_reply2.get(event.chat_id, 0) < gap2: return
            last_reply2[event.chat_id] = now
            m = await event.reply(msg2)
            if delay2 > 0: await asyncio.sleep(delay2); await m.delete()
    except ChatWriteForbiddenError: pass
    except Exception as e: logging.error(f"[Bot2] {e}")

# Admin commands - Bot 1
@client1.on(events.NewMessage)
async def bot1_commands(e):
    global msg1, delay1, gap1
    if e.sender_id != ADMIN1: return
    txt = e.raw_text.strip()
    chat_id = e.chat_id

    if e.is_private and txt.startswith("/addgroup"):
        try: group_id = int(txt.split(" ", 1)[1])
        except: return await e.reply("❌ Usage: /addgroup -100xxxx")
        groups1.add(group_id); save_groups(GROUPS_FILE1, groups1)
        return await e.reply(f"✅ Group `{group_id}` added.")

    elif e.is_private and txt.startswith("/removegroup"):
        try: group_id = int(txt.split(" ", 1)[1])
        except: return await e.reply("❌ Usage: /removegroup -100xxxx")
        groups1.discard(group_id); save_groups(GROUPS_FILE1, groups1)
        return await e.reply(f"❌ Group `{group_id}` removed.")

    elif not e.is_private and txt == "/add":
        groups1.add(chat_id); save_groups(GROUPS_FILE1, groups1)
        return await e.reply("✅ Group added.")

    elif not e.is_private and txt == "/remove":
        groups1.discard(chat_id); save_groups(GROUPS_FILE1, groups1)
        return await e.reply("❌ Group removed.")

    elif txt.startswith("/setmsg"):
        try: msg1 = txt.split(" ", 1)[1]; save_settings(SETTINGS_FILE1, msg1, delay1, gap1); await e.reply("✅ Message set")
        except: await e.reply("❌ Usage: /setmsg your message")

    elif txt.startswith("/setdel"):
        try: delay1 = int(txt.split(" ", 1)[1]); save_settings(SETTINGS_FILE1, msg1, delay1, gap1); await e.reply("✅ Delete delay set")
        except: await e.reply("❌ Usage: /setdel 10")

    elif txt.startswith("/setgap"):
        try: gap1 = int(txt.split(" ", 1)[1]); save_settings(SETTINGS_FILE1, msg1, delay1, gap1); await e.reply("✅ Reply gap set")
        except: await e.reply("❌ Usage: /setgap 30")

    elif txt == "/ping": await e.reply("🏓 Bot1 alive!")
    elif txt == "/status":
        await e.reply(f"Bot1 Status:\nGroups: {len(groups1)}\nMsg: {msg1}\nDelete: {delay1}s\nGap: {gap1}s")

# Admin commands - Bot 2
@client2.on(events.NewMessage)
async def bot2_commands(e):
    global msg2, delay2, gap2
    if e.sender_id != ADMIN2: return
    txt = e.raw_text.strip()
    chat_id = e.chat_id

    if e.is_private and txt.startswith("/addgroup"):
        try: group_id = int(txt.split(" ", 1)[1])
        except: return await e.reply("❌ Usage: /addgroup -100xxxx")
        groups2.add(group_id); save_groups(GROUPS_FILE2, groups2)
        return await e.reply(f"✅ Group `{group_id}` added.")

    elif e.is_private and txt.startswith("/removegroup"):
        try: group_id = int(txt.split(" ", 1)[1])
        except: return await e.reply("❌ Usage: /removegroup -100xxxx")
        groups2.discard(group_id); save_groups(GROUPS_FILE2, groups2)
        return await e.reply(f"❌ Group `{group_id}` removed.")

    elif not e.is_private and txt == "/add":
        groups2.add(chat_id); save_groups(GROUPS_FILE2, groups2)
        return await e.reply("✅ Group added.")

    elif not e.is_private and txt == "/remove":
        groups2.discard(chat_id); save_groups(GROUPS_FILE2, groups2)
        return await e.reply("❌ Group removed.")

    elif txt.startswith("/setmsg"):
        try: msg2 = txt.split(" ", 1)[1]; save_settings(SETTINGS_FILE2, msg2, delay2, gap2); await e.reply("✅ Message set")
        except: await e.reply("❌ Usage: /setmsg your message")

    elif txt.startswith("/setdel"):
        try: delay2 = int(txt.split(" ", 1)[1]); save_settings(SETTINGS_FILE2, msg2, delay2, gap2); await e.reply("✅ Delete delay set")
        except: await e.reply("❌ Usage: /setdel 10")

    elif txt.startswith("/setgap"):
        try: gap2 = int(txt.split(" ", 1)[1]); save_settings(SETTINGS_FILE2, msg2, delay2, gap2); await e.reply("✅ Reply gap set")
        except: await e.reply("❌ Usage: /setgap 30")

    elif txt == "/ping": await e.reply("🏓 Bot2 alive!")
    elif txt == "/status":
        await e.reply(f"Bot2 Status:\nGroups: {len(groups2)}\nMsg: {msg2}\nDelete: {delay2}s\nGap: {gap2}s")

# Start both clients
async def start_clients():
    try: await client1.start()
    except Exception as e: logging.error(f"[Client1 Start Failed] {e}")
    try: await client2.start()
    except Exception as e: logging.error(f"[Client2 Start Failed] {e}")
    tasks = []
    if client1.is_connected(): tasks.append(client1.run_until_disconnected())
    if client2.is_connected(): tasks.append(client2.run_until_disconnected())
    print("✅ Running bots...")
    if tasks: await asyncio.gather(*tasks)
    else: print("❌ Both sessions failed.")

asyncio.get_event_loop().run_until_complete(start_clients())
