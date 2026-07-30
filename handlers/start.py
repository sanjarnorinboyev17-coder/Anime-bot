from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram import F
try:
    from ..database import Database
except ImportError:
    from database import Database

router = Router()

def search_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔎 Anime nomi orqali izlash")],
        [KeyboardButton(text="🔢 Kod orqali izlash")],
        [KeyboardButton(text="📢 Kanal orqali izlash")],
    ], resize_keyboard=True, input_field_placeholder="Qidiruv turini tanlang")

@router.callback_query(F.data == "check_subscription")
async def check_subscription(callback: CallbackQuery, bot, settings):
    member = await bot.get_chat_member(settings.channel_id, callback.from_user.id)
    if member.status in {"creator", "administrator", "member"}:
        await callback.answer("✅ Obuna tasdiqlandi")
        await callback.message.answer("✅ Rahmat! Endi botdan foydalanishingiz mumkin.")
    else:
        await callback.answer("Hali kanalga obuna bo‘lmagansiz", show_alert=True)

@router.message(Command("start"))
async def start(message: Message, db: Database):
    await db.upsert_user(message.from_user)
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) == 2 and parts[1].startswith("anime_"):
        try:
            code = int(parts[1].split("_", 1)[1])
            anime = await db.get_anime(code)
            details = await db.get_anime_details(code)
            rows = await db.get_episodes(code)
            if anime and rows:
                buttons = [[InlineKeyboardButton(text=f"{index + 1}-qism", callback_data=f"episode_get:{row[0]}" ) for index, row in enumerate(rows)]]
                if anime[2]:
                    voice, genre, language = (details[1:] if details else ("", "", "Uzbek tilida"))
                    caption = f"🎬 <b>{anime[1]}</b>\n\n🎤 Ovoz berdi: {voice or '—'}\n📂 Nomi: {anime[1]}\n🎭 Janri: {genre or '—'}\n🌐 Tili: {language or 'Uzbek tilida'}\n🆔 Anime kodi: {code}"
                    if anime[2].startswith("photo:"):
                        return await message.answer_photo(anime[2].split(":", 1)[1], caption=caption, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
                    return await message.answer_video(anime[2], caption=caption, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
            if anime:
                if anime[2]:
                    voice, genre, language = (details[1:] if details else ("", "", "Uzbek tilida"))
                    caption = f"🎬 <b>{anime[1]}</b>\n\n🎤 Ovoz berdi: {voice or '—'}\n📂 Nomi: {anime[1]}\n🎭 Janri: {genre or '—'}\n🌐 Tili: {language or 'Uzbek tilida'}\n🆔 Anime kodi: {code}\n\nHali qismlar qo‘shilmagan."
                    if anime[2].startswith("photo:"):
                        return await message.answer_photo(anime[2].split(":", 1)[1], caption=caption, parse_mode="HTML")
                    return await message.answer_video(anime[2], caption=caption, parse_mode="HTML")
                return await message.answer(f"🎬 <b>{anime[1]}</b>\n\nHali qismlar qo‘shilmagan.", parse_mode="HTML")
        except (ValueError, IndexError):
            pass
    await message.answer("🎬 <b>Anime Finder</b> botiga xush kelibsiz!\n\nQidiruv turini tanlang:", parse_mode="HTML", reply_markup=search_menu())

@router.message(Command("cancel"))
async def cancel(message: Message):
    await message.answer("✅ Amal bekor qilindi.", reply_markup=search_menu())
