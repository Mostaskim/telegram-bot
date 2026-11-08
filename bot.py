import asyncio
import logging
import os
import threading
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from flask import Flask

# --- CONFIGURATION ---
TOKEN = "8819749952:AAH5Gcu-Grm4hnNPTxPk6gOFRhHph93qG50"
CHANNEL_ID = -1001004493826491  # Apnar private channel ID

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- 2. KEEP ALIVE (Flask Server for Render Port) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running 24/7!"

def run_flask():
    # Render-er automatic PORT detect korbe, na pele default 10000 use korbe
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# --- 3. BOT LOGIC ---
@dp.message(Command("start"))
async def start_command(message: types.Message):
    await message.answer(
        "👋 Assalamu Alaikum! Amar kache kono Photo ba Video pathan, ami seta channel-e secure kore rekhe ekta link/forward diye dibo jeta 1 minute por auto-delete hoye jabe."
    )

# Jekono media handle korar jonno
@dp.message(F.photo | F.video | F.document)
async def handle_media(message: types.Message):
    try:
        # Private channel-e media store kora
        if message.video:
            await message.forward(chat_id=CHANNEL_ID)
            sent_msg = await message.answer_video(
                video=message.video.file_id,
                caption="⚠️ Ei video-ti 1 minute por auto-delete hoye jabe."
            )
        elif message.photo:
            await message.forward(chat_id=CHANNEL_ID)
            sent_msg = await message.answer_photo(
                photo=message.photo[-1].file_id,
                caption="⚠️ Ei photo-ti 1 minute por auto-delete hoye jabe."
            )
        elif message.document:
            await message.forward(chat_id=CHANNEL_ID)
            sent_msg = await message.answer_document(
                document=message.document.file_id,
                caption="⚠️ Ei file-ti 1 minute por auto-delete hoye jabe."
            )

        # Original message delete kora
        await message.delete()

        # 1 minute (60 seconds) por auto-delete
        await asyncio.sleep(60)
        try:
            await bot.delete_message(chat_id=sent_msg.chat.id, message_id=sent_msg.message_id)
        except Exception as e:
            print(f"Error deleting message: {e}")

    except Exception as e:
        await message.answer(f"Kono shomossha hoyeche: {e}")

# --- 4. MAIN FUNCTION ---
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot is running successfully...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Flask server background thread-e start korchi jate Render port peye jay
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
