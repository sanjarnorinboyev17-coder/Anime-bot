import re
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
try:
    from ..database import Database
except ImportError:
    from database import Database

router = Router()
EPISODES_PER_PAGE = 10
code_search_users: set[int] = set()
NAME_BUTTON = "🔎 Anime nomi orqali izlash"
CODE_BUTTON = "🔢 Kod orqali izlash"
CHANNEL_BUTTON = "📢 Kanal orqali izlash"

def anime_code(caption: str):
    match = re.search(r"(?:kod|code)\s*[:#-]\s*(\d+)|#(\d+)", caption or "", re.I)
    return int(next(value for value in match.groups() if value)) if match else None

def episode_number(caption: str):
    match = re.search(r"(?:qism|episode|ep)\s*[-:#]?\s*(\d+)", caption or "", re.I)
    return int(match.group(1)) if match else 0

def result_keyboard(groups, trailers):
    buttons = []
    for code, caption in groups:
        title = re.sub(r"(?:kod|code)\s*[:#-]?\s*\d+|#\d+", "", caption or "", flags=re.I).strip()[:40]
        buttons.append([InlineKeyboardButton(text=f"🎞 {title or f'Anime {code}'}", callback_data=f"episode_select:{code}:0")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def episode_keyboard(rows, code, page, has_trailer=False):
    start, end = page * EPISODES_PER_PAGE, (page + 1) * EPISODES_PER_PAGE
    buttons = []
    if has_trailer:
        buttons.append([InlineKeyboardButton(text="🎬 Trailer", callback_data=f"trailer_show:{code}")])
    buttons.append([InlineKeyboardButton(text=f"{episode_number(row[1]) or index + 1}-qism", callback_data=f"episode_get:{row[0]}") for index, row in enumerate(rows[start:end], start=start)])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"episode_select:{code}:{page-1}"))
    if end < len(rows): nav.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"episode_select:{code}:{page+1}"))
    if nav: buttons.append(nav)
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="episodes_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def do_search(message: Message, query: str, db: Database):
    await db.upsert_user(message.from_user)
    rows = await db.search(message.from_user.id, query.strip())
    groups, seen = [], set()
    query_lower = query.strip().lower()
    for code, name, _, _ in await db.list_animes():
        if not query_lower or query_lower in name.lower() or query_lower in str(code):
            groups.append((code, name)); seen.add(code)
    for row in rows:
        code = anime_code(row[1])
        if code is not None and code not in seen:
            groups.append((code, row[1])); seen.add(code)
    if not groups:
        return await message.answer("🔎 Kechirasiz, topilmadi. Captionda anime kodi bo‘lishi kerak: <code>kod:26 Naruto 1-qism</code>", parse_mode="HTML")
    trailers = {code for code, _ in groups if await db.get_trailer(code)}
    await message.answer(f"🔎 <b>{len(groups)} ta anime</b> topildi. Anime yoki trailer tanlang:", reply_markup=result_keyboard(groups, trailers), parse_mode="HTML")

async def do_code_search(message: Message, code_text: str, db: Database):
    try:
        code = int(code_text.strip())
    except ValueError:
        return await message.answer("⚠️ Kod faqat raqamlardan iborat bo‘lishi kerak. Masalan: 26")
    anime = await db.get_anime(code)
    if not anime:
        return await message.answer(f"🔎 {code} kodli anime topilmadi.")
    trailers = {code} if await db.get_trailer(code) else set()
    await message.answer("🔎 Faqat shu kodga mos anime topildi:", reply_markup=result_keyboard([(code, anime[1])], trailers))

@router.message(Command("search"))
async def search_command(message: Message):
    from .start import search_menu
    await message.answer("Qidiruv turini tanlang:", reply_markup=search_menu())

@router.message(F.text == NAME_BUTTON)
async def search_by_name(message: Message):
    await message.answer("🔎 Anime nomini yuboring. Bekor qilish: /cancel")

@router.message(F.text == CODE_BUTTON)
async def search_by_code(message: Message):
    code_search_users.add(message.from_user.id)
    await message.answer("🔢 Anime kodini yuboring (masalan: 26). Bekor qilish: /cancel")

@router.message(F.text == CHANNEL_BUTTON)
async def search_by_channel(message: Message, db: Database):
    await message.answer(
        "📢 Anime izlash uchun kanalimizga o‘ting:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga o‘tish", url="https://t.me/animelarxuzbtilda")]
        ])
    )

