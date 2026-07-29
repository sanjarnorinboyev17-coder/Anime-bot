import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import BaseMiddleware
from aiogram import exceptions
from apscheduler.schedulers.asyncio import AsyncIOScheduler
try:
    from .config import get_settings
    from .database import Database
    from .utils.cache import cache_channel_message, refresh_cache
    from .handlers import start, search, admin
except ImportError:
    from config import get_settings
    from database import Database
    from utils.cache import cache_channel_message, refresh_cache
    from handlers import start, search, admin

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        settings, bot, db = data.get("settings"), data.get("bot"), data.get("db")
        user = getattr(event, "from_user", None)
        if not settings or not bot or not user or user.id in settings.admin_ids:
            return await handler(event, data)
        try:
            channels = await db.required_channels() if db else []
            if not channels:
                channels = [(settings.channel_id, "", "", "")]
            missing = None
            for channel_id, title, username, invite_link in channels:
                member = await bot.get_chat_member(channel_id, user.id)
                if member.status not in {"creator", "administrator", "member"}:
                    missing = (channel_id, title, username, invite_link)
                    break
            if missing:
                chat = await bot.get_chat(missing[0])
                username = missing[3] or missing[2] or getattr(chat, "username", None)
                buttons = []
                if username:
                    buttons.append([InlineKeyboardButton(text="📢 Kanalga obuna bo‘lish", url=f"https://t.me/{username}")])
                buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription")])
                text = "⛔ Botdan foydalanish uchun kanalga obuna bo‘ling.\n\nObuna bo‘lgach, ✅ Tekshirish tugmasini bosing."
                if event.__class__.__name__ == "CallbackQuery":
                    await event.answer("Avval kanalga obuna bo‘ling", show_alert=True)
                    if event.message: await event.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
                else:
                    await event.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
                return
        except Exception:
            pass
        return await handler(event, data)

async def main():
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    db = Database(settings.database_path)
    await db.init()
    bot = Bot(settings.bot_token)
    dp = Dispatcher(db=db, settings=settings)
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())
    dp.include_router(start.router); dp.include_router(admin.router); dp.include_router(search.router)

    @dp.channel_post()
    async def channel_post(message):
        try: await cache_channel_message(message, db)
        except Exception: logging.exception("Channel cache error")

    scheduler = AsyncIOScheduler()
    scheduler.add_job(refresh_cache, "interval", minutes=30, args=(bot, db, settings.channel_id))
    scheduler.start()
    await bot.set_my_commands([BotCommand(command="start", description="Botni boshlash"), BotCommand(command="search", description="Anime qidirish"), BotCommand(command="cancel", description="Bekor qilish")])
    try:
        while True:
            try:
                await dp.start_polling(bot)
                break
            except exceptions.TelegramNetworkError as error:
                logging.warning("Telegram ulanishi uzildi: %s. 5 soniyadan keyin qayta ulanadi.", error)
                await asyncio.sleep(5)
    finally:
        scheduler.shutdown()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
