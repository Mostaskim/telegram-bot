import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from flask import Flask
import threading

# --- 1. CONFIGURATION ---
TOKEN = "8819749952:AAH5Gcu-Grm4hnNPTxPk6gOFRhHph93qG50"  # BotFather theke pawa apnar bot token-ti ekhane boshan
TOTAL_ADS = 3                  # Koyta click/ad complete korte hobe
TARGET_VIDEO_ID = "YOUR_TELEGRAM_VIDEO_FILE_ID"  # Jei video-ti pathaben tar File ID

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_progress = {}

# --- 2. KEEP ALIVE (Flask Server) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

# --- 3. BOT LOGIC ---
@dp.message(Command("start"))
async def start_command(message: types.Message):
    user_id = message.from_user.id
    user_progress[user_id] = 0
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🔓 UNLOCK NOW (0/{TOTAL_ADS})", callback_data="watch_ad")]
    ])
    
    await message.answer(
        "👋 Assalamu Alaikum! Video-ti dekhar jonno niche button-e click kore task complete korun.",
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "watch_ad")
async def process_ad(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in user_progress:
        user_progress[user_id] = 0
        
    user_progress[user_id] += 1
    current_step = user_progress[user_id]
    
    if current_step < TOTAL_ADS:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"⏳ Please Wait / Watch ({current_step}/{TOTAL_ADS})", callback_data="watch_ad")]
        ])
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer(f"Step {current_step} completed! Abar click korun.", show_alert=False)
    else:
        await callback.message.delete()
        
        sent_msg = await bot.send_video(
            chat_id=callback.message.chat.id,
            video=TARGET_VIDEO_ID,
            caption="🎉 Congratulations! Apnar video unlock hoyeche. Ei video-ti 1 minute por vanish (delete) hoye jabe."
        )
        
        await callback.answer("Video Unlocked!", show_alert=True)
        
        # 1 minute (60 seconds) por video auto-delete hobar logic
        await asyncio.sleep(60)
        try:
            await bot.delete_message(chat_id=sent_msg.chat.id, message_id=sent_msg.message_id)
        except Exception as e:
            print(f"Error deleting message: {e}")

# --- 4. MAIN FUNCTION ---
async def main():
    print("Bot is running successfully...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    keep_alive()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

import asyncio
import logging
from flask import Flask, render_template, request
import threading

# Flask app initialize kora
app = Flask(__name__)

@app.route('/watch')
def watch_page():
    video_id = request.args.get('id', 'default_video')
    return render_template('watch.html', video_id=video_id)

# Flask server-ke alada thread-e chalanor jonno function
def run_flask():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# Telegram Bot run korar main async function
async def main():
    # Puraton kono update thakle seta bad diye fresh polling start kora
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot is running successfully...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    # 1. Prothome Flask server-ke background thread-e start korchi
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("Flask server is running on http://127.0.0.1:8080")

    # 2. Tarpor aiogram v3 bot-er polling loop-ti main thread-e chalacchi
    asyncio.run(main())