@router.message(F.text, ~F.text.startswith("/"))
async def search_text(message: Message, bot: Bot, db: Database):
    try:
        if message.from_user.id in code_search_users:
            code_search_users.discard(message.from_user.id)
            await bot.send_chat_action(message.chat.id, "typing")
            return await do_code_search(message, message.text, db)
        code_search_users.discard(message.from_user.id)
        await bot.send_chat_action(message.chat.id, "typing")
        await do_search(message, message.text, db)
    except Exception:
        await message.answer("⚠️ Qidiruvda xatolik yuz berdi.")

@router.callback_query(F.data.startswith("episode_select:"))
async def episode_select(callback: CallbackQuery, db: Database):
    try:
        _, code, page = callback.data.split(":")
        rows = await db.get_episodes(int(code))
        if not rows: return await callback.answer("Bu anime uchun qismlar topilmadi", show_alert=True)
        await callback.answer()
        await callback.message.edit_text(f"🎞 Anime kodi: {code}\nTrailer yoki qismni tanlang:", reply_markup=episode_keyboard(rows, int(code), int(page), bool(await db.get_trailer(int(code)))))
    except Exception:
        await callback.answer("Xatolik yuz berdi", show_alert=True)

@router.callback_query(F.data.startswith("episode_get:"))
async def episode_get(callback: CallbackQuery, bot: Bot, db: Database, settings):
    try:
        await callback.answer("Yuborilmoqda…")
        message_id = int(callback.data.split(":")[1])
        rows = await db.get_message(message_id) if hasattr(db, "get_message") else None
        if rows:
            await bot.send_video(callback.from_user.id, rows[1], caption=rows[0])
        else:
            await bot.forward_message(callback.from_user.id, settings.channel_id, message_id)
    except Exception:
        await callback.message.answer("⚠️ Qismni yuborishda xatolik yuz berdi.")

@router.callback_query(F.data.startswith("trailer_show:"))
async def trailer_show(callback: CallbackQuery, bot: Bot, db: Database):
    try:
        trailer = await db.get_trailer(int(callback.data.split(":")[1]))
        if not trailer: return await callback.answer("Trailer topilmadi", show_alert=True)
        await callback.answer("Trailer yuborilmoqda…")
        if trailer[0].startswith("photo:"):
            await bot.send_photo(callback.from_user.id, trailer[0].split(":", 1)[1], caption="🎬 Anime rasmi")
        else:
            await bot.send_video(callback.from_user.id, trailer[0], caption="🎬 Anime trailer")
    except Exception:
        await callback.message.answer("⚠️ Trailer yuborishda xatolik yuz berdi.")

@router.callback_query(F.data.startswith("anime_download:"))
async def anime_download(callback: CallbackQuery, bot: Bot, db: Database):
    try:
        code = int(callback.data.split(":")[1]); anime = await db.get_anime(code)
        if not anime or not anime[2]: return await callback.answer("Anime topilmadi", show_alert=True)
        rows = await db.get_episodes(code)
        if rows:
            await callback.answer()
            return await callback.message.answer(f"🎬 <b>{anime[1]}</b>\n\nTrailer yoki qismni tanlang:", reply_markup=episode_keyboard(rows, code, 0, bool(await db.get_trailer(code))), parse_mode="HTML")
        await callback.answer("Hali qismlar qo‘shilmagan", show_alert=True)
    except Exception:
        await callback.answer("Xatolik yuz berdi", show_alert=True)

@router.callback_query(F.data.startswith("anime_episodes:"))
async def anime_episodes(callback: CallbackQuery, db: Database):
    try:
        code = int(callback.data.split(":")[1]); rows = await db.get_episodes(code)
        if not rows: return await callback.answer("Hali qismlar qo‘shilmagan", show_alert=True)
        await callback.answer()
        await callback.message.answer(f"📚 Trailer yoki mavjud qismlarni tanlang ({len(rows)} ta):", reply_markup=episode_keyboard(rows, code, 0, bool(await db.get_trailer(code))))
    except Exception:
        await callback.answer("Xatolik yuz berdi", show_alert=True)

@router.callback_query(F.data == "episodes_back")
async def episodes_back(callback: CallbackQuery):
    await callback.answer("Qidiruvni qayta yuboring")
    await callback.message.edit_text("⬅️ Orqaga qaytish uchun anime nomini qayta yuboring.")
