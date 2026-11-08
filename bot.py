import asyncio
import logging
import os
import re
from contextlib import suppress
from urllib.parse import urlparse, parse_qs

import asyncpg
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("videofinderx")

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])
DATABASE_URL = os.environ["DATABASE_URL"]
DELETE_AFTER_SECONDS = int(os.getenv("DELETE_AFTER_SECONDS", "60"))

# Normalize Render/Neon-style URLs for asyncpg.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
pool: asyncpg.Pool | None = None
bot_username: str | None = None

LINK_PATTERN = re.compile(
    r"(?:https?://)?t\.me/([A-Za-z0-9_]+)/?\?start=([A-Za-z0-9_-]{1,64})",
    re.IGNORECASE,
)


async def init_db() -> None:
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS media (
                token TEXT PRIMARY KEY,
                channel_message_id BIGINT NOT NULL,
                uploader_user_id BIGINT NOT NULL,
                media_type TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS deliveries (
                id BIGSERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                delete_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(chat_id, message_id)
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS deliveries_delete_at_idx
            ON deliveries(delete_at)
        """)
    log.info("Database initialized")


def make_share_link(token: str) -> str:
    return f"https://t.me/{bot_username}?start={token}"


async def save_media(message: Message) -> None:
    if message.from_user is None:
        await message.answer("এই Media-টি User Account থেকে পাঠান।")
        return

    if message.photo:
        media_type = "photo"
    elif message.video:
        media_type = "video"
    else:
        await message.answer("শুধু Photo অথবা Video Upload করতে পারবেন।")
        return

    status = await message.answer("⏳ Media সংরক্ষণ করছি...")
    try:
        # Copy the original upload into the private storage channel.
        stored = await bot.copy_message(
            chat_id=CHANNEL_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        # Short, URL-safe token accepted by Telegram deep links.
        import secrets
        token = secrets.token_urlsafe(12).replace(".", "_")
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO media(token, channel_message_id, uploader_user_id, media_type)
                VALUES($1, $2, $3, $4)
                """,
                token,
                stored.message_id,
                message.from_user.id,
                media_type,
            )

        await status.edit_text(
            "✅ তোমার Media সংরক্ষণ করা হয়েছে!\n\n"
            f"🔗 Share Link:\n{make_share_link(token)}\n\n"
            "যে কেউ এই Link দিয়ে Media দেখতে পারবে। "
            f"দেখার {DELETE_AFTER_SECONDS} সেকেন্ড পর তার Chat থেকে Media মুছে যাবে।"
        )
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        log.exception("Could not store media in channel")
        await status.edit_text(
            "❌ Channel-এ Media সংরক্ষণ করা যায়নি। Bot-কে Private Channel-এর "
            "Administrator করে Post Messages permission দিন এবং CHANNEL_ID যাচাই করুন."
        )
    except Exception:
        log.exception("Upload failed")
        await status.edit_text("❌ Upload ব্যর্থ হয়েছে। একটু পরে আবার চেষ্টা করুন।")


async def deliver_media(chat_id: int, token: str) -> None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT channel_message_id FROM media WHERE token = $1",
            token,
        )

    if row is None:
        await bot.send_message(chat_id, "❌ এই Link পাওয়া যায়নি অথবা ভুল Link।")
        return

    try:
        sent = await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=CHANNEL_ID,
            message_id=row["channel_message_id"],
            protect_content=True,
        )
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO deliveries(chat_id, message_id, delete_at)
                VALUES($1, $2, NOW() + ($3 * INTERVAL '1 second'))
                ON CONFLICT(chat_id, message_id) DO NOTHING
                """,
                chat_id,
                sent.message_id,
                DELETE_AFTER_SECONDS,
            )
    except (TelegramBadRequest, TelegramForbiddenError):
        log.exception("Could not deliver media")
        await bot.send_message(
            chat_id,
            "❌ Media পাঠানো যায়নি। হয়তো Original Media Channel থেকে মুছে গেছে "
            "অথবা Bot-এর Channel Access নেই।",
        )


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    # /start may optionally include a share token.
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2:
        await deliver_media(message.chat.id, parts[1].strip())
        return

    await message.answer(
        "👋 Welcome to VideoFinder!\n\n"
        "📤 একটি Photo অথবা Video পাঠান — আমি সেটি Store করে Share Link দেব।\n"
        "🔗 অন্য কারও VideoFinder Link পাঠালেও Media দেখাতে পারব.\n\n"
        f"⏱️ শেয়ার করা Media {DELETE_AFTER_SECONDS} সেকেন্ড পর এই Chat থেকে মুছে যাবে।"
    )


@dp.message(F.photo | F.video)
async def media_handler(message: Message) -> None:
    await save_media(message)


@dp.message(F.text)
async def link_text_handler(message: Message) -> None:
    text = message.text or ""
    match = LINK_PATTERN.search(text)
    if not match:
        await message.answer(
            "একটি Photo/Video পাঠান, অথবা VideoFinder-এর Share Link পাঠান।"
        )
        return

    linked_username, token = match.groups()
    if bot_username and linked_username.lower() != bot_username.lower():
        await message.answer("এটি VideoFinder Bot-এর Link নয়।")
        return
    await deliver_media(message.chat.id, token)


async def deletion_worker() -> None:
    """Delete due messages from users' chats, including after a worker restart."""
    while True:
        try:
            async with pool.acquire() as conn:
                due = await conn.fetch(
                    """
                    SELECT id, chat_id, message_id
                    FROM deliveries
                    WHERE delete_at <= NOW()
                    ORDER BY delete_at
                    LIMIT 100
                    """
                )
            for item in due:
                try:
                    await bot.delete_message(
                        chat_id=item["chat_id"],
                        message_id=item["message_id"],
                    )
                    async with pool.acquire() as conn:
                        await conn.execute("DELETE FROM deliveries WHERE id = $1", item["id"])
                except TelegramBadRequest as exc:
                    # Already deleted / too old / otherwise not deletable: stop retrying.
                    log.info("Delete skipped for %s: %s", item["message_id"], exc)
                    async with pool.acquire() as conn:
                        await conn.execute("DELETE FROM deliveries WHERE id = $1", item["id"])
                except TelegramForbiddenError:
                    # Keep the row so the worker can retry if permissions are restored.
                    log.warning("No permission to delete in chat %s", item["chat_id"])
        except Exception:
            log.exception("Deletion worker error")
        await asyncio.sleep(2)


async def main() -> None:
    global bot_username
    await init_db()

    # Ensure the bot is configured with the expected channel access.
    me = await bot.get_me()
    bot_username = me.username
    log.info("Starting @%s", bot_username)

    # Remove stale webhook before starting long polling.
    await bot.delete_webhook(drop_pending_updates=False)

    delete_task = asyncio.create_task(deletion_worker())
    try:
        await dp.start_polling(bot)
    finally:
        delete_task.cancel()
        with suppress(asyncio.CancelledError):
            await delete_task
        if pool:
            await pool.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
