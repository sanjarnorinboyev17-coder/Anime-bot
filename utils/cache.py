from aiogram import Bot
from aiogram.types import Message
try:
    from ..database import Database
except ImportError:
    from database import Database


async def cache_channel_message(message: Message, db: Database):
    media = None
    file_type = None
    if message.video:
        media, file_type = message.video.file_id, "video"
    elif message.document:
        media, file_type = message.document.file_id, "document"
    if media:
        await db.save_message(message.message_id, message.caption or "", media, file_type, message.date.isoformat())


async def refresh_cache(bot: Bot, db: Database, channel_id: int):
    # Bot API eski kanal xabarlarini ro'yxat qilib qaytarmaydi. Yangi postlar handler orqali keshga tushadi.
    await bot.get_chat(channel_id)